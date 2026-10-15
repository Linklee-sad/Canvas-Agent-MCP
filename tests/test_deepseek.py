import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from canvas_bridge.config import BridgeError
from canvas_bridge.deepseek import deepseek_configuration, export_deepseek


class DeepSeekTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.config = self.folder / 'private config.toml'
        self.config.write_text('token = "private-fixture-value"\n')
        self.output = self.folder / 'patch with spaces.yml'

    def test_official_insert_contract_and_portable_module(self):
        row = deepseek_configuration('canvas-study', self.config)[0]['insert'][0]
        self.assertEqual(row['name'], '@deepseek-ai/dsh-mcp-client')
        self.assertEqual(row['id'], 'mcp-canvas-study')
        self.assertEqual(row['config']['serverName'], 'canvas-study')
        self.assertEqual(row['config']['command'], sys.executable)
        self.assertEqual(row['config']['args'], ['-m', 'canvas_bridge', 'serve'])
        self.assertEqual(row['config']['env'], {'CANVAS_CONFIG': str(self.config)})
        self.assertNotIn('private-fixture-value', json.dumps(row))

    def test_export_is_opt_in_read_back_and_idempotent(self):
        with patch('canvas_bridge.deepseek.shutil.which', return_value=None):
            first = export_deepseek(config_path=self.config, output_path=self.output)
            before = self.output.read_bytes()
            second = export_deepseek(config_path=self.config, output_path=self.output)
        self.assertTrue(first['exported'])
        self.assertFalse(first['registered'])
        self.assertFalse(first['harness_connection_verified'])
        self.assertFalse(first['dsh_cli_available'])
        self.assertTrue(second['already_exported'])
        self.assertEqual(before, self.output.read_bytes())
        self.assertEqual(first['launch_argv'], ['dsh', '--profile', 'web', '--patch', str(self.output)])
        self.assertEqual(first['verify_config_argv'], first['launch_argv'] + ['--dump-config'])
        self.assertEqual(json.loads(before), deepseek_configuration(config_path=self.config))
        if os.name != 'nt':
            self.assertEqual(self.output.stat().st_mode & 0o777, 0o600)

    def test_existing_user_patch_is_never_overwritten(self):
        self.output.write_text('- insert: []\n# user configuration\n')
        before = self.output.read_bytes()
        with self.assertRaises(BridgeError):
            export_deepseek(config_path=self.config, output_path=self.output)
        self.assertEqual(self.output.read_bytes(), before)

    def test_conflicting_account_or_server_requires_new_output(self):
        export_deepseek(config_path=self.config, output_path=self.output)
        for values in ({'name': 'other'}, {'config_path': self.folder / 'other.toml'}):
            with self.assertRaises(BridgeError):
                export_deepseek(output_path=self.output, **values)

    def test_server_names_and_profiles_reject_injection_and_oversize(self):
        for name in ('', 'x' * 33, 'canvas;command', '../canvas', 'canvas space'):
            with self.assertRaises(BridgeError):
                deepseek_configuration(name, self.config)
        for profile in ('../web', 'web --port 4', 'desktop', ''):
            with self.assertRaises(BridgeError):
                export_deepseek(config_path=self.config, output_path=self.output, profile=profile)
        self.assertFalse(self.output.exists())

    def test_default_output_does_not_touch_harness_profile(self):
        with patch('canvas_bridge.deepseek.user_config_path', return_value=self.folder / 'config.toml'):
            result = export_deepseek(config_path=self.config, profile='headless')
        self.assertEqual(Path(result['overlay_path']), self.folder / 'deepseek-canvas.cordis.patch.yml')
        self.assertEqual(result['launch_argv'][2], 'headless')
        self.assertEqual(result['tool_prefix'], 'mcp__canvas__')

    @unittest.skipIf(os.name == 'nt', 'Symlink creation may require Windows developer mode')
    def test_symlink_output_is_rejected_without_modifying_target(self):
        self.output.symlink_to(self.config)
        before = self.config.read_bytes()
        with self.assertRaises(BridgeError):
            export_deepseek(config_path=self.config, output_path=self.output)
        self.assertEqual(self.config.read_bytes(), before)

    def test_cli_can_export_and_print_config_without_credentials(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith('CANVAS_')}
        command = [sys.executable, '-m', 'canvas_bridge']
        printed = subprocess.run(command + ['config', '--client', 'deepseek', '--config-path', str(self.config)],
                                 check=True, capture_output=True, text=True, env=env)
        self.assertEqual(json.loads(printed.stdout), deepseek_configuration(config_path=self.config))
        exported = subprocess.run(command + ['export-deepseek', '--config-path', str(self.config), '--output', str(self.output)],
                                  check=True, capture_output=True, text=True, env=env)
        self.assertTrue(json.loads(exported.stdout)['exported'])
        self.assertNotIn('private-fixture-value', exported.stdout + exported.stderr)


if __name__ == '__main__':
    unittest.main()
