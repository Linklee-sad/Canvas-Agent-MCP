from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import tomllib
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
import zipfile
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent.parent


def user_config_path() -> Path:
    if os.name == "nt":
        folder = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
    else:
        folder = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return folder / "canvas-agent-bridge" / "config.toml"


def default_config_path() -> Path:
    explicit = os.environ.get("CANVAS_CONFIG")
    if explicit:
        return Path(explicit).expanduser().absolute()
    # Keep existing source-checkout installations working. Public clones don't
    # contain this ignored file; wheel installs use the per-user configuration.
    legacy = ROOT / "canvas.toml"
    if (ROOT / "pyproject.toml").is_file() and legacy.is_file():
        return legacy
    existing_user = user_config_path()
    if existing_user.is_file():
        return existing_user
    account = ROOT / "canvas-account.local.json"
    if (ROOT / "pyproject.toml").is_file() and account.is_file():
        return account
    return user_config_path()


def read_config_data(config_path=None):
    path = Path(config_path or default_config_path()).expanduser().absolute()
    try:
        if path.exists():
            if path.suffix.lower() == ".json":
                data = json.loads(path.read_text(encoding="utf-8-sig"))
                if not isinstance(data, dict):
                    raise BridgeError("账号 JSON 格式不正确，请保留外层花括号，只填写双引号里的内容。")
            else:
                data = tomllib.loads(path.read_text(encoding="utf-8"))
        elif config_path or os.environ.get("CANVAS_CONFIG"):
            raise BridgeError("指定的 Canvas 配置文件不存在。")
        else:
            data = {}
        local_path = path.with_name("canvas.local.toml")
        if path.name == "canvas.toml" and local_path.exists():
            data.update(tomllib.loads(local_path.read_text(encoding="utf-8")))
        return path, data
    except BridgeError:
        raise
    except (OSError, ValueError):
        raise BridgeError("无法加载配置，请检查 JSON/TOML 格式和文件权限；不要把文件里的 key 发到聊天里。") from None


class BridgeError(Exception):
    """An actionable error safe to show to the agent."""


def ensure_account_file(path: Path) -> bool:
    """Create a private blank account file, preserving anything already there."""
    path = Path(path)
    if path.is_symlink():
        raise BridgeError("账号文件不能是符号链接，请使用普通的本地文件。")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump({"base_url": "", "api_key": "", "timezone": "Asia/Hong_Kong"}, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return True


def validate_token(token):
    if not isinstance(token, str) or not token or any(c.isspace() for c in token):
        raise BridgeError("key 为空或包含空格、换行，请在本地账号文件中检查；不要将 key 发到聊天里。")
    return token


def read_token(path: Path) -> str:
    try:
        if path.suffix.lower() == ".json":
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(data, dict):
                raise BridgeError("授权 JSON 格式不正确。")
            token = data.get("api_key")
        elif path.suffix.lower() == ".docx":
            with zipfile.ZipFile(path) as archive:
                if archive.getinfo("word/document.xml").file_size > 1_000_000:
                    raise BridgeError("凭据文档过大，请使用只包含一个令牌的文件。")
                root = ET.fromstring(archive.read("word/document.xml"))
                ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                text = "\n".join(
                    "".join(n.text or "" for n in p.findall(".//w:t", ns))
                    for p in root.findall(".//w:p", ns)
                )
            candidates = set(re.findall(r"(?<![\w~])(?:\d+~)?[A-Za-z0-9_+/-]{40,}(?![\w~])", text))
            candidates = {c for c in candidates if not c.startswith(("http", "schemas"))}
            if len(candidates) != 1:
                raise BridgeError("凭据文档中必须能识别到且只能识别到一个令牌。")
            token = candidates.pop()
        else:
            token = path.read_text(encoding="utf-8").strip()
    except BridgeError:
        raise
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, ET.ParseError):
        raise BridgeError("无法读取令牌文件，请检查 token_file 配置和文件格式。") from None
    return validate_token(token)


@dataclass
class Settings:
    base_url: str
    token: str = field(repr=False)
    cache_dir: Path = ROOT / ".canvas-cache"
    timezone: str = "Asia/Hong_Kong"
    timeout_seconds: int = 30
    max_download_mb: int = 50
    proxy_fake_ip_domains: tuple[str, ...] = ()

    def __post_init__(self):
        parts = urlsplit(self.base_url)
        if (parts.scheme != "https" or not parts.hostname or parts.username or
                parts.password or parts.path not in ("", "/") or parts.query or parts.fragment):
            raise BridgeError("base_url 必须是 Canvas 的 HTTPS 根地址。")
        self.base_url = self.base_url.rstrip("/")
        ZoneInfo(self.timezone)
        if not 1 <= self.timeout_seconds <= 120 or not 1 <= self.max_download_mb <= 200:
            raise BridgeError("timeout_seconds 应为 1–120，max_download_mb 应为 1–200。")
        if any(not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*\.[a-z]{2,}", d) for d in self.proxy_fake_ip_domains):
            raise BridgeError("proxy_fake_ip_domains 必须是明确的域名后缀，不包含通配符或网址。")


def load_settings(config_path: str | Path | None = None) -> Settings:
    path, data = read_config_data(config_path)
    try:
        base_url = os.environ.get("CANVAS_BASE_URL", data.get("base_url", ""))
        if not base_url:
            if path.suffix.lower() == ".json":
                raise BridgeError("请在本地账号 JSON 的 base_url 中填写学校 Canvas 的 https:// 网址。")
            raise BridgeError("尚未配置 Canvas 地址。请运行 canvas-bridge configure 或设置 CANVAS_BASE_URL。")
        token = os.environ.get("CANVAS_TOKEN")
        if not token and path.suffix.lower() == ".json" and data.get("api_key"):
            token = validate_token(data["api_key"])
        if not token:
            configured_file = os.environ.get("CANVAS_TOKEN_FILE", data.get("token_file", ""))
            if not configured_file:
                if path.suffix.lower() == ".json":
                    raise BridgeError("请在本地账号 JSON 的 api_key 中填写你自己的已授权 key，不要发到聊天里。")
                raise BridgeError("尚未配置授权凭据。请使用学校批准的认证流程，并在本地配置 token_file 或 CANVAS_TOKEN。")
            token_path = Path(configured_file).expanduser()
            token = read_token(token_path if token_path.is_absolute() else path.parent / token_path)
        cache = Path(data.get("cache_dir", ".canvas-cache"))
        return Settings(
            base_url=base_url,
            token=token,
            cache_dir=(cache if cache.is_absolute() else path.parent / cache).resolve(),
            timezone=os.environ.get("CANVAS_TIMEZONE", data.get("timezone", "UTC")),
            timeout_seconds=int(data.get("timeout_seconds", 30)),
            max_download_mb=int(data.get("max_download_mb", 50)),
            proxy_fake_ip_domains=tuple(data.get("proxy_fake_ip_domains", [])),
        )
    except BridgeError:
        raise
    except Exception:
        raise BridgeError("无法加载配置，请检查本地账号文件的格式和时区设置。") from None
