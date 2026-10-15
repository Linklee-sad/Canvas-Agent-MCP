import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from canvas_bridge.config import BridgeError, ROOT, default_config_path, ensure_account_file, load_settings, read_token


class AccountJSONTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.path = self.folder / 'canvas-account.local.json'
        environment = {k: v for k, v in os.environ.items() if not k.startswith('CANVAS_')}
        self.env = patch.dict(os.environ, environment, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def fill(self, **overrides):
        data = {'base_url': 'https://canvas.example.edu', 'api_key': 'json-secret-fixture', 'timezone': 'Asia/Hong_Kong'}
        data.update(overrides)
        self.path.write_text(json.dumps(data), encoding='utf-8-sig')

    def test_blank_template_is_private_and_never_overwrites_filled_file(self):
        self.assertTrue(ensure_account_file(self.path))
        self.assertEqual(json.loads(self.path.read_text())['api_key'], '')
        if os.name != 'nt':
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.fill()
        before = self.path.read_bytes()
        self.assertFalse(ensure_account_file(self.path))
        self.assertEqual(self.path.read_bytes(), before)

    def test_json_is_a_direct_configuration_and_credential_file(self):
        self.fill()
        settings = load_settings(self.path)
        self.assertEqual(settings.base_url, 'https://canvas.example.edu')
        self.assertEqual(settings.token, 'json-secret-fixture')
        self.assertEqual(settings.timezone, 'Asia/Hong_Kong')
        self.assertNotIn('json-secret-fixture', repr(settings))
        self.assertEqual(read_token(self.path), 'json-secret-fixture')
        with patch.dict(os.environ, {'CANVAS_CONFIG': str(self.path)}):
            self.assertEqual(load_settings().token, settings.token)

    def test_environment_override_and_json_key_refresh(self):
        self.fill()
        with patch.dict(os.environ, {'CANVAS_TOKEN': 'environment-fixture'}):
            self.assertEqual(load_settings(self.path).token, 'environment-fixture')
        self.fill(api_key='refreshed-json-fixture')
        self.assertEqual(load_settings(self.path).token, 'refreshed-json-fixture')

    def test_blank_and_malformed_values_fail_without_exposing_secrets(self):
        ensure_account_file(self.path)
        with self.assertRaisesRegex(BridgeError, 'base_url'):
            load_settings(self.path)
        for key in ('secret fixture', 'secret\nfixture', ['private-value'], 123):
            self.fill(api_key=key)
            with self.assertRaises(BridgeError) as error:
                load_settings(self.path)
            self.assertNotIn('private-value', str(error.exception))
            self.assertNotIn('secret fixture', str(error.exception))
        for text in ('[]', '{"api_key":"do-not-print-this-value", BAD'):
            self.path.write_text(text)
            with self.assertRaises(BridgeError) as error:
                load_settings(self.path)
            self.assertNotIn('do-not-print-this-value', str(error.exception))

    def test_existing_source_and_user_configuration_take_precedence(self):
        (self.folder / 'pyproject.toml').write_text('')
        user_config = self.folder / 'private' / 'config.toml'
        with patch('canvas_bridge.config.ROOT', self.folder), patch('canvas_bridge.config.user_config_path', return_value=user_config):
            ensure_account_file(self.path)
            self.assertEqual(default_config_path(), self.path)
            user_config.parent.mkdir()
            user_config.write_text('')
            self.assertEqual(default_config_path(), user_config)
            legacy = self.folder / 'canvas.toml'
            legacy.write_text('')
            self.assertEqual(default_config_path(), legacy)

    def test_blank_account_is_pending_and_client_pins_the_file(self):
        ensure_account_file(self.path)
        spec = importlib.util.spec_from_file_location('setup_canvas', ROOT / 'setup_canvas.py')
        setup = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(setup)
        summary = {'installed': True, 'python': 'fixture-python', 'self_test': {'ok': True}, 'codex': {'registered': True}}
        with patch.object(setup.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, json.dumps(summary), '')) as run, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            result = setup.run_setup('codex', config_path=self.path, state_path=self.folder / 'state.json')
        self.assertFalse(result['canvas_connected'])
        self.assertEqual(run.call_count, 1)
        self.assertIn(str(self.path), run.call_args.args[0])
        self.assertIn('填写 base_url', output.getvalue())
        self.assertNotIn('暂时连不上学校', output.getvalue())

    def test_wizard_creates_explicit_json_path_without_requesting_secrets(self):
        spec = importlib.util.spec_from_file_location('setup_canvas', ROOT / 'setup_canvas.py')
        setup = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(setup)
        with patch.object(setup.sys.stdin, 'isatty', return_value=False), \
             patch.object(setup, 'run_setup') as run, contextlib.redirect_stdout(io.StringIO()):
            setup.main(['--client', 'codex', '--config-path', str(self.path)])
        self.assertTrue(self.path.is_file())
        self.assertEqual(json.loads(self.path.read_text())['api_key'], '')
        self.assertEqual(run.call_args.kwargs['config_path'], self.path)

    def test_filled_public_template_is_blocked_from_release(self):
        spec = importlib.util.spec_from_file_location('release', ROOT / 'scripts/package_release.py')
        release = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(release)
        public_template = self.folder / 'canvas-account.example.json'
        public_template.write_text('{"api_key":"otherwise-unrecognizable-secret"}')
        with self.assertRaises(ValueError) as error:
            release.audit([public_template], self.folder)
        self.assertNotIn('otherwise-unrecognizable-secret', str(error.exception))
        files = {p.relative_to(ROOT).as_posix() for p in release.public_files()}
        self.assertIn('canvas-account.example.json', files)
        self.assertNotIn('canvas-account.local.json', files)


if __name__ == '__main__':
    unittest.main()
