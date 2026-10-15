#!/usr/bin/env python3
"""Start the configured Harness without asking beginners to copy patch paths."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

STATE = Path(__file__).resolve().parent / ".canvas-setup.local.json"


def launch(state_path=STATE):
    path = Path(state_path)
    if not path.is_file():
        raise ValueError("还没完成安装。请先运行 setup_canvas.py，选择 DeepSeek Harness。")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("application") != "canvas-agent-bridge-setup" or data.get("client") != "deepseek":
        raise ValueError("还没配置 DeepSeek Harness。请运行 setup_canvas.py，选择 DeepSeek Harness。")
    profile = data.get("profile", "web")
    if not isinstance(profile, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", profile) or profile.lower() == "desktop":
        raise ValueError("启动设置有误，请重新运行安装向导。")
    overlay = data.get("overlay_path")
    if not isinstance(overlay, str) or not Path(overlay).is_absolute() or not Path(overlay).is_file():
        raise ValueError("没有找到连接设置，请重新运行安装向导。")
    executable = shutil.which("dsh")
    if not executable:
        raise ValueError("电脑上没有找到 DeepSeek Harness 命令。请让 agent 安装官方 DeepSeek Harness 后重试。")
    print("正在启动 DeepSeek Harness，并加载 Canvas 连接……", flush=True)
    return subprocess.call([executable, "--profile", profile, "--patch", overlay])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="启动已配置的 DeepSeek Harness，无需填写连接路径。")
    parser.add_argument("--state-path", default=str(STATE))
    args = parser.parse_args()
    try:
        raise SystemExit(launch(args.state_path))
    except (ValueError, OSError) as error:
        print(str(error) if isinstance(error, ValueError) and not isinstance(error, json.JSONDecodeError)
              else "启动设置无法读取，请重新运行 setup_canvas.py。", file=sys.stderr)
        raise SystemExit(1)
