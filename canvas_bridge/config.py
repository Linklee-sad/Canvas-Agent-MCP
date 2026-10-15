from dataclasses import dataclass, field
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
    return user_config_path()


def read_config_data(config_path=None):
    path = Path(config_path or default_config_path()).expanduser().absolute()
    try:
        if path.exists():
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
        raise BridgeError("无法加载配置，请检查 TOML 格式和文件权限。") from None


class BridgeError(Exception):
    """An actionable error safe to show to the agent."""


def read_token(path: Path) -> str:
    try:
        if path.suffix.lower() == ".docx":
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
    except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError):
        raise BridgeError("无法读取令牌文件，请检查 token_file 配置和文件格式。") from None
    if not token or any(c.isspace() for c in token):
        raise BridgeError("令牌为空或包含空白字符。")
    return token


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
            raise BridgeError("尚未配置 Canvas 地址。请运行 canvas-bridge configure 或设置 CANVAS_BASE_URL。")
        token = os.environ.get("CANVAS_TOKEN")
        if not token:
            configured_file = os.environ.get("CANVAS_TOKEN_FILE", data.get("token_file", ""))
            if not configured_file:
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
        raise BridgeError("无法加载配置，请检查 canvas.toml 的格式和时区设置。") from None
