#!/usr/bin/env python3
"""Run with Python 3.11+. Installs from this checkout, independent of the current directory."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import venv


ROOT = Path(__file__).resolve().parent


def run(command, capture=False):
    return subprocess.run(command, cwd=ROOT, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None)


def main():
    parser = argparse.ArgumentParser(description="Install Canvas Agent Bridge and optionally connect Codex")
    parser.add_argument("--register-codex", action="store_true")
    parser.add_argument("--name", default="canvas")
    parser.add_argument("--venv", type=Path, default=ROOT / ".venv")
    parser.add_argument("--config-path", type=Path)
    parser.add_argument("--base-url")
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--timezone", default="UTC")
    parser.add_argument("--check-connection", action="store_true")
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        parser.error("Python 3.11 or newer is required.")
    if bool(args.base_url) != bool(args.token_file):
        parser.error("--base-url and --token-file must be supplied together.")
    target = args.venv.expanduser().absolute()
    python = target / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        venv.EnvBuilder(with_pip=True).create(target)
    run([str(python), "-m", "pip", "install", "-r", str(ROOT / "requirements.lock")])
    run([str(python), "-m", "pip", "install", str(ROOT)])
    base = [str(python), "-m", "canvas_bridge"]
    summary = {"installed": True, "python": str(python), "self_test": json.loads(run(base + ["self-test"], True).stdout)}
    config_path = args.config_path.expanduser().absolute() if args.config_path else None
    if args.base_url:
        command = base + ["configure", "--base-url", args.base_url, "--token-file", str(args.token_file.expanduser().absolute()),
                          "--timezone", args.timezone]
        if config_path:
            command += ["--config-path", str(config_path)]
        configured = json.loads(run(command, True).stdout)
        config_path = Path(configured["config_path"])
        summary["configuration"] = configured
    if args.register_codex:
        command = base + ["register-codex", "--name", args.name]
        if config_path:
            command += ["--config-path", str(config_path)]
        summary["codex"] = json.loads(run(command, True).stdout)
    if args.check_connection:
        environment = os.environ.copy()
        if config_path:
            environment["CANVAS_CONFIG"] = str(config_path)
        checked = subprocess.run(base + ["doctor"], cwd=ROOT, env=environment, check=True, text=True, stdout=subprocess.PIPE)
        summary["connection"] = json.loads(checked.stdout)
    else:
        summary["connection_verified"] = False
        summary["next_step"] = "Configure an institution-approved credential locally, then run doctor. See DEPLOY.md."
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, subprocess.SubprocessError):
        print("Installation did not complete. Review the failed step above; no credentials were printed.", file=sys.stderr)
        raise SystemExit(1)
