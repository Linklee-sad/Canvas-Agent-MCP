#!/usr/bin/env python3
"""Beginner-friendly setup. Only paths, never raw credentials, are requested."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
STATE = ROOT / ".canvas-setup.local.json"


def local_path(value):
    return Path(value.strip().strip("\"'")).expanduser().absolute()


def save_state(path, data):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("安装记录的位置是一个链接，请换一个保存位置。")
    if path.exists():
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise ValueError("安装记录的位置已有其他文件，请换一个保存位置。") from None
        if not isinstance(previous, dict) or previous.get("application") != "canvas-agent-bridge-setup":
            raise ValueError("安装记录的位置已有其他文件，请换一个保存位置。")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump({"application": "canvas-agent-bridge-setup", **data}, handle, ensure_ascii=False, indent=2)
        temporary = Path(handle.name)
    try:
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def run_setup(client, *, base_url=None, token_file=None, timezone="Asia/Hong_Kong", config_path=None,
              venv_path=None, output_path=None, state_path=STATE, name="canvas"):
    from canvas_bridge.config import BridgeError, Settings, default_config_path
    if client not in ("codex", "deepseek"):
        raise ValueError("请选择 Codex 或 DeepSeek Harness。")
    if bool(base_url) != bool(token_file):
        raise ValueError("学校网址和授权文件路径需要一起提供。")
    if base_url:
        try:
            Settings(base_url, "setup-validation", timezone=timezone)
        except BridgeError:
            raise ValueError("请检查学校网址是否以 https:// 开头，以及时区设置是否正确；不确定时让助手帮你检查。") from None
        if not local_path(str(token_file)).is_file():
            raise ValueError("没有找到这个授权文件。请检查文件位置；不要把密钥本身填在这里。")
    config = local_path(str(config_path or default_config_path()))
    command = [sys.executable, str(ROOT / "install.py"), "--json", "--name", name, "--config-path", str(config)]
    if venv_path:
        command += ["--venv", str(local_path(str(venv_path)))]
    if base_url:
        command += ["--base-url", base_url, "--token-file", str(local_path(str(token_file))), "--timezone", timezone]
    if client == "codex":
        command += ["--register-codex"]
    else:
        command += ["--deepseek"]
        if output_path:
            command += ["--deepseek-output", str(local_path(str(output_path)))]
    print("\n[1/3] 正在安装需要的组件，首次安装可能需要几分钟……", flush=True)
    install_environment = os.environ.copy()
    install_environment["PYTHONUTF8"] = "1"
    completed = subprocess.run(command, cwd=ROOT, env=install_environment, capture_output=True,
                               text=True, encoding="utf-8", errors="replace")
    if completed.returncode:
        # Keep detailed diagnostics local, out of the beginner's console.
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".log", prefix="canvas-install-", delete=False) as log:
            log.write(completed.stdout + "\n" + completed.stderr)
            log_path = log.name
        raise ValueError("这次安装没有完成。请让 agent 检查本机日志：" + log_path)
    try:
        summary = json.loads(completed.stdout)
        if not summary.get("installed") or not summary.get("self_test", {}).get("ok"):
            raise ValueError()
    except (ValueError, AttributeError):
        raise ValueError("还没有完成工具检查，请让 agent 检查安装结果后重试。") from None
    print("[2/3] 功能检查通过：14 项功能可以启动。", flush=True)
    print("[3/3] 正在检查你的 Canvas 连接……", flush=True)
    account_ok = False
    json_pending = False
    if config.is_file() and config.suffix.lower() == ".json":
        try:
            from canvas_bridge.config import read_config_data
            _, account = read_config_data(config)
            json_pending = not (account.get("base_url") and (account.get("api_key") or account.get("token_file")))
        except BridgeError:
            pass
    if config.is_file() and not json_pending:
        environment = os.environ.copy()
        environment["PYTHONUTF8"] = "1"
        environment["CANVAS_CONFIG"] = str(config)
        checked = subprocess.run([summary["python"], "-m", "canvas_bridge", "doctor"], cwd=ROOT,
                                 env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if checked.returncode == 0:
            try:
                account_ok = json.loads(checked.stdout).get("ok") is True
            except ValueError:
                pass
    state = {"client": client, "config_path": str(config)}
    if client == "deepseek":
        state.update({"overlay_path": summary["deepseek"]["overlay_path"], "profile": "web"})
    save_state(state_path, state)
    print("\n安装完成。")
    if account_ok:
        print("Canvas 连接成功，已经可以读取你的课程。")
    elif json_pending:
        print("工具已装好。现在用文本编辑器打开这个文件：")
        print("  " + str(config))
        print("填写 base_url（学校 https:// 网址）和 api_key（你自己的 key），保存后让助手查询课程即可。")
        print("不要把 key 发到聊天里，也不要上传这个文件。")
    elif not config.is_file():
        print("工具已装好；还没连接学校账号。拿到已有授权文件后，再运行一次这个向导即可。")
    else:
        print("工具已装好，但暂时连不上学校。请让 agent 检查学校网址、网络和授权是否有效。")
    if client == "codex":
        if summary.get("codex", {}).get("registered"):
            print("Codex 已添加好。重新打开 Codex 或重新连接工具，再新建聊天，发送：列出我的 Canvas 课程。")
        else:
            print("电脑上没有找到 Codex 命令。请把这句话发给 Codex：帮我完成 Canvas 工具注册，并检查是否能读取课程。")
    else:
        print("以后启动时，在项目文件夹运行：")
        print("  " + ("py -3" if os.name == "nt" else "python3") + " start_deepseek.py")
        if not summary["deepseek"].get("dsh_cli_available"):
            print("电脑上还没找到 DeepSeek Harness 命令，请先让 agent 帮你安装官方 DeepSeek Harness。")
        print("启动后新建聊天，发送：列出我的 Canvas 课程。看到课程列表，才表示整个连接成功。")
    return {"installed": True, "canvas_connected": account_ok, "client": client}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Canvas 安装向导：选客户端，再按提示操作。")
    parser.add_argument("--client", choices=("codex", "deepseek"))
    parser.add_argument("--base-url")
    parser.add_argument("--token-file")
    parser.add_argument("--timezone", default="Asia/Hong_Kong", help="截止时间显示时区，默认香港/北京时间")
    parser.add_argument("--config-path")
    parser.add_argument("--venv")
    parser.add_argument("--deepseek-output")
    parser.add_argument("--state-path", default=str(STATE))
    parser.add_argument("--name", default="canvas")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 11):
        raise ValueError("需要 Python 3.11 或更新版本。请让 agent 帮你安装后重试。")
    print("Canvas 安装向导\n让你的 AI 助手读取课程、作业和课件。\n")
    client = args.client
    if not client:
        if not sys.stdin.isatty():
            raise ValueError("请指定 --client codex 或 --client deepseek；也可以在终端直接运行向导进行选择。")
        choice = input("你使用哪个助手？输入 1 = Codex，2 = DeepSeek Harness，然后回车：").strip()
        if choice not in ("1", "2"):
            raise ValueError("请输入 1 或 2，再运行一次即可。")
        client = {"1": "codex", "2": "deepseek"}[choice]
    if bool(args.base_url) != bool(args.token_file):
        raise ValueError("学校网址和授权文件路径需要一起提供。没有授权文件时可以先不填。")
    from canvas_bridge.config import default_config_path
    config = local_path(str(args.config_path or default_config_path()))
    if not args.config_path and not os.environ.get("CANVAS_CONFIG") and not args.base_url and not config.exists():
        config = ROOT / "canvas-account.local.json"
    if not args.base_url and config.suffix.lower() == ".json" and not config.exists():
        from canvas_bridge.config import BridgeError, ensure_account_file
        try:
            ensure_account_file(config)
        except BridgeError as error:
            raise ValueError(str(error)) from None
    if not args.base_url and config.suffix.lower() == ".json":
        print("账号文件：" + str(config))
        print("用文本编辑器打开，只在双引号里填写 base_url（学校网址）和 api_key（你自己的 key），保存即可。")
        print("不要把 key 发到聊天里，也不要上传这个文件。")
    elif not args.base_url and config.exists():
        print("检测到已有 Canvas 设置，将继续使用。")
    elif not args.base_url and sys.stdin.isatty():
        print("如果已有学校批准的授权文件，可以现在连接；没有的话直接回车跳过。")
        args.base_url = input("学校的 Canvas 网址（浏览器地址栏里 https:// 开头的网址）：").strip() or None
        if args.base_url:
            args.token_file = input("授权文件的完整路径（不要输入文件里的密钥）：").strip() or None
            if not args.token_file:
                args.base_url = None
                print("先跳过账号连接，继续安装。")
    run_setup(client, base_url=args.base_url, token_file=args.token_file, timezone=args.timezone,
              config_path=config, venv_path=args.venv, output_path=args.deepseek_output,
              state_path=local_path(args.state_path), name=args.name)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print("\n" + (str(error) if isinstance(error, ValueError) else "操作没有完成，请让 agent 帮你检查本机文件和权限。"), file=sys.stderr)
        raise SystemExit(1)
    except (EOFError, KeyboardInterrupt):
        print("\n已退出向导，可以稍后重新运行。")
        raise SystemExit(1)
