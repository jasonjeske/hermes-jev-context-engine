import copy
import json
import math
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from plugin.engine import JevContextEngine,Settings,ScoreResult,groups_in,MARKER
from plugin.decisions import DecisionsScorer,Budget,ENDPOINT
from plugin.storage import Archive,Metrics


def fixture():
    return [ {'role':'system','content':'SYSTEM unchanged'},
      {'role':'user','content':'Find public documentation'},
      {'role':'assistant','content':'Searching old topic','tool_calls':[
       {'id':'a','type':'function','function':{'name':'web_search','arguments':'{}'}},
       {'id':'b','type':'function','function':{'name':'web_search','arguments':'{}'}}]},
      {'role':'tool','tool_call_id':'a','content':'obsolete public result '*100},
      {'role':'tool','tool_call_id':'b','content':'redundant public result '*100},
      {'role':'assistant','content':'Topic completed'},
      {'role':'user','content':'Now explain something unrelated'},
      {'role':'assistant','content':'Recent response'} ]

class Scorer:
    def __init__(self,value=0): self.value=value; self.calls=0
    def score(self,groups,goal,*,deadline):
        self.calls+=1
        return ScoreResult({g['id']:self.value for g in groups})

class Fallback:
    def __init__(self): self.calls=0
    def compress(self,messages,**kwargs): self.calls+=1; return messages
    def on_session_reset(self): pass
    def update_from_response(self,usage): pass

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.archive=Archive(Path(self.tmp.name)/'archives')
    def engine(self,**settings):
        opts=dict(mode='active',protect_first_n=1,protect_last_n=1,egress_authorized=True,session_scope='public_synthetic',authorized_task='Explain public fixture')
        opts.update(settings)
        return JevContextEngine(settings=Settings(**opts),scorer=Scorer(),fallback=Fallback(),archive=self.archive)
    def test_preserves_text_structure_original_and_archive(self):
        m=fixture(); original=copy.deepcopy(m); e=self.engine(); out=e.compress(m)
        self.assertEqual(m,original); self.assertEqual(len(out),len(m)); groups_in(out)
        for i in (0,1,2,5,6,7): self.assertEqual(out[i],m[i])
        for i in (3,4): self.assertTrue(out[i]['content'].startswith(MARKER))
        saved=list((Path(self.tmp.name)/'archives').glob('*.json'))
        self.assertEqual(json.loads(saved[0].read_text()),m)
        self.assertEqual(saved[0].stat().st_mode&0o777,0o600)
        self.assertEqual(e.last_metrics['groups_pruned'],1)
    def test_default_native_tail(self):
        e=JevContextEngine(scorer=Scorer(),fallback=Fallback()); m=fixture()
        self.assertEqual(e.protect_last_n,40); self.assertEqual(e.compress(m),m); self.assertEqual(e.scorer.calls,0)
    def test_group_boundary_protection(self):
        e=self.engine(protect_first_n=2); m=fixture(); self.assertEqual(e.compress(m),m)
        self.assertEqual(e.scorer.calls,0)
    def test_error_evidence_decision_protection(self):
        for content in ('ERROR bad','decision: retain','required evidence','sha256 abc','Traceback'):
            with self.subTest(content=content):
                m=fixture(); m[3]['content']+=content; e=self.engine()
                self.assertEqual(e.compress(m),m); self.assertEqual(e.scorer.calls,0)
    def test_explicit_protection(self):
        for key in ('jev_protected','required_evidence','is_error'):
            m=fixture(); m[4][key]=True; e=self.engine(); self.assertEqual(e.compress(m),m)
    def test_recent_latest_user(self):
        m=fixture(); m.insert(2,{'role':'user','content':'Current goal'}); m.pop(7)
        e=self.engine(); self.assertEqual(e.compress(m),m)
    def test_malformed_histories_never_score_or_fallback(self):
        variants=[]
        m=fixture(); del m[4]; variants.append(m)
        m=fixture(); m[4]['tool_call_id']='a'; variants.append(m)
        m=fixture(); m[2]['tool_calls'][1]['id']='a'; variants.append(m)
        variants += [[{'role':'tool','tool_call_id':'x','content':'x'}],[None]]
        for m in variants:
            e=self.engine(); self.assertEqual(e.compress(m),m); self.assertEqual(e.scorer.calls,0); self.assertEqual(e.fallback.calls,0)
    def test_multimodal_protected(self):
        m=fixture(); m[3]['content']=[{'type':'image_url','image_url':{'url':'https://invalid/'}}]
        e=self.engine(); self.assertEqual(e.compress(m),m); self.assertEqual(e.scorer.calls,0)
    def test_huge_input(self):
        e=self.engine(max_input_bytes=100); self.assertEqual(e.compress(fixture()),fixture()); self.assertEqual(e.scorer.calls,0)
    def test_invalid_scores_fallback(self):
        for score in (float('nan'),float('inf'),-1,1.1,True,'0'):
            e=self.engine(); e.scorer=Scorer(score); self.assertEqual(e.compress(fixture()),fixture()); self.assertEqual(e.fallback.calls,1)
    def test_id_set_and_exception(self):
        e=self.engine()
        for result in (None,ScoreResult({'wrong':0}),ScoreResult({})):
            e.scorer=unittest.mock.Mock(); e.scorer.score.return_value=result
            self.assertEqual(e.compress(fixture()),fixture())
        e.scorer.score.side_effect=RuntimeError('DO NOT LOG'); e.compress(fixture())
        self.assertNotIn('DO NOT LOG',json.dumps(e.last_metrics))
    def test_no_reduction(self):
        e=self.engine(); e.scorer=Scorer(1); self.assertEqual(e.compress(fixture()),fixture()); self.assertEqual(e.fallback.calls,1)
    def test_archive_failure(self):
        e=self.engine(); e.archive=None; self.assertEqual(e.compress(fixture()),fixture()); self.assertEqual(e.last_metrics['reason'],'archive_failed')
    def test_shadow_native_authoritative(self):
        records=[]; e=self.engine(mode='shadow'); e.metrics=records.append
        self.assertEqual(e.compress(fixture()),fixture()); self.assertEqual(e.fallback.calls,1)
        self.assertTrue(records[-1]['shadow']); self.assertFalse((Path(self.tmp.name)/'archives').exists())
    def test_privacy_gate_and_off(self):
        for settings in ({'egress_authorized':False},{'mode':'off'}):
            e=self.engine(**settings); self.assertEqual(e.compress(fixture()),fixture()); self.assertEqual(e.scorer.calls,0)
    def test_deadline_discards_late_score(self):
        e=self.engine(timeout_seconds=.05)
        class Late:
            def score(self,groups,goal,*,deadline):
                time.sleep(.06); return ScoreResult({g['id']:0 for g in groups})
        e.scorer=Late(); self.assertEqual(e.compress(fixture()),fixture()); self.assertEqual(e.last_metrics['reason'],'deadline')
    def test_concurrent_admission_no_queue(self):
        entered=threading.Event(); release=threading.Event(); e=self.engine()
        class Slow:
            def score(self,groups,goal,*,deadline):
                entered.set(); release.wait(2); return ScoreResult({g['id']:0 for g in groups})
        e.scorer=Slow(); thread=threading.Thread(target=e.compress,args=(fixture(),)); thread.start()
        self.assertTrue(entered.wait(1)); self.assertEqual(e.compress(fixture()),fixture()); release.set(); thread.join(2); self.assertFalse(thread.is_alive())
    def test_deepcopy_and_session_isolation(self):
        e=self.engine(); other=copy.deepcopy(e); e.update_from_response({'prompt_tokens':33}); self.assertEqual(other.last_prompt_tokens,0)
        e.on_session_reset(); self.assertEqual(e.last_prompt_tokens,0)
    def test_settings_reject_unsafe(self):
        for values in ({'mode':'apply'},{'timeout_seconds':math.nan},{'protect_last_n':0},{'egress_authorized':'false'}):
            with self.assertRaises(ValueError): Settings(**values)
    def test_metrics_no_content(self):
        p=Path(self.tmp.name)/'metrics.jsonl'; e=self.engine(); e.metrics=Metrics(p); e.compress(fixture())
        text=p.read_text(); self.assertNotIn('public result',text); self.assertNotIn('archive=',text)
        with self.assertRaises(ValueError): e.metrics({'content':'oops'})

class DecisionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.budget=Budget(Path(self.tmp.name)/'b.sqlite',total_limit=.04,daily_limit=.04,per_call_limit=.02,max_requests=10)
        self.payload=None
    def transport(self,url,headers,body,deadline):
        self.assertEqual(url,ENDPOINT); self.payload=json.loads(body)
        return json.dumps({'model':'typesafe/jev-1.13-20260917','provider':'TypeSafe','answers':{'g1':{'type':'noul','noul':.05}},'usage':{'input_tokens':30,'output_tokens':2,'cost':.001}}).encode()
    def scorer(self,**kwargs):
        values=dict(budget=self.budget,key_resolver=lambda:'test-placeholder',transport=self.transport,egress_authorized=True,spend_policy='bounded_local_trial',session_scope='public_synthetic')
        values.update(kwargs); return DecisionsScorer(**values)
    def score(self,scorer): return scorer.score([{'id':'g1','messages':[]}],'public fixture',deadline=time.monotonic()+1)
    def test_wire_contract_privacy_and_measured_cost(self):
        r=self.score(self.scorer()); self.assertEqual(r.cost_usd,.001)
        self.assertEqual(self.payload['provider'],{'zdr':True,'data_collection':'deny','allow_fallbacks':False,'require_parameters':True})
        self.assertNotIn('messages',self.payload); self.assertNotIn('session_id',self.payload)
    def test_missing_key_no_reservation(self):
        with self.assertRaises(RuntimeError): self.score(self.scorer(key_resolver=lambda:None))
        self.assertFalse(Path(self.budget.path).exists())
    def test_privacy_and_hard_budget_gates(self):
        for kw in ({'egress_authorized':False},{'spend_policy':'disabled'}):
            with self.assertRaises(RuntimeError): self.score(self.scorer(**kw))
    def test_secret_refusal(self):
        with patch('agent.redact.redact_sensitive_text',return_value='[REDACTED]'):
            with self.assertRaises(RuntimeError): self.score(self.scorer())
        self.assertFalse(Path(self.budget.path).exists())
    def test_persistent_unknown_reservation(self):
        def fail(*args): raise TimeoutError()
        with self.assertRaises(TimeoutError): self.score(self.scorer(transport=fail))
        fresh=Budget(self.budget.path,total_limit=2,daily_limit=2)
        with self.assertRaises(RuntimeError): fresh.reserve()
    def test_total_daily_and_per_call_budget(self):
        for total,daily in ((0,1),(1,0),(.01,1),(1,.01)):
            b=Budget(Path(self.tmp.name)/f'{total}-{daily}.sqlite',total_limit=total,daily_limit=daily)
            with self.assertRaises(RuntimeError): b.reserve()
    def test_malformed_and_route_refusal(self):
        for mutate in (lambda d:d.update(provider='Other'),lambda d:d.update(answers={}),lambda d:d['usage'].pop('cost'),lambda d:d['answers']['g1'].update(noul=True)):
            with self.subTest(mutate=mutate):
                b=Budget(Path(self.tmp.name)/(str(time.monotonic_ns())+'.sqlite'),total_limit=1,daily_limit=1,max_requests=10)
                def bad(*args):
                    d=json.loads(self.transport(*args)); mutate(d); return json.dumps(d).encode()
                with self.assertRaises(RuntimeError): self.score(self.scorer(budget=b,transport=bad))

if __name__=='__main__': unittest.main()
