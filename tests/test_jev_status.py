"""Read-only status tests: synthetic config/telemetry only, no plugin imports."""
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('jev_status', ROOT/'scripts/jev_status.py')
status = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(status)


class StatusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT/'tests')
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.state = self.home/'state'/'tao-jev'
        self.state.mkdir(parents=True)

    def config(self):
        import yaml
        c = {'context': {'engine': 'tao-jev'}, 'plugins': {'enabled': ['tao-jev'],
             'entries': {'tao-jev': {'enabled': True, 'settings': {
                 'mode': 'active', 'session_scope': 'personal_pilot',
                 'state_dir': str(self.state), 'total_limit_usd': .9,
                 'daily_limit_usd': .1, 'per_call_limit_usd': .02, 'max_requests': 100,
                 'authorized_task': 'DO_NOT_PRINT', 'api_key': 'DO_NOT_PRINT'}}}},
             'unrelated': 'DO_NOT_PRINT'}
        (self.home/'config.yaml').write_text(yaml.safe_dump(c))

    def metrics(self, records):
        (self.state/'metrics.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))

    def ledger(self, rows):
        with sqlite3.connect(self.state/'budget.sqlite3') as c:
            c.execute('CREATE TABLE spend (id INTEGER PRIMARY KEY, day TEXT, amount REAL, actual REAL, settled INTEGER DEFAULT 0)')
            c.executemany('INSERT INTO spend(day,amount,actual,settled) VALUES (?,?,?,?)', rows)

    def test_missing_not_zero_and_no_creation(self):
        before = set(self.home.rglob('*'))
        result = status.collect(self.home)
        self.assertEqual(result['config']['status'], 'missing')
        self.assertEqual(result['metrics']['status'], 'unknown')
        self.assertIsNone(result['metrics']['attempts'])
        self.assertEqual(before, set(self.home.rglob('*')))

    def test_config_whitelist(self):
        self.config()
        result = status.collect(self.home)
        self.assertTrue(result['config']['selected'])
        self.assertTrue(result['config']['enabled'])
        self.assertEqual(result['config']['mode'], 'active')
        self.assertNotIn('DO_NOT_PRINT', json.dumps(result))
        self.assertEqual(result['metrics']['status'], 'missing')
        self.assertIsNone(result['metrics']['attempts'])

    def test_metrics_partial_and_shadow_not_commit(self):
        self.config()
        self.metrics([
            {'schema': 1, 'mode': 'active', 'outcome': 'pruned', 'groups_pruned': 2,
             'candidate_bytes_saved': 1000, 'elapsed_ms': 10, 'cost_usd': .001},
            {'schema': 1, 'mode': 'shadow', 'outcome': 'fallback', 'shadow': True,
             'candidate_bytes_saved': 500, 'elapsed_ms': 20, 'cost_usd': None},
            {'schema': 1, 'mode': 'active', 'outcome': 'retained', 'reason': 'busy'}])
        m = status.collect(self.home)['metrics']
        self.assertEqual((m['attempts'], m['pruned'], m['fallback'], m['shadow']), (3, 1, 1, 1))
        self.assertEqual(m['totals']['candidate_bytes_saved']['known_sum'], 1500)
        self.assertEqual(m['totals']['cost_usd']['unknown_records'], 2)
        self.assertIsNone(m['totals']['cost_usd']['total'])
        self.assertEqual(m['totals']['elapsed_ms']['known_sum'], 30)

    def test_empty_is_observed_zero(self):
        self.config()
        self.metrics([{'schema': 1, 'mode': 'active', 'outcome': 'fallback', 'reason': 'no_candidates'},
                      {'schema': 1, 'mode': 'active', 'outcome': 'fallback', 'reason': ['DO_NOT_PRINT']}])
        m = status.collect(self.home)['metrics']
        self.assertEqual(m['reasons'], {'no_candidates': 1, 'unknown': 1})
        self.assertNotIn('DO_NOT_PRINT', json.dumps(m))

    def test_empty_records_are_observed_zero(self):
        self.config(); self.metrics([]); self.ledger([])
        r = status.collect(self.home)
        self.assertEqual(r['metrics']['attempts'], 0)
        self.assertEqual(r['budget']['rows'], 0)
        self.assertEqual(r['budget']['accounted_usd'], 0)

    def test_malformed_lines_and_future_schema(self):
        self.config()
        (self.state/'metrics.jsonl').write_text('{oops\n[]\n'+json.dumps({'schema': 2, 'outcome': 'pruned'})+'\n'+json.dumps({'schema': 1, 'mode': 'active', 'outcome': 'retained', 'cost_usd': -2})+'\n')
        m = status.collect(self.home)['metrics']
        self.assertEqual(m['status'], 'partial')
        self.assertEqual(m['invalid_records'], 3)
        self.assertEqual(m['attempts'], 1)
        self.assertIsNone(m['totals']['cost_usd']['known_sum'])

    def test_bad_config(self):
        for text in ('x: [', '[]', 'plugins: []'):
            (self.home/'config.yaml').write_text(text)
            self.assertEqual(status.collect(self.home)['config']['status'], 'malformed')

    def test_budget_actual_vs_reservation_and_reconciled(self):
        self.config()
        self.ledger([('2026-09-20', .02, None, 0), ('2026-09-20', .001, .001, 1),
                     ('2026-09-20', .02, None, 1), ('2026-09-20', .03, .03, 0)])
        b = status.collect(self.home)['budget']
        self.assertAlmostEqual(b['accounted_usd'], .071)
        self.assertAlmostEqual(b['reported_actual_usd'], .031)
        self.assertAlmostEqual(b['conservative_reservations_usd'], .04)
        self.assertEqual(b['unknown_actual_rows'], 2)
        self.assertEqual(b['unsettled_rows'], 2)
        self.assertTrue(b['admission_blocked_by_unsettled'])

    def test_malformed_database_and_rows(self):
        self.config()
        (self.state/'budget.sqlite3').write_text('not sqlite')
        self.assertEqual(status.collect(self.home)['budget']['status'], 'malformed')
        (self.state/'budget.sqlite3').unlink()
        self.ledger([('2026-09-20', -1, None, 0)])
        self.assertEqual(status.collect(self.home)['budget']['status'], 'malformed')

    def test_wal_refused_without_side_effects(self):
        self.config(); self.ledger([])
        (self.state/'budget.sqlite3-wal').write_bytes(b'pending')
        self.assertEqual(status.collect(self.home)['budget']['status'], 'busy_or_uncheckpointed')

    def test_symlink_refused(self):
        self.config()
        (self.state/'metrics.jsonl').symlink_to(self.home/'config.yaml')
        self.assertEqual(status.collect(self.home)['metrics']['status'], 'unsafe_path')

    def test_no_file_changes_network_or_plugin_imports(self):
        self.config(); self.metrics([]); self.ledger([])
        before = {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in self.home.rglob('*') if p.is_file()}
        with patch('socket.socket', side_effect=AssertionError('network forbidden')):
            status.collect(self.home)
        after = {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in self.home.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        # Check imports in a fresh interpreter, not this combined-suite process.
        proc = subprocess.run([sys.executable, '-B', '-c',
            "import runpy,sys; runpy.run_path(sys.argv[1]); assert 'plugin.engine' not in sys.modules; assert 'hermes_cli.plugins' not in sys.modules",
            str(ROOT/'scripts/jev_status.py')], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_bundle_and_skill_contract(self):
        import yaml
        bundle = ROOT/'skill/jev-status/scripts/jev_status.py'
        self.assertEqual((ROOT/'scripts/jev_status.py').read_bytes(), bundle.read_bytes())
        text = (ROOT/'skill/jev-status/SKILL.md').read_text()
        front = yaml.safe_load(text.split('---', 2)[1])
        self.assertEqual(front['name'], 'jev-status')
        self.assertLessEqual(len(front['description']), 60)
        self.assertIn('/jev-status', text)
        self.assertIn('venv/bin/python', text)

    def test_number_rejects_nonfinite_bool_and_huge_values(self):
        for value in (True, float('nan'), float('inf'), -1, 10**1000, '1'):
            self.assertFalse(status.number(value))

    def test_cli_native_home_json_and_text(self):
        self.config(); self.metrics([])
        # A tiny import-safe native-constants substitute selects only this fixture.
        (self.home/'hermes_constants.py').write_text('import os\nfrom pathlib import Path\ndef get_hermes_home(): return Path(os.environ["HERMES_HOME"])\n')
        env = dict(os.environ, HERMES_HOME=str(self.home), PYTHONPATH=str(self.home), PYTHONDONTWRITEBYTECODE='1')
        for flags in ([], ['--json']):
            proc = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/jev_status.py'), *flags], env=env, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            if flags:
                self.assertEqual(json.loads(proc.stdout)['home'], str(self.home))
            else:
                self.assertIn('Candidate', proc.stdout)
                self.assertIn('unverified', proc.stdout)


if __name__ == '__main__':
    unittest.main()
