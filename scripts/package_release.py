"""Produce an audited source ZIP and optional GitHub tree payload from an allowlist."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import tomllib
import zipfile


ROOT = Path(__file__).resolve().parent.parent
FIXED = ("README.md", "DEPLOY.md", "DEEPSEEK.md", "ADVANCED.md", "AUTHENTICATION.md", "AGENTS.md", "LICENSE", "CHANGELOG.md",
         "pyproject.toml", "requirements.lock", "MANIFEST.in", "install.py", "install_deepseek.py", "setup_canvas.py", "start_deepseek.py", "server.py", ".gitignore",
         "canvas.example.toml", "canvas-account.example.json", "mcp-config.example.json", "scripts/package_release.py", "scripts/verify_deepseek.mjs", ".github/workflows/ci.yml")


def public_files(root=ROOT):
    paths = [root / name for name in FIXED]
    paths += sorted((root / "canvas_bridge").glob("*.py"))
    paths += sorted((root / "tests").glob("test_*.py"))
    if any(not p.is_file() or p.is_symlink() for p in paths):
        raise ValueError("A required public file is missing or is a symbolic link.")
    return sorted(set(paths))


def audit(paths, root=ROOT, known_secret=None):
    records, entries = [], []
    patterns = [re.compile(r"\b\d+~[A-Za-z0-9_+/-]{40,}"),
                re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),
                re.compile(r"/Users/[^/\s]+/(?:Desktop|Documents)/"),
                re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+\\(?:Desktop|Documents)\\")]
    for path in paths:
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            def contains_credential(value):
                if isinstance(value, dict):
                    return any((key.lower() in {"api_key", "token", "access_token", "client_secret"} and bool(item))
                               or contains_credential(item) for key, item in value.items())
                return isinstance(value, list) and any(contains_credential(item) for item in value)
            if contains_credential(json.loads(text)):
                raise ValueError("Publication audit failed for " + relative + "; a public JSON template contains a credential value.")
        if (known_secret and known_secret in text) or any(p.search(text) for p in patterns):
            raise ValueError("Publication audit failed for " + relative + "; contents were not printed.")
        records.append({"path": relative, "sha256": hashlib.sha256(text.encode()).hexdigest()})
        entries.append({"path": relative, "mode": "100644", "type": "blob", "content": text})
    return records, entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    parser.add_argument("--payload", action="store_true", help="Write an ignored local JSON tree payload")
    parser.add_argument("--secret-file", type=Path, help="Optional local credential used only for an exact-match leak check")
    args = parser.parse_args()
    secret = None
    if args.secret_file:
        sys.path.insert(0, str(ROOT))
        from canvas_bridge.config import read_token
        secret = read_token(args.secret_file)
    paths = public_files()
    records, entries = audit(paths, known_secret=secret)
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    output = args.output_dir.expanduser().absolute()
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"canvas-agent-bridge-{version}-source.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for entry in entries:
            bundle.writestr(f"canvas-agent-bridge-{version}/" + entry["path"], entry["content"])
    manifest = {"version": version, "file_count": len(records), "files": records,
                "source_archive": archive.name, "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if args.payload:
        local = ROOT / ".release"
        local.mkdir(exist_ok=True)
        (local / "publish-payload.local.json").write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"audit": "passed", "version": version, "file_count": len(records),
                      "archive": str(archive), "archive_sha256": manifest["archive_sha256"]}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # These failures reference paths and validation status only.
        print(str(error) if isinstance(error, ValueError) else "Release packaging failed; private contents were not printed.", file=sys.stderr)
        raise SystemExit(1)
