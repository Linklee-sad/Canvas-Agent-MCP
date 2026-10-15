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

from canvas_bridge.config import ROOT


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BeginnerSetupTests(unittest.TestCase):
    def setUp(self):
        self.setup = load_script('setup_canvas')
        self.launcher = load_script('start_deepseek')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.config = self.folder / 'account.toml'
        self.state = self.folder / 'setup.json'
        self.overlay = self.folder / 'path with spaces.yml'
        self.overlay.write_text('[]')
        self.summary = {'installed': True, 'python': 'fixture-python', 'self_test': {'ok': True, 'tool_count': 14},
                        'codex': {'registered': True},
                        'deepseek': {'overlay_path': str(self.overlay), 'dsh_cli_available': True}}

    def completed(self, summary=None):
        return subprocess.CompletedProcess([], 0, json.dumps(summary or self.summary), '')

    def test_missing_account_does_not_claim_connected_or_make_http_request(self):
        with patch.object(self.setup.subprocess, 'run', return_value=self.completed()) as run, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            result = self.setup.run_setup('deepseek', config_path=self.config, state_path=self.state)
        self.assertFalse(result['canvas_connected'])
        self.assertEqual(run.call_count, 1)
        self.assertIn('--json', run.call_args.args[0])
        self.assertIn('还没连接学校账号', output.getvalue())
        self.assertIn('start_deepseek.py', output.getvalue())
        self.assertNotIn('launch_argv', output.getvalue())
        state = json.loads(self.state.read_text())
        self.assertEqual(state['overlay_path'], str(self.overlay))

    def test_connection_is_reported_only_after_doctor_success(self):
        self.config.write_text('local-fixture')
        doctor = subprocess.CompletedProcess([], 0, '{"ok": true}', '')
        with patch.object(self.setup.subprocess, 'run', side_effect=[self.completed(), doctor]) as run, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            result = self.setup.run_setup('codex', config_path=self.config, state_path=self.state)
        self.assertTrue(result['canvas_connected'])
        self.assertIn('Canvas 连接成功', output.getvalue())
        self.assertEqual(run.call_args.kwargs['env']['CANVAS_CONFIG'], str(self.config))

    def test_failed_account_check_preserves_successful_installation(self):
        self.config.write_text('local-fixture')
        doctor = subprocess.CompletedProcess([], 1, '', 'private-error-fixture')
        with patch.object(self.setup.subprocess, 'run', side_effect=[self.completed(), doctor]), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            result = self.setup.run_setup('codex', config_path=self.config, state_path=self.state)
        self.assertTrue(result['installed'])
        self.assertFalse(result['canvas_connected'])
        self.assertNotIn('private-error-fixture', output.getvalue())
        self.assertIn('暂时连不上学校', output.getvalue())

    def test_only_credential_path_is_saved_and_passed(self):
        token = self.folder / '授权 file with spaces.token'
        token.write_text('secret-fixture-never-print')
        with patch.object(self.setup.subprocess, 'run', return_value=self.completed()) as run, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.setup.run_setup('codex', base_url='https://canvas.example.edu', token_file='"' + str(token) + '"',
                                 config_path=self.config, state_path=self.state)
        args = run.call_args.args[0]
        self.assertEqual(args[args.index('--token-file') + 1], str(token))
        self.assertEqual(run.call_args.kwargs['env']['PYTHONUTF8'], '1')
        self.assertNotIn(token.read_text(), self.state.read_text() + output.getvalue())

    def test_existing_unrelated_setup_record_is_preserved(self):
        for content in ('[]', '{"application":"other"}', 'user text'):
            self.state.write_text(content)
            with self.assertRaises(ValueError):
                self.setup.save_state(self.state, {'client': 'deepseek'})
            self.assertEqual(self.state.read_text(), content)

    def test_private_setup_record_has_restrictive_permissions(self):
        self.setup.save_state(self.state, {'client': 'deepseek'})
        if os.name != 'nt':
            self.assertEqual(self.state.stat().st_mode & 0o777, 0o600)

    def test_launcher_preserves_spaced_path_and_uses_no_shell(self):
        self.setup.save_state(self.state, {'client': 'deepseek', 'profile': 'web', 'overlay_path': str(self.overlay)})
        with patch.object(self.launcher.shutil, 'which', return_value='dsh'), \
             patch.object(self.launcher.subprocess, 'call', return_value=0) as call, \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.launcher.launch(self.state), 0)
        self.assertEqual(call.call_args.args[0], ['dsh', '--profile', 'web', '--patch', str(self.overlay)])
        self.assertNotIn('shell', call.call_args.kwargs)

    def test_launcher_does_not_run_when_configuration_or_harness_is_missing(self):
        with patch.object(self.launcher.subprocess, 'call') as call:
            with self.assertRaisesRegex(ValueError, '还没完成安装'):
                self.launcher.launch(self.state)
            self.setup.save_state(self.state, {'client': 'deepseek', 'overlay_path': str(self.overlay)})
            with patch.object(self.launcher.shutil, 'which', return_value=None):
                with self.assertRaisesRegex(ValueError, '没有找到 DeepSeek Harness'):
                    self.launcher.launch(self.state)
            call.assert_not_called()

    def test_launcher_rejects_malformed_records_and_injected_profiles(self):
        self.state.write_text('[]')
        with self.assertRaises(ValueError):
            self.launcher.launch(self.state)
        self.setup.save_state(self.folder / 'valid.json', {'client': 'deepseek', 'profile': 'web; command', 'overlay_path': str(self.overlay)})
        with self.assertRaises(ValueError):
            self.launcher.launch(self.folder / 'valid.json')


if __name__ == '__main__':
    unittest.main()
