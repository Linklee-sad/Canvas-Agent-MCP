"""Portable installation helpers. Credentials are never embedded in MCP settings."""
import asyncio
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib

from .config import BridgeError, Settings, default_config_path, user_config_path


def mcp_configuration(name="canvas", config_path=None, executable=None):
    path = Path(config_path or default_config_path()).expanduser().absolute()
    return {"mcpServers": {name: {
        "command": str(executable or sys.executable),
        "args": ["-m", "canvas_bridge", "serve"],
        "env": {"CANVAS_CONFIG": str(path)},
    }}}


def configure(base_url=None, token_file=None, timezone="UTC", config_path=None, force=False):
    if not base_url or not token_file:
        if not sys.stdin.isatty():
            raise BridgeError("请指定 --base-url 和 --token-file；凭据只需要本地文件路径，不要将令牌贴入聊天。")
        base_url = base_url or input("Canvas HTTPS 地址: ").strip()
        token_file = token_file or input("已有授权凭据文件的本地路径（不是令牌内容）: ").strip()
    # Validate metadata without reading or displaying the credential.
    Settings(base_url, "configuration-validation", timezone=timezone)
    credential = Path(token_file).expanduser().absolute()
    if not credential.is_file():
        raise BridgeError("指定的凭据文件不存在。")
    path = Path(config_path or user_config_path()).expanduser().absolute()
    if path.is_symlink():
        raise BridgeError("配置路径不能是符号链接。")
    if path.exists() and not force:
        try:
            existing = tomllib.loads(path.read_text(encoding="utf-8"))
            if (existing.get("base_url") == base_url.rstrip("/") and existing.get("token_file") == str(credential)
                    and existing.get("timezone") == timezone):
                return {"configured": True, "already_configured": True, "config_path": str(path),
                        "credential_copied": False, "connection_verified": False}
        except (OSError, ValueError):
            pass
        raise BridgeError("配置文件已存在，已保留原配置；需要覆盖时请显式使用 --force。")
    path.parent.mkdir(parents=True, exist_ok=True)
    values = {"base_url": base_url.rstrip("/"), "token_file": str(credential),
              "cache_dir": str(path.parent / "cache"), "timezone": timezone,
              "timeout_seconds": 30, "max_download_mb": 50, "proxy_fake_ip_domains": []}
    text = "\n".join(key + " = " + json.dumps(value, ensure_ascii=False) for key, value in values.items()) + "\n"
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    try:
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return {"configured": True, "config_path": str(path), "credential_copied": False,
            "connection_verified": False, "next_step": "运行 doctor 验证 Canvas 连接。"}


def register_codex(name="canvas", config_path=None):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name):
        raise BridgeError("服务名称应为 1–64 位英文字母、数字、横线或下划线。")
    entry = mcp_configuration(name, config_path)["mcpServers"][name]
    codex = shutil.which("codex")
    if not codex:
        return {"registered": False, "reason": "codex_cli_not_found", "manual_configuration": mcp_configuration(name, config_path)}
    try:
        existing = subprocess.run([codex, "mcp", "get", name, "--json"], capture_output=True, text=True, timeout=30)
        if existing.returncode == 0:
            data = json.loads(existing.stdout)
            transport = data.get("transport", data)
            if (transport.get("command") == entry["command"] and transport.get("args") == entry["args"]
                    and (transport.get("env") or {}).get("CANVAS_CONFIG") == entry["env"]["CANVAS_CONFIG"]):
                return {"registered": True, "name": name, "already_registered": True}
            raise BridgeError("该 MCP 服务名称已被其他配置使用，请指定新的 --name；未覆盖原配置。")
        command = [codex, "mcp", "add", name, "--env", "CANVAS_CONFIG=" + entry["env"]["CANVAS_CONFIG"],
                   "--", entry["command"], *entry["args"]]
        subprocess.run(command, capture_output=True, text=True, check=True, timeout=30)
        verified = subprocess.run([codex, "mcp", "get", name, "--json"], capture_output=True, text=True, check=True, timeout=30)
        data = json.loads(verified.stdout)
        transport = data.get("transport", data)
        if (transport.get("command") != entry["command"] or transport.get("args") != entry["args"]
                or (transport.get("env") or {}).get("CANVAS_CONFIG") != entry["env"]["CANVAS_CONFIG"]):
            raise BridgeError("注册后的配置核对失败，请在 Codex MCP 设置中检查。")
        return {"registered": True, "name": name, "already_registered": False,
                "credentials_in_mcp_config": False}
    except BridgeError:
        raise
    except (OSError, subprocess.SubprocessError, ValueError):
        raise BridgeError("无法注册或核对 Codex MCP；未输出其他配置或凭据信息。") from None


def self_test():
    async def verify():
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        params = StdioServerParameters(command=sys.executable, args=["-m", "canvas_bridge", "serve"],
                                      cwd=tempfile.gettempdir())
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = (await session.list_tools()).tools
                names = sorted(t.name for t in tools)
                if len(names) != 14 or not {"get_upcoming_work", "get_assignment_context", "read_material"} <= set(names):
                    raise BridgeError("MCP 工具列表与预期不符。")
                return {"ok": True, "transport": "stdio", "tool_count": len(names), "tools": names,
                        "canvas_connection_tested": False}
    try:
        return asyncio.run(verify())
    except BridgeError:
        raise
    except Exception:
        raise BridgeError("MCP 离线自检失败，请确认已经将本项目安装到当前 Python 环境。") from None
