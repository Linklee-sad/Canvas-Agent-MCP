"""GET-only HTTP client. API credentials never cross the configured origin."""

import ipaddress
from http.client import IncompleteRead
import json
import re
import socket
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit, parse_qsl
from urllib.request import Request, build_opener, HTTPRedirectHandler, HTTPSHandler

from .config import BridgeError, Settings


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def origin(url: str):
    parts = urlsplit(url)
    return parts.scheme, parts.hostname, parts.port or 443


def valid_id(value: str) -> str:
    value = str(value)
    if not re.fullmatch(r"[1-9][0-9]*", value):
        raise BridgeError("Canvas ID 必须是正整数。")
    return value


class CanvasClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.opener = build_opener(NoRedirect(), HTTPSHandler(context=ssl.create_default_context()))

    def api_url(self, path: str, params=None):
        url = urljoin(self.settings.base_url + "/", path)
        parts = urlsplit(url)
        if (origin(url) != origin(self.settings.base_url) or parts.username or parts.password or
                not parts.path.startswith("/api/v1/") or
                any(k.lower() == "access_token" for k, _ in parse_qsl(parts.query))):
            raise BridgeError("拒绝请求非配置站点的 Canvas API。")
        if params:
            url += ("&" if parts.query else "?") + urlencode(params, doseq=True)
        return url

    def _open(self, url: str, authenticated=True):
        headers = {"User-Agent": "Canvas-Agent-Bridge/0.1", "Accept": "application/json+canvas-string-ids"}
        if authenticated:
            if origin(url) != origin(self.settings.base_url):
                raise BridgeError("拒绝向其他站点发送 Canvas 令牌。")
            headers["Authorization"] = "Bearer " + self.settings.token
        for attempt in range(3):
            try:
                return self.opener.open(Request(url, headers=headers, method="GET"),
                                        timeout=self.settings.timeout_seconds)
            except HTTPError as error:
                if error.code in (301, 302, 303, 307, 308):
                    raise
                retry = error.headers.get("Retry-After", "")
                status = error.code
                error.close()
                if status in (429, 502, 503, 504) and attempt < 2:
                    delay = float(retry) if retry.replace(".", "", 1).isdigit() else 2 ** attempt
                    if delay > 10:
                        raise BridgeError("Canvas 暂时限流，请稍后重试。") from None
                    time.sleep(max(0, delay))
                    continue
                message = {401: "令牌无效或已过期，请更新本地令牌文件。",
                           403: "当前账号无权读取此内容，可能尚未开放。",
                           404: "内容不存在，或当前账号不可见。",
                           429: "Canvas 暂时限流，请稍后重试。"}.get(status, "Canvas 请求失败。")
                raise BridgeError(f"HTTP {status}：{message}") from None
            except (URLError, TimeoutError, OSError):
                if attempt < 2:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise BridgeError("无法连接 Canvas，重试后仍失败，请检查网络、DNS 或代理设置。") from None

    def get(self, path: str, params=None):
        url = self.api_url(path, params)
        for attempt in range(3):
            try:
                with self._open(url) as response:
                    if "json" not in response.headers.get("Content-Type", "").lower():
                        raise BridgeError("Canvas 返回了非 JSON 内容，可能需要重新认证。")
                    try:
                        raw = response.read(16_000_001)
                    except IncompleteRead as error:
                        # Some proxies omit the final HTTP chunk. Accept only a complete
                        # JSON document; truncated JSON is retried, never used as data.
                        raw = error.partial
                    if len(raw) > 16_000_000:
                        raise BridgeError("API 响应过大，请缩小查询范围。")
                    return json.loads(raw), response.headers
            except HTTPError as error:
                error.close()
                raise BridgeError("Canvas API 重定向已阻止，请检查配置的根地址。") from None
            except (ValueError, UnicodeError, OSError):
                if attempt == 2:
                    raise BridgeError("Canvas 响应不完整或无法解析，重试后仍然失败。") from None
                time.sleep(0.5 * (attempt + 1))

    def list(self, path: str, params=None, limit=100):
        if not 1 <= limit <= 1000:
            raise BridgeError("limit 应为 1–1000。")
        query = dict(params or {})
        query.setdefault("per_page", min(limit, 100))
        url = self.api_url(path, query)
        items, seen = [], set()
        while url:
            if url in seen or len(seen) >= 100:
                raise BridgeError("Canvas 分页异常，已停止以避免无限请求。")
            seen.add(url)
            page, headers = self.get(url)
            if not isinstance(page, list):
                raise BridgeError("Canvas 列表接口返回了意外的数据格式。")
            remaining = limit - len(items)
            items.extend(page[:remaining])
            match = re.search(r'<([^>]+)>\s*;\s*rel="next"', headers.get("Link", ""), re.I)
            next_url = match.group(1) if match else None
            if len(items) >= limit:
                return {"items": items, "count": len(items), "truncated": len(page) > remaining or bool(next_url)}
            url = self.api_url(next_url) if next_url else None
        return {"items": items, "count": len(items), "truncated": False}

    def download(self, url: str, expected_size: int | None = None) -> bytes:
        """Follow signed file redirects without forwarding Authorization externally."""
        max_bytes = self.settings.max_download_mb * 1024 * 1024
        auth_allowed = True
        retries, redirects = 0, 0
        for _ in range(9):
            parts = urlsplit(url)
            if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
                raise BridgeError("文件下载地址必须使用 HTTPS。")
            same_origin = origin(url) == origin(self.settings.base_url)
            if not same_origin:
                auth_allowed = False
                try:
                    addresses = socket.getaddrinfo(parts.hostname, parts.port or 443, type=socket.SOCK_STREAM)
                except OSError:
                    raise BridgeError("无法解析课件下载服务器地址。") from None
                fake_ip_domain = any(parts.hostname == d or parts.hostname.endswith("." + d)
                                     for d in self.settings.proxy_fake_ip_domains)
                fake_ip_network = ipaddress.ip_network("198.18.0.0/15")
                def permitted(address):
                    ip = ipaddress.ip_address(address)
                    return ip.is_global or (fake_ip_domain and ip.version == 4 and ip in fake_ip_network)
                if not addresses or any(not permitted(a[4][0]) for a in addresses):
                    raise BridgeError("拒绝下载指向本地或私有网络的文件。")
            try:
                with self._open(url, authenticated=same_origin and auth_allowed) as response:
                    if int(response.headers.get("Content-Length", "0")) > max_bytes:
                        raise BridgeError("文件超过配置的下载大小限制。")
                    if "text/html" in response.headers.get("Content-Type", "").lower():
                        raise BridgeError("下载返回了网页，可能是登录页或外部工具页面。")
                    try:
                        data = response.read(max_bytes + 1)
                    except IncompleteRead as error:
                        if expected_size is None or len(error.partial) != expected_size:
                            raise
                        data = error.partial
                    if len(data) > max_bytes:
                        raise BridgeError("文件超过配置的下载大小限制。")
                    if expected_size is not None and len(data) != expected_size:
                        raise IncompleteRead(data)
                    return data
            except HTTPError as error:
                location = error.headers.get("Location")
                error.close()
                if not location:
                    raise BridgeError("课件下载重定向缺少目标地址。") from None
                redirects += 1
                if redirects > 5:
                    raise BridgeError("课件下载重定向次数过多。") from None
                url = urljoin(url, location)
            except IncompleteRead:
                retries += 1
                if retries >= 3:
                    raise BridgeError("课件下载不完整，重试后仍失败，未保存损坏文件。") from None
                time.sleep(0.5 * retries)
            except (ValueError, OSError):
                raise BridgeError("课件下载中断或响应格式异常。") from None
        raise BridgeError("课件下载重定向次数过多。")
