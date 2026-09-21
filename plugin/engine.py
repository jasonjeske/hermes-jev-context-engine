"""Conservative boundary-only Jev engine. No inference at import/registration."""
from __future__ import annotations
import copy
import json
import math
import re
import threading
import time
from dataclasses import dataclass
from typing import Optional
from agent.context_compressor import ContextCompressor
from agent.auxiliary_client import AuxiliaryExplicitCancellation
from agent.model_metadata import estimate_messages_tokens_rough
from .policy import PERSONAL_TOOLS, excluded_text, scope_authorized

# Module lock is deliberately not held in the deepcopy-able engine prototype.
_DECISIONS_ADMISSION = threading.Lock()
MARKER = '[TAO_JEV_PRUNED: original available in local archive]'
PROTECTED = re.compile(r'error|exception|traceback|fail|decision|evidence|must.keep|do.not.remove|citation|sha256|checksum|commit|diff|assert|exit_code\s*["\x27]?\s*[:=]\s*[1-9]', re.I)

@dataclass(frozen=True)
class Settings:
    mode: str = 'shadow'
    protect_first_n: int = 3
    protect_last_n: int = 40
    threshold_percent: float = .7
    summary_target_ratio: float = .35
    max_groups: int = 8
    max_input_bytes: int = 1_000_000
    min_result_chars: int = 800
    max_keep_probability: float = .10
    min_reduction_chars: int = 400
    timeout_seconds: float = 8.0
    egress_authorized: bool = False
    session_scope: str = 'disabled'
    employer_data_excluded: bool = False
    secrets_excluded: bool = False
    authorized_task: str = ''
    # Latest-user extraction is opt-in, not a declaration that a session is public.
    task_source: str = 'authorized_task'
    min_reduction_ratio: float = .15
    runway_ratio: float = .90
    # Non-default tool sets require deliberate public-session policy, not fixture tuning.
    tool_policy: str = 'public_search'
    # Only this explicit tool allowlist may be considered. Never assume tools recoverable.
    eligible_tools: tuple = ('web_search', 'search_files')

    def __post_init__(self):
        if self.session_scope not in ('disabled','public_synthetic','personal_pilot') or not isinstance(self.authorized_task,str) or len(self.authorized_task.encode())>2048:
            raise ValueError('invalid authorized session/task')
        if any(type(x) is not bool for x in (self.employer_data_excluded, self.secrets_excluded)):
            raise ValueError('invalid exclusion declaration')
        if self.session_scope=='personal_pilot' and self.tool_policy!='public_search':
            raise ValueError('personal pilot cannot expand tool policy')
        if self.task_source not in ('authorized_task','latest_user'):
            raise ValueError('invalid task source')
        if not .1 <= self.min_reduction_ratio <= .9 or not .5 <= self.runway_ratio <= .95:
            raise ValueError('invalid runway bounds')
        if (tuple(self.eligible_tools)!=('web_search','search_files')
                and not (self.session_scope=='personal_pilot' and tuple(self.eligible_tools)==('web_search',))
                and self.tool_policy!='explicit_public_session_tools'):
            raise ValueError('custom tools require deliberate public-session policy')
        if self.mode not in ('off', 'shadow', 'active'):
            raise ValueError('invalid mode')
        for name in ('protect_first_n','protect_last_n','max_groups','max_input_bytes','min_result_chars','min_reduction_chars'):
            x = getattr(self, name)
            if type(x) is not int or x < 0:
                raise ValueError('invalid bound')
        if self.protect_last_n < 1 or not 1 <= self.max_groups <= 32:
            raise ValueError('invalid preservation/group bound')
        for name in ('threshold_percent','summary_target_ratio','max_keep_probability','timeout_seconds'):
            x = getattr(self, name)
            if type(x) not in (int,float) or not math.isfinite(x):
                raise ValueError('invalid numeric setting')
        if not 0 < self.threshold_percent < 1 or not 0 < self.summary_target_ratio < 1 or not 0 <= self.max_keep_probability <= .2 or not .05 <= self.timeout_seconds <= 30:
            raise ValueError('invalid range')
        if type(self.egress_authorized) is not bool or not isinstance(self.eligible_tools, (list, tuple)) or any(not isinstance(x,str) for x in self.eligible_tools):
            raise ValueError('invalid settings')

@dataclass(frozen=True)
class ScoreResult:
    scores: dict
    cost_usd: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


def groups_in(messages):
    """Strict contiguous OpenAI tool groups; fail closed on unsupported structures."""
    if not isinstance(messages,list) or any(not isinstance(m,dict) for m in messages):
        raise ValueError('invalid messages')
    groups, seen, i = [], set(), 0
    while i < len(messages):
        m = messages[i]
        if m.get('role') not in ('system','developer','user','assistant','tool') or 'function_call' in m:
            raise ValueError('unsupported structure')
        if m.get('role') == 'tool':
            raise ValueError('orphan result')
        calls = m.get('tool_calls')
        if calls:
            if m['role'] != 'assistant' or not isinstance(calls,list):
                raise ValueError('invalid calls')
            ids, names = [], []
            for c in calls:
                if not isinstance(c,dict) or c.get('type') != 'function' or not isinstance(c.get('id'),str) or not c['id'] or c['id'] in seen:
                    raise ValueError('invalid call')
                f=c.get('function',{})
                if not isinstance(f,dict) or not isinstance(f.get('name'),str) or not isinstance(f.get('arguments'),str):
                    raise ValueError('invalid function')
                seen.add(c['id']); ids.append(c['id']); names.append(f['name'])
            end=i+1+len(ids)
            results=messages[i+1:end]
            if len(results)!=len(ids) or any(r.get('role')!='tool' for r in results) or set(r.get('tool_call_id') for r in results)!=set(ids):
                raise ValueError('incomplete group')
            groups.append({'id':f'g{i}', 'start':i, 'end':end, 'names':names, 'messages':messages[i:end]})
            i=end
        else:
            i+=1
    return groups


class JevContextEngine(ContextCompressor):
    def __init__(self, *, settings=None, scorer=None, fallback=None, archive=None, metrics=None,
                 native_kwargs=None, native_config=None):
        self.settings=settings or Settings()
        kwargs=dict(model='', config_context_length=200000, quiet_mode=True,
                    threshold_percent=self.settings.threshold_percent,
                    protect_first_n=self.settings.protect_first_n,
                    protect_last_n=self.settings.protect_last_n,
                    summary_target_ratio=self.settings.summary_target_ratio)
        kwargs.update(native_kwargs or {})
        super().__init__(**kwargs)
        # A supplied native compressor is a settings/state snapshot, never a second authority.
        if isinstance(fallback, ContextCompressor):
            self.__dict__.update(copy.deepcopy({k:v for k,v in fallback.__dict__.items() if k not in ('_session_db','_session_id')}))
            fallback=None
        self.scorer,self.archive,self.metrics=scorer,archive,metrics
        self._test_fallback=fallback
        self._native_config=copy.deepcopy(native_config)
        self._native_initialized=native_config is None
        self.last_metrics={}
        self._attempt_lock=threading.Lock()
        self._jev_epoch=0

    @property
    def name(self): return 'tao-jev'

    @property
    def fallback(self):
        # Compatibility view; native state is this object, not a delegated wrapper.
        return self._test_fallback if self._test_fallback is not None else self

    @fallback.setter
    def fallback(self, value): self._test_fallback=value

    def __deepcopy__(self, memo):
        clone=type(self).__new__(type(self)); memo[id(self)]=clone
        for key,value in self.__dict__.items():
            if key=='_attempt_lock': continue
            # DB bindings are host resources, not prototype/session-copy state.
            if key=='_session_db': value=None
            if key=='_session_id': value=''
            setattr(clone,key,copy.deepcopy(value,memo))
        clone._attempt_lock=threading.Lock()
        return clone

    def update_model(self, model, context_length, base_url='', api_key='', provider='', api_mode='', max_tokens=None):
        self._jev_epoch+=1
        if not self._native_initialized:
            from .native_settings import constructor_kwargs
            kwargs=constructor_kwargs(self._native_config, model=model, provider=provider,
                                      api_mode=api_mode, max_tokens=max_tokens)
            ContextCompressor.__init__(self, **kwargs, base_url=base_url, api_key=api_key,
                                      config_context_length=context_length)
            self._native_initialized=True
        super().update_model(model,context_length,base_url=base_url,api_key=api_key,
                             provider=provider,api_mode=api_mode,max_tokens=max_tokens)

    def update_from_response(self, usage):
        self._jev_epoch+=1
        super().update_from_response(usage)

    def on_session_reset(self):
        self._jev_epoch+=1
        super().on_session_reset()
        self.last_metrics={}

    def _emit(self, record):
        self.last_metrics=dict(record)
        if self.metrics:
            try: self.metrics(dict(record))
            except Exception: pass  # telemetry must not break compaction

    def compress(self, messages, current_tokens=None, focus_topic=None, force=False, memory_context='', bypass_cooldown=False):
        if not self._attempt_lock.acquire(blocking=False):
            self._emit({'schema':1,'mode':self.settings.mode,'outcome':'retained','reason':'busy'})
            return messages
        try:
            return self._compress(messages,current_tokens,focus_topic,force,memory_context,bypass_cooldown)
        finally:
            self._attempt_lock.release()

    def _compress(self,messages,current_tokens,focus_topic,force,memory_context,bypass_cooldown):
        started=time.monotonic()
        epoch=self._jev_epoch
        cancelled=getattr(self,'_compression_cancelled_check',None)
        generation=getattr(self,'_compression_working_attempt_generation',None)
        def check_current():
            if self._jev_epoch!=epoch or (callable(cancelled) and cancelled()) or generation!=getattr(self,'_compression_working_attempt_generation',None):
                raise AuxiliaryExplicitCancellation()
        # The host reads these result flags BEFORE committing a candidate. Inherited
        # completion hooks alone do not initialize an overridden compress path.
        # Use native attempt setup (including force-only durable cooldown clearing),
        # but never native finalization: it rewrites media/replay/persistence fields.
        check_current()
        telemetry=self._begin_compress_attempt(current_tokens,force)
        record={'schema':1,'mode':self.settings.mode,'outcome':'retained','reason':'no_candidates',
                'groups_pruned':0,'candidate_groups':0,'candidate_bytes_saved':0,
                'cost_usd':None,'input_tokens':None,'output_tokens':None}
        def finish(out):
            check_current()
            record['elapsed_ms']=round((time.monotonic()-started)*1000,3)
            if out!=messages:
                self.last_prompt_tokens=-1
            self._emit(record)
            return out
        def native(reason):
            check_current()
            record['reason']=reason; record['outcome']='fallback'
            if self.fallback:
                try:
                    out=(self._test_fallback.compress if self._test_fallback is not None else super(JevContextEngine,self).compress)(copy.deepcopy(messages),current_tokens=current_tokens,
                        focus_topic=focus_topic,force=force,memory_context=memory_context,bypass_cooldown=bypass_cooldown)
                    if not out: raise ValueError('empty native result')
                    groups_in(out)
                    return finish(out)
                except AuxiliaryExplicitCancellation: raise
                except Exception: record['reason']='native_failed'
            record['outcome']='retained'
            return finish(messages)
        try:
            encoded=json.dumps(messages,ensure_ascii=False,allow_nan=False).encode()
            groups=groups_in(messages)
            if len(encoded)>self.settings.max_input_bytes:
                record['reason']='input_limit'; return finish(messages)
        except AuxiliaryExplicitCancellation: raise
        except Exception:
            # Invalid source must not be sent anywhere, including native summarization.
            record['reason']='invalid_structure'; return finish(messages)
        if self.settings.mode=='off': return native('off')
        non_system=[i for i,m in enumerate(messages) if m['role'] not in ('system','developer')]
        protected=set(non_system[:self.protect_first_n]+non_system[-self.protect_last_n:])
        # The latest user request and all following results are always protected.
        users=[i for i,m in enumerate(messages) if m['role']=='user']
        if users: protected.update(range(users[-1],len(messages)))
        candidates=[]
        for g in groups:
            if any(i in protected for i in range(g['start'],g['end'])): continue
            if any(n not in self.settings.eligible_tools for n in g['names']): continue
            if self.settings.session_scope=='personal_pilot' and any(n not in PERSONAL_TOOLS for n in g['names']): continue
            if g['messages'][0].get('content') is not None and not isinstance(g['messages'][0].get('content',''),str): continue
            if any(not isinstance(m.get('content',''),str) for m in g['messages'][1:]): continue
            allowed={'role','content','tool_calls','tool_call_id','name','jev_protected','required_evidence','is_error','_db_id','_db_persisted'}
            if any(set(m)-allowed for m in g['messages']): continue
            text=json.dumps(g['messages'],ensure_ascii=False)
            if PROTECTED.search(text) or MARKER in text: continue
            if any(m.get('jev_protected') or m.get('required_evidence') or m.get('is_error') for m in g['messages']): continue
            if sum(len(m.get('content','')) for m in g['messages'][1:])<self.settings.min_result_chars: continue
            candidates.append(g)
        candidates=candidates[:self.settings.max_groups]
        record['candidate_groups']=len(candidates)
        if not candidates: return native('no_candidates')
        if not self.settings.egress_authorized or not scope_authorized(self.settings.session_scope,
                self.settings.employer_data_excluded, self.settings.secrets_excluded):
            return native('privacy_not_authorized')
        # Derive from the native compress() transcript, not cached session attributes,
        # focus_topic, memory_context, system prompts or concatenated old user turns.
        # Do not silently use stale static text if the current request is unsupported.
        goal=self.settings.authorized_task
        if self.settings.task_source=='latest_user':
            latest=messages[users[-1]] if users else {}
            goal=latest.get('content')
            if set(latest)-{'role','content','_db_id','_db_persisted'}:
                return native('task_unavailable')
        if not isinstance(goal,str) or not goal.strip() or len(goal.encode())>2048:
            return native('task_unavailable')
        if excluded_text(goal): return native('excluded_data')
        if self.scorer is None: return native('scorer_unavailable')
        deadline=started+self.settings.timeout_seconds
        try:
            if not _DECISIONS_ADMISSION.acquire(blocking=False): return native('decisions_busy')
            try:
                wire=[{'id':g['id'],'messages':[{k:copy.deepcopy(v) for k,v in m.items() if k in ('role','content','tool_calls','tool_call_id','name')} for m in g['messages']]} for g in candidates]
                # Tool calls are projected too; provider/internal metadata never leaves.
                for g in wire:
                    for m in g['messages']:
                        if m.get('tool_calls'):
                            m['tool_calls']=[{'id':c['id'],'type':'function','function':{'name':c['function']['name'],'arguments':c['function']['arguments']}} for c in m['tool_calls']]
                if excluded_text(json.dumps(wire,ensure_ascii=False)):
                    raise ValueError('excluded payload')
                scored=self.scorer.score(wire,goal,deadline=deadline)
            finally: _DECISIONS_ADMISSION.release()
            check_current()
            if not isinstance(scored,ScoreResult) or set(scored.scores)!=set(g['id'] for g in candidates): raise ValueError()
            if any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in scored.scores.values()): raise ValueError()
            for key in ('cost_usd','input_tokens','output_tokens'):
                v=getattr(scored,key)
                if v is not None and (type(v) not in (int,float) or not math.isfinite(v) or v<0): raise ValueError()
                record[key]=v
            if time.monotonic()>deadline: return native('deadline')
        except AuxiliaryExplicitCancellation: raise
        except Exception:
            usage=getattr(self.scorer,'last_usage',{})
            if isinstance(usage,dict):
                for key in ('cost_usd','input_tokens','output_tokens'):
                    value=usage.get(key)
                    if type(value) in (int,float) and math.isfinite(value) and value>=0: record[key]=value
            return native('scorer_failed')
        out=copy.deepcopy(messages)
        selected=[g for g in candidates if scored.scores[g['id']]<=self.settings.max_keep_probability]
        for g in selected:
            for i in range(g['start']+1,g['end']): out[i]['content']=MARKER
        saved=len(encoded)-len(json.dumps(out,ensure_ascii=False).encode())
        record['candidate_bytes_saved']=max(0,saved)
        if not selected or saved<self.settings.min_reduction_chars: return native('insufficient_reduction')
        # Use native effective-message estimator, plus the observed request overhead.
        # Rough estimates are not provider token measurements; require material reduction
        # AND runway, then let inherited real-usage verdict adjudicate the committed result.
        projected=copy.deepcopy(out)
        for g in selected:
            for i in range(g['start']+1,g['end']): projected[i]['content']=MARKER+' archive='+('a'*97)+'.json'
        before=estimate_messages_tokens_rough(messages)
        after=estimate_messages_tokens_rough(projected)
        observed=max(current_tokens or 0, self.last_prompt_tokens or 0, before)
        overhead=max(0,observed-before)
        effective_after=overhead+after
        if before<=0 or before-after < max(100, before*self.settings.min_reduction_ratio) or effective_after>min(self.threshold_tokens,self.context_length-(self.max_tokens or 0))*self.settings.runway_ratio:
            return native('insufficient_runway')
        try: groups_in(out)
        except Exception: return native('invalid_candidate')
        if self.settings.mode=='shadow':
            record['shadow']=True
            return native('shadow_authoritative_native')
        check_current()
        try:
            ref=self.archive.save(messages) if self.archive else None
            if not isinstance(ref,str) or not re.fullmatch(r'[a-f0-9-]+\.json',ref): raise ValueError()
        except Exception: return native('archive_failed')
        for g in selected:
            for i in range(g['start']+1,g['end']): out[i]['content']=MARKER+' archive='+ref
        if len(encoded)-len(json.dumps(out,ensure_ascii=False).encode())<self.settings.min_reduction_chars:
            return native('insufficient_reduction')
        check_current()
        self.compression_count+=1
        # Only state covered by the host attempt snapshot is published here. Do
        # not reset micro-compaction cursors or treat Jev as a successful native
        # summary (it cannot certify recovery of the summary provider). The host
        # alone arms record_completed_compaction after its commit fence passes.
        self._last_compression_savings_pct=(before-estimate_messages_tokens_rough(out))/before*100
        self._last_compression_made_progress=True
        # Native telemetry is content-free and describes no summary/chunk call;
        # Decisions usage stays in plugin metrics, not fabricated aux telemetry.
        telemetry['fallback_used']=False
        record['outcome']='pruned'; record['reason']='selected'; record['groups_pruned']=len(selected)
        return finish(out)
