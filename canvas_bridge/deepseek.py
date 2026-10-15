"""Opt-in Cordis overlays for the official DeepSeek Harness MCP client."""
import json
import os
from pathlib import Path
import re
import shutil
import sys

from .config import BridgeError, default_config_path, user_config_path


def deepseek_configuration(name="canvas", config_path=None, executable=None):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", name):
        raise BridgeError("DeepSeek 服务名称应为 1–32 位英文字母、数字、横线或下划线。")
    path = Path(config_path or default_config_path()).expanduser().absolute()
    return [{"insert": [{"id": "mcp-" + name, "name": "@deepseek-ai/dsh-mcp-client", "config": {
        "serverName": name, "transport": "stdio", "command": str(executable or sys.executable),
        "args": ["-m", "canvas_bridge", "serve"], "env": {"CANVAS_CONFIG": str(path)},
        "toolCallTimeoutMs": 120000,
    }}]}]


def export_deepseek(name="canvas", config_path=None, output_path=None, profile="web"):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", profile) or profile.lower() == "desktop":
        raise BridgeError("请指定有效的 CLI profile，例如 web、headless、sdk 或 acp。")
    overlay = deepseek_configuration(name, config_path)
    path = Path(output_path or user_config_path().parent / ("deepseek-" + name + ".cordis.patch.yml")).expanduser().absolute()
    if path.is_symlink():
        raise BridgeError("DeepSeek 配置导出路径不能是符号链接。")
    already_exported = False
    path.parent.mkdir(parents=True, exist_ok=True)
    # JSON is a YAML 1.2 subset, preserving Windows paths and quoted scalar values.
    content = json.dumps(overlay, ensure_ascii=False, indent=2) + "\n"
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        try:
            same = json.loads(path.read_text(encoding="utf-8")) == overlay
        except (OSError, ValueError):
            same = False
        if not same:
            raise BridgeError("导出文件已有不同内容，已保留原文件；请指定新的 --output。") from None
        already_exported = True
    else:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
    # Read back our own file, never an unrelated profile or credential document.
    if json.loads(path.read_text(encoding="utf-8")) != overlay:
        raise BridgeError("DeepSeek 配置导出后核对失败。")
    executable = shutil.which("dsh")
    launch = [executable or "dsh", "--profile", profile, "--patch", str(path)]
    return {"exported": True, "already_exported": already_exported, "overlay_path": str(path),
            "registered": False, "harness_connection_verified": False,
            "dsh_cli_available": bool(executable), "launch_argv": launch,
            "verify_config_argv": launch + ["--dump-config"],
            "tool_prefix": "mcp__" + name + "__", "credentials_in_overlay": False,
            "next_step": "Launch the chosen Harness profile with this --patch, then verify its 14 Canvas tools. See DEEPSEEK.md."}
