"""Portable installer and native discovery acceptance, only synthetic homes."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import yaml
import plugin
from plugin.decisions import process_transport

ROOT = Path(__file__).resolve().parents[1]


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve()
        self.env = dict(os.environ, HOME=str(self.home), HERMES_HOME=str(self.home), PYTHONDONTWRITEBYTECODE='1')
        self.config = self.home/'config.yaml'
        self.config.write_text(yaml.safe_dump({'model': {'default': 'synthetic-model'}, 'memory': {'provider': 'synthetic-preserve'}}))

    def run_cli(self, command, *args, good=True):
        p = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/install.py'), command, *args], env=self.env, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0 if good else 2, p.stderr+p.stdout)
        return json.loads(p.stdout) if good else p

    def cfg(self): return yaml.safe_load(self.config.read_text())

    def test_full_lifecycle_native_discovery_status_stock_remove(self):
        before = self.config.read_bytes()
        self.run_cli('install')
        self.assertEqual(self.config.read_bytes(), before)
        self.assertFalse((self.home/'plugins').exists())
        self.run_cli('install', '--apply')
        installed = self.config.read_bytes()
        self.assertFalse(self.run_cli('install', '--apply')['changed'])
        self.assertEqual(self.config.read_bytes(), installed)
        self.run_cli('activate', '--apply', good=False)
        self.run_cli('activate', '--opt-in-active', '--apply')
        # Native plugin discovery and selector are real; no AIAgent/provider initialization.
        code = '''import sys
sys.addaudithook(lambda event, args: (_ for _ in ()).throw(RuntimeError('network forbidden')) if event in ('socket.connect','socket.getaddrinfo','socket.sendto') else None)
from hermes_cli.plugins import discover_plugins, get_plugin_context_engine
from hermes_cli.config import load_config_readonly
from agent.agent_init import _select_context_engine
discover_plugins()
e = get_plugin_context_engine()
assert e is not None and e.name == 'tao-jev'
s = _select_context_engine(load_config_readonly())
assert s is not e and s.name == 'tao-jev'
assert not s.settings.egress_authorized
assert _select_context_engine({'context': {'engine': 'compressor'}}) is None
from agent.skill_commands import scan_skill_commands
assert '/jev-status' in scan_skill_commands()
print('native discovery, selector and skill discovery passed')
'''
        p = subprocess.run([sys.executable, '-B', '-c', code], env=self.env, text=True, capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr+p.stdout)
        p = subprocess.run([sys.executable, '-B', str(self.home/'skills/jev-status/scripts/jev_status.py'), '--json'], env=self.env, text=True, capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(json.loads(p.stdout)['config']['selected'])
        self.run_cli('authorize-egress', '--opt-in-egress', '--scope', 'personal_pilot', '--exclude-employer-and-secrets', '--total-usd', '.1', '--daily-usd', '.05', '--per-call-usd', '.02', '--max-requests', '2', '--apply')
        p = subprocess.run([sys.executable, '-B', '-c', code.replace('assert not s.settings.egress_authorized', 'assert s.settings.egress_authorized')], env=self.env, text=True, capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr+p.stdout)
        state = self.home/'state/tao-jev'
        (state/'budget.sqlite3').write_bytes(b'synthetic-preserve-budget')
        (state/'archives').mkdir(); (state/'archives/original.json').write_text('synthetic-original')
        cfg = self.cfg(); cfg['newer_edit'] = 'retain'; self.config.write_text(yaml.safe_dump(cfg))
        self.run_cli('stock', '--apply')
        self.assertEqual(self.cfg()['context']['engine'], 'compressor')
        stock_code = "from hermes_cli.config import load_config_readonly; from agent.agent_init import _select_context_engine; assert _select_context_engine(load_config_readonly()) is None"
        p = subprocess.run([sys.executable, '-B', '-c', stock_code], env=self.env, text=True, capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr+p.stdout)
        self.assertEqual(self.cfg()['newer_edit'], 'retain')
        self.run_cli('remove', '--apply')
        self.assertFalse((self.home/'plugins/tao-jev/__init__.py').exists())
        self.assertFalse((self.home/'skills/jev-status/SKILL.md').exists())
        self.assertEqual((state/'budget.sqlite3').read_bytes(), b'synthetic-preserve-budget')
        self.assertEqual((state/'archives/original.json').read_text(), 'synthetic-original')
        self.assertFalse(self.run_cli('remove', '--apply')['changed'])
        self.assertEqual(self.cfg()['model'], {'default': 'synthetic-model'})
        self.assertEqual(self.cfg()['memory'], {'provider': 'synthetic-preserve'})
        for backup in (state/'backups').iterdir(): self.assertEqual(backup.stat().st_mode & 0o777, 0o600)

    def test_edited_files_and_config_preserved(self):
        self.run_cli('install', '--apply')
        p = self.home/'plugins/tao-jev/engine.py'; p.write_text(p.read_text()+'\n# local edit\n')
        before = self.config.read_bytes()
        self.run_cli('remove', '--apply', good=False)
        self.assertEqual(self.config.read_bytes(), before)
        self.assertTrue(p.read_text().endswith('# local edit\n'))

    def test_config_edit_conflict_and_plan_digest(self):
        plan = self.run_cli('install')
        self.config.write_text(self.config.read_text()+'newer: keep\n')
        self.run_cli('install', '--expect-config-sha256', plan['config_sha256'], '--apply', good=False)
        self.assertFalse((self.home/'plugins').exists())
        self.run_cli('install', '--apply')
        cfg = self.cfg(); cfg['plugins']['entries']['tao-jev']['settings']['max_requests'] = 7
        self.config.write_text(yaml.safe_dump(cfg)); before = self.config.read_bytes()
        self.run_cli('stock', '--apply', good=False)
        self.assertEqual(before, self.config.read_bytes())

    def test_symlink_and_preexisting_conflicts(self):
        (self.home/'plugins').symlink_to(self.home/'elsewhere')
        self.run_cli('install', '--apply', good=False)
        (self.home/'plugins').unlink()
        (self.home/'skills/jev-status').mkdir(parents=True)
        self.run_cli('install', '--apply', good=False)

    def test_concurrent_config_change_is_refused(self):
        spec = importlib.util.spec_from_file_location('installer_under_test', ROOT/'scripts/install.py')
        installer = importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)
        original_read = installer.read
        reads = [0]
        newer = self.config.read_bytes()+b'concurrent: preserved\n'
        def changing_read(path):
            if path == self.config:
                reads[0] += 1
                if reads[0] == 2: self.config.write_bytes(newer)
            return original_read(path)
        with patch('hermes_constants.get_hermes_home', return_value=self.home), patch.object(installer, 'read', side_effect=changing_read):
            with self.assertRaises(SystemExit) as outcome: installer.main(['install', '--apply'])
        self.assertEqual(outcome.exception.code, 2)
        self.assertEqual(self.config.read_bytes(), newer)
        self.assertFalse((self.home/'plugins').exists())

    def test_egress_requires_finite_budgets_and_separate_consent(self):
        self.run_cli('install', '--apply')
        for value in ('nan', 'inf', '-1', '0'):
            self.run_cli('authorize-egress', '--opt-in-egress', '--scope', 'public_synthetic', '--exclude-employer-and-secrets', '--total-usd', value, '--daily-usd', '.1', '--per-call-usd', '.02', '--max-requests', '1', '--apply', good=False)
        self.assertFalse(self.cfg()['plugins']['entries']['tao-jev']['settings']['egress_authorized'])

    def test_host_and_profile_binding(self):
        class Context:
            def __init__(self, cfg): self.cfg = cfg
            def get_config(self, key, default=None): return self.cfg.get(key, default)
            def register_context_engine(self, engine): self.engine = engine
        for actual, target, target_home, admitted in [
            ('workstation.example', 'WORKSTATION.EXAMPLE.', str(self.home), True),
            ('workstation.example', 'other.example', str(self.home), False),
            ('workstation.example', '*', str(self.home), False),
            ('', '', str(self.home), False),
            ('workstation.example', 'workstation.example', str(self.home/'other'), False)]:
            ctx = Context(dict(egress_authorized=True, target_host=target, target_home=target_home))
            with patch('hermes_constants.get_hermes_home', return_value=self.home), patch('hermes_cli.config.load_config_readonly', return_value={}), patch('plugin.platform.node', return_value=actual):
                plugin.register(ctx)
            self.assertEqual(ctx.engine.settings.egress_authorized, admitted)
            self.assertEqual(ctx.engine.scorer.egress_authorized, admitted)
            self.assertEqual(ctx.engine.archive.path, str(self.home/'state/tao-jev/archives'))

    def test_transport_wall_timeout_kills_reaps_and_scrubs(self):
        import time
        from unittest.mock import Mock
        child = Mock(returncode=0)
        child.communicate.side_effect = [subprocess.TimeoutExpired('worker', .01), (b'', b'')]
        with patch('plugin.decisions.subprocess.Popen', return_value=child) as popen, patch.dict(os.environ, {'FAKE_API_KEY': 'synthetic', 'HTTPS_PROXY': 'synthetic'}):
            with self.assertRaises(TimeoutError): process_transport('https://openrouter.ai/api/alpha/decisions', {}, b'{}', time.monotonic()+1)
        child.kill.assert_called_once()
        self.assertEqual(child.communicate.call_count, 2)
        self.assertNotIn('FAKE_API_KEY', popen.call_args.kwargs['env'])
        self.assertNotIn('HTTPS_PROXY', popen.call_args.kwargs['env'])

    def test_worker_rejects_other_endpoint_without_network(self):
        p = subprocess.run([sys.executable, '-I', str(ROOT/'plugin/http_worker.py')], input=json.dumps({'url':'https://example.invalid'}), capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)
        self.assertEqual(p.stdout+p.stderr, '')
