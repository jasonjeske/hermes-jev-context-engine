"""Review regressions: offline, no credential lookup or inference."""
import copy
import json
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from agent.context_compressor import ContextCompressor
from plugin.engine import JevContextEngine, Settings, ScoreResult
from plugin.decisions import Budget, DecisionsScorer
from plugin.storage import Archive
from test_plugin import fixture, Scorer, Fallback

class Repairs(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
    def engine(self, **kw):
        opts=dict(mode='active',protect_first_n=1,protect_last_n=1,egress_authorized=True)
        opts.update(kw)
        return JevContextEngine(settings=Settings(**opts), scorer=Scorer(), fallback=Fallback(), archive=Archive(Path(self.temp.name)/'a'))
    def test_native_state_is_authoritative(self):
        e=JevContextEngine(); self.assertIsInstance(e,ContextCompressor)
        e.update_model('gpt-6-astra',200000,provider='openai-codex')
        e.record_completed_compaction(); e.update_from_response({'prompt_tokens':190000})
        self.assertEqual(e._ineffective_compression_count,1)
        self.assertFalse(e._verify_compaction_cleared_threshold)
        c=copy.deepcopy(e); self.assertIsNot(c,e)
        c.update_from_response({'prompt_tokens':100}); self.assertEqual(e.last_prompt_tokens,190000)
    def test_native_nondefault_settings_and_model_switch_parity(self):
        from plugin.native_settings import constructor_kwargs
        cfg={'compression':{'threshold':.61,'protect_last_n':40,'target_ratio':.32,
             'abort_on_summary_failure':True,'threshold_tokens':90000,'proactive_prune_tokens':50000,
             'tail_mode':'legacy','min_tail_user_messages':3,'proactive_prune_min_result_chars':9000,
             'proactive_prune_min_reclaim_tokens':4500},'max_tokens':12345,
             'custom_providers':[{'name':'synthetic','base_url':'https://example.invalid'}]}
        kw=constructor_kwargs(cfg,model='gpt-6-astra',provider='openai-codex')
        stock=ContextCompressor(**kw,config_context_length=200000)
        e=JevContextEngine(native_config=cfg)
        e.update_model('gpt-6-astra',200000,provider='openai-codex')
        attrs=('abort_on_summary_failure','threshold_tokens_cap','max_tokens','tail_mode','min_tail_user_messages',
               'proactive_prune_tokens','proactive_prune_min_result_chars','proactive_prune_min_reclaim_tokens',
               'custom_providers','threshold_tokens','tail_token_budget','summary_target_ratio')
        for attr in attrs: self.assertEqual(getattr(e,attr),getattr(stock,attr),attr)
        self.assertIs(e.fallback,e)
        for obj in (stock,e): obj.update_model('synthetic-model',100000,provider='custom')
        for attr in attrs: self.assertEqual(getattr(e,attr),getattr(stock,attr),attr)
        self.assertIs(type(e).record_completed_compaction,ContextCompressor.record_completed_compaction)
        self.assertIs(type(e).bind_session_state,ContextCompressor.bind_session_state)
    def test_host_cancelled_late_fallback_cannot_overwrite_usage(self):
        from agent.auxiliary_client import AuxiliaryExplicitCancellation
        entered=threading.Event(); release=threading.Event(); cancel=threading.Event()
        e=self.engine(mode='off'); errors=[]
        class Slow(Fallback):
            def compress(self,messages,**kw):
                entered.set(); release.wait(2); return messages[:2]
        e.fallback=Slow(); e._compression_cancelled_check=cancel.is_set
        def run():
            try: e.compress(fixture())
            except AuxiliaryExplicitCancellation: errors.append('cancelled')
        t=threading.Thread(target=run); t.start()
        try:
            self.assertTrue(entered.wait(1)); cancel.set()
            e.update_from_response({'prompt_tokens':99})
            other=self.engine(); other.update_from_response({'prompt_tokens':7})
            self.assertEqual(other.last_prompt_tokens,7)
        finally: release.set(); t.join(2)
        self.assertEqual(errors,['cancelled']); self.assertEqual(e.last_prompt_tokens,99)
    def test_unknown_metadata_protected_and_tool_policy_explicit(self):
        e=self.engine(session_scope='public_synthetic',authorized_task='public')
        m=fixture(); m[3]['api_content']='other representation'
        self.assertEqual(e.compress(m),m); self.assertEqual(e.scorer.calls,0)
        with self.assertRaises(ValueError): Settings(eligible_tools=('read_file',))
        s=Settings(eligible_tools=('read_file',),tool_policy='explicit_public_session_tools')
        self.assertEqual(s.session_scope,'disabled')
    def test_oversize_malformed_never_falls_back(self):
        e=self.engine(max_input_bytes=100); m=fixture(); del m[4]
        self.assertEqual(e.compress(m),m); self.assertEqual(e.fallback.calls,0)
    def test_insignificant_reduction_rejected(self):
        e=self.engine(session_scope='public_synthetic',authorized_task='Explain public fixture'); m=fixture(); m[5]['content']='retain narrative '*30000
        self.assertEqual(e.compress(m,current_tokens=190000),m)
        self.assertEqual(e.fallback.calls,1)
    def test_private_historical_goal_never_exported(self):
        e=self.engine(); m=fixture(); m[1]['content']='private synthetic medical canary'
        spy=unittest.mock.Mock(); spy.score.return_value=ScoreResult({'g2':0}); e.scorer=spy
        e.compress(m)
        self.assertEqual(spy.score.call_count,0) # no explicit session/task envelope
    def test_metadata_and_null_wrapper(self):
        e=self.engine(session_scope='public_synthetic',authorized_task='Explain public topic')
        m=fixture(); m[2]['content']=None; m[3]['_db_id']=123
        spy=unittest.mock.Mock(); spy.score.return_value=ScoreResult({'g2':0}); e.scorer=spy
        out=e.compress(m)
        self.assertEqual(e.last_metrics['outcome'],'pruned')
        args=spy.score.call_args.args
        self.assertEqual(args[1],'Explain public topic'); self.assertNotIn('_db_id',json.dumps(args[0]))
        self.assertEqual(out[3]['_db_id'],123)
    def test_other_session_update_during_slow_fallback(self):
        entered=threading.Event(); release=threading.Event(); done=threading.Event()
        e=self.engine(mode='off'); other=self.engine()
        class Slow(Fallback):
            def compress(self,messages,**kw): entered.set(); release.wait(2); return messages
        e.fallback=Slow()
        t=threading.Thread(target=e.compress,args=(fixture(),)); t.start()
        try:
            self.assertTrue(entered.wait(1))
            u=threading.Thread(target=lambda:(other.update_from_response({'prompt_tokens':7}),done.set())); u.start()
            self.assertTrue(done.wait(.1))
        finally: release.set(); t.join(2); u.join(2)
    def test_request_count_survives_restart(self):
        path=Path(self.temp.name)/'b'
        b=Budget(path,total_limit=1,daily_limit=1,max_requests=1)
        i=b.reserve(); b.settle(i,.001)
        with self.assertRaises(RuntimeError): Budget(path,total_limit=1,daily_limit=1,max_requests=1).reserve()
    def test_late_measured_cost_settled(self):
        b=Budget(Path(self.temp.name)/'b',total_limit=1,daily_limit=1,max_requests=2)
        def transport(*args):
            time.sleep(.02)
            return json.dumps({'provider':'TypeSafe','model':'typesafe/jev-1.13','answers':{'g1':{'type':'noul','noul':0}},'usage':{'cost':.001,'input_tokens':10,'output_tokens':1}}).encode()
        s=DecisionsScorer(budget=b,key_resolver=lambda:'test',transport=transport,egress_authorized=True,spend_policy='bounded_local_trial',session_scope='public_synthetic')
        with self.assertRaises(RuntimeError): s.score([{'id':'g1','messages':[]}],'public',deadline=time.monotonic()+.01)
        with sqlite3.connect(b.path) as c: self.assertEqual(c.execute('SELECT actual,settled FROM spend').fetchone(),(.001,1))

if __name__=='__main__': unittest.main()
