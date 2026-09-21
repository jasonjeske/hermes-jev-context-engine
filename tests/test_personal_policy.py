"""Approved personal policy, with synthetic content and no provider calls."""
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from plugin.engine import Settings, JevContextEngine, ScoreResult
from plugin.decisions import Budget, DecisionsScorer
from plugin.storage import Archive
from test_plugin import fixture, Fallback


class PersonalPilotTests(unittest.TestCase):
    def settings(self, **changes):
        values = dict(mode='active', session_scope='personal_pilot',
                      egress_authorized=True, employer_data_excluded=True,
                      secrets_excluded=True, task_source='latest_user',
                      protect_first_n=1, protect_last_n=1)
        values.update(changes)
        return Settings(**values)

    def engine(self, **changes):
        scorer = Mock()
        scorer.score.return_value = ScoreResult({'g2': 0})
        return JevContextEngine(settings=self.settings(**changes), scorer=scorer,
                                fallback=Fallback())

    def test_personal_prunes_without_relabel_or_threshold_changes(self):
        with tempfile.TemporaryDirectory() as home:
            e = self.engine(); e.archive = Archive(Path(home) / 'archive')
            m = fixture(); m[6]['content'] = 'Help plan my personal garden project'
            out = e.compress(m)
            self.assertNotEqual(out, m)
            self.assertEqual(e.settings.session_scope, 'personal_pilot')
            self.assertEqual(e.last_metrics['outcome'], 'pruned')
            self.assertEqual(e.settings.max_keep_probability, .10)
            self.assertEqual(e.settings.min_reduction_ratio, .15)
            self.assertEqual(Settings().protect_last_n, 40)
            self.assertEqual(e.scorer.score.call_args.args[1], m[6]['content'])

    def test_exclusion_declarations_required(self):
        for flag in ('employer_data_excluded', 'secrets_excluded'):
            e = self.engine(**{flag: False}); e.compress(fixture())
            e.scorer.score.assert_not_called()
            self.assertEqual(e.last_metrics['reason'], 'privacy_not_authorized')



    def test_no_file_terminal_mailbox_memory_candidates(self):
        for tool in ('search_files', 'read_file', 'terminal', 'execute_code',
                     'session_search', 'memory', 'mailbox_read'):
            e = self.engine(); m = fixture()
            for call in m[2]['tool_calls']: call['function']['name'] = tool
            e.compress(m); e.scorer.score.assert_not_called()
        with self.assertRaises(ValueError):
            self.settings(tool_policy='explicit_public_session_tools', eligible_tools=('read_file',))

    def test_injected_or_ambiguous_latest_user_falls_back(self):
        for text in ('<memory-context>private canary</memory-context>\nPlan my garden',
                     '<memory-context>unclosed canary', '# User Profile\ncanary',
                     'MEMORY.md: canary', '<user_profile>canary</user_profile>',
                     '# Persistent Memory\ncanary'):
            for scope in ('personal_pilot', 'public_synthetic'):
                e = self.engine(session_scope=scope); m = fixture(); m[6]['content'] = text
                e.compress(m); e.scorer.score.assert_not_called()
        e = self.engine(); m = fixture(); m[6]['injected_context'] = 'canary'
        e.compress(m); e.scorer.score.assert_not_called()

    def test_task_and_payload_exclusion_markers(self):
        for text in ('employer data', 'CONFIDENTIAL', 'company internal', 'proprietary',
                     '<memory-context>canary</memory-context>', '# User Profile'):
            for location in ('goal', 'result', 'arguments'):
                e = self.engine(); m = fixture()
                if location == 'goal': m[6]['content'] = text
                elif location == 'result': m[3]['content'] += text
                else: m[2]['tool_calls'][0]['function']['arguments'] = json.dumps({'q': text})
                e.compress(m); e.scorer.score.assert_not_called()

    def test_real_scorer_positive_and_precredential_exclusions(self):
        with tempfile.TemporaryDirectory() as home:
            key = Mock(return_value='offline-placeholder')
            transport = Mock(return_value=json.dumps({'provider': 'TypeSafe',
                'model': 'typesafe/jev-1.13', 'usage': {'cost': .001, 'input_tokens': 20,
                'output_tokens': 0}, 'answers': {'g2': {'type': 'noul', 'noul': 0}}}).encode())
            def scorer(**changes):
                values = dict(budget=Budget(Path(home)/'budget.sqlite3', total_limit=.90,
                    daily_limit=.10, per_call_limit=.02, max_requests=100),
                    key_resolver=key, transport=transport, egress_authorized=True,
                    session_scope='personal_pilot', spend_policy='bounded_local_trial',
                    employer_data_excluded=True, secrets_excluded=True)
                values.update(changes)
                return DecisionsScorer(**values)
            groups = [{'id': 'g2', 'messages': [{'role': 'tool', 'content': 'old garden results'}]}]
            s = scorer()
            self.assertEqual(s.score(groups, 'My garden', deadline=time.monotonic()+5).scores, {'g2': 0})
            payload = json.loads(transport.call_args.args[2])
            self.assertEqual(payload['provider']['data_collection'], 'deny')
            key.reset_mock(); transport.reset_mock()
            for goal in ('CONFIDENTIAL employer task', '<memory-context>canary</memory-context>'):
                with self.assertRaises(RuntimeError): s.score(groups, goal, deadline=time.monotonic()+5)
            for flag in ('employer_data_excluded', 'secrets_excluded'):
                with self.assertRaises(RuntimeError):
                    scorer(**{flag: False}).score(groups, 'My garden', deadline=time.monotonic()+5)
            with patch('agent.redact.redact_sensitive_text', return_value='REDACTED') as redact:
                with self.assertRaises(RuntimeError): s.score(groups, 'My garden', deadline=time.monotonic()+5)
                self.assertEqual(redact.call_args.kwargs, {'force': True, 'redact_url_credentials': True})
            key.assert_not_called(); transport.assert_not_called()

    def test_daily_lifetime_unknown_and_restart_caps(self):
        with tempfile.TemporaryDirectory() as home:
            path = Path(home)/'budget.sqlite3'
            def budget(): return Budget(path, total_limit=.90, daily_limit=.10, per_call_limit=.02, max_requests=100)
            b = budget()
            for _ in range(5):
                ident = b.reserve(); b.settle(ident, .02)
            with self.assertRaises(RuntimeError): budget().reserve()
            with b._db() as db: db.execute("UPDATE spend SET day='2000-01-01'")
            ident = budget().reserve()
            with self.assertRaises(RuntimeError): budget().reserve()
            b.settle(ident, .02)
            with b._db() as db:
                db.execute("UPDATE spend SET day='2000-01-01', amount=.15")
            with self.assertRaises(RuntimeError): budget().reserve()
            with b._db() as db:
                db.execute('DELETE FROM spend')
                db.executemany('INSERT INTO spend(day,amount,actual,settled) VALUES (?,0,0,1)',
                               [('2000-01-01',)]*100)
            with self.assertRaises(RuntimeError): budget().reserve()


if __name__ == '__main__': unittest.main()
