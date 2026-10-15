import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from canvas_bridge.config import BridgeError, ROOT, default_config_path, load_settings
from canvas_bridge.deployment import configure, mcp_configuration, register_codex


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.credential = self.folder / "credentials.token"
        self.credential.write_text("authorized-test-credential")
        self.path = self.folder / "private" / "config.toml"
        environment = {k: v for k, v in os.environ.items() if not k.startswith("CANVAS_")}
        self.environment = patch.dict(os.environ, environment, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_private_configuration_round_trip_without_copying_secret(self):
        result = configure("https://canvas.example.edu", str(self.credential), "Asia/Hong_Kong", self.path)
        self.assertFalse(result["credential_copied"])
        self.assertNotIn(self.credential.read_text(), self.path.read_text())
        settings = load_settings(self.path)
        self.assertEqual(settings.token, "authorized-test-credential")
        self.assertEqual(settings.timezone, "Asia/Hong_Kong")
        if os.name != "nt":
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_configuration_is_idempotent_but_conflicts_are_preserved(self):
        configure("https://canvas.example.edu", str(self.credential), "UTC", self.path)
        before = self.path.read_bytes()
        same = configure("https://canvas.example.edu", str(self.credential), "UTC", self.path)
        self.assertTrue(same["already_configured"])
        with self.assertRaises(BridgeError):
            configure("https://other.example.edu", str(self.credential), "UTC", self.path)
        self.assertEqual(before, self.path.read_bytes())

    def test_installed_package_uses_user_config_and_supports_environment_only(self):
        with patch("canvas_bridge.config.ROOT", self.folder / "site-packages"), \
             patch("canvas_bridge.config.user_config_path", return_value=self.path):
            self.assertEqual(default_config_path(), self.path)
            with patch.dict(os.environ, {"CANVAS_BASE_URL": "https://canvas.example.edu", "CANVAS_TOKEN": "test-env-token"}):
                settings = load_settings()
                self.assertEqual(settings.token, "test-env-token")
                self.assertEqual(settings.timezone, "UTC")

    def test_explicit_config_is_not_silently_ignored(self):
        with patch.dict(os.environ, {"CANVAS_CONFIG": str(self.path), "CANVAS_TOKEN": "test-env-token"}):
            with self.assertRaises(BridgeError):
                load_settings()

    def test_portable_mcp_command_uses_current_interpreter_not_repo_path(self):
        entry = mcp_configuration(config_path=self.path)["mcpServers"]["canvas"]
        self.assertEqual(entry["command"], sys.executable)
        self.assertEqual(entry["args"], ["-m", "canvas_bridge", "serve"])
        self.assertEqual(entry["env"], {"CANVAS_CONFIG": str(self.path)})
        self.assertNotIn("server.py", json.dumps(entry))

    @patch("canvas_bridge.deployment.shutil.which", return_value=None)
    def test_missing_codex_returns_manual_configuration(self, _):
        result = register_codex(config_path=self.path)
        self.assertFalse(result["registered"])
        self.assertIn("manual_configuration", result)

    @patch("canvas_bridge.deployment.shutil.which", return_value="codex")
    @patch("canvas_bridge.deployment.subprocess.run")
    def test_registration_reads_back_exact_transport(self, run, _):
        entry = mcp_configuration(config_path=self.path)["mcpServers"]["canvas"]
        run.side_effect = [subprocess.CompletedProcess([], 1, stdout=""),
                           subprocess.CompletedProcess([], 0, stdout="Added"),
                           subprocess.CompletedProcess([], 0, stdout=json.dumps({"transport": entry}))]
        result = register_codex(config_path=self.path)
        self.assertTrue(result["registered"])
        self.assertFalse(result["credentials_in_mcp_config"])
        self.assertEqual(run.call_count, 3)

    @patch("canvas_bridge.deployment.shutil.which", return_value="codex")
    @patch("canvas_bridge.deployment.subprocess.run")
    def test_conflicting_codex_entry_is_not_overwritten(self, run, _):
        run.return_value = subprocess.CompletedProcess([], 0, stdout=json.dumps({"transport": {"command": "other"}}))
        with self.assertRaises(BridgeError):
            register_codex(config_path=self.path)
        self.assertEqual(run.call_count, 1)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("package_release", ROOT / "scripts/package_release.py")
        self.release = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.release)

    def test_allowlist_excludes_credentials_cache_and_local_reports(self):
        files = self.release.public_files()
        names = {p.relative_to(ROOT).as_posix() for p in files}
        self.assertIn("install.py", names)
        self.assertIn("DEPLOY.md", names)
        self.assertNotIn("canvas.toml", names)
        self.assertNotIn("mcp-config.json", names)
        self.assertFalse(any("verification" in name or "api_key" in name or ".venv" in name for name in names))
        self.release.audit(files)

    def test_known_secret_blocks_publication_without_printing_it(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            document = root / "README.md"
            document.write_text("accidental-value")
            with self.assertRaises(ValueError) as error:
                self.release.audit([document], root, known_secret="accidental-value")
            self.assertNotIn("accidental-value", str(error.exception))

    def test_private_machine_path_blocks_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            document = root / "README.md"
            document.write_text("/Users/" + "example" + "/Desktop/" + "private")
            with self.assertRaises(ValueError):
                self.release.audit([document], root)


if __name__ == "__main__":
    unittest.main()
