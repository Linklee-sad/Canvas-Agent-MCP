#!/usr/bin/env python3
"""DeepSeek Harness entry point; delegates shared installation to install.py."""
import subprocess
import sys
from pathlib import Path


if __name__ == "__main__":
    raise SystemExit(subprocess.call([sys.executable, str(Path(__file__).with_name("install.py")), "--deepseek", *sys.argv[1:]]))
