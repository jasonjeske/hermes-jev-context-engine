"""Native settings mapping; no core patches or credentials."""
from types import SimpleNamespace


def constructor_kwargs(config, *, model, provider='', api_mode='', max_tokens=None):
    # Reuse native parsing (including threshold overrides), not raw YAML approximations.
    from agent.agent_init import _parse_compression_config, _compressor_max_tokens
    agent=SimpleNamespace(model=model,provider=provider,api_mode=api_mode,base_url='',
                          max_tokens=max_tokens if max_tokens is not None else config.get('max_tokens'))
    cs=_parse_compression_config(agent,config)
    return dict(model=model,provider=provider,api_mode=api_mode,quiet_mode=True,
                threshold_percent=cs.threshold,protect_first_n=cs.protect_first,
                protect_last_n=cs.protect_last,summary_target_ratio=cs.target_ratio,
                summary_model_override=None,abort_on_summary_failure=cs.abort_on_summary_failure,
                max_tokens=_compressor_max_tokens(agent),model_thresholds=cs.model_thresholds,
                threshold_tokens_cap=cs.threshold_tokens,proactive_prune_tokens=cs.proactive_prune_tokens,
                proactive_prune_min_result_chars=cs.proactive_prune_min_chars,
                proactive_prune_min_reclaim_tokens=cs.proactive_prune_min_reclaim,
                min_tail_user_messages=cs.min_tail_users,tail_mode=cs.tail_mode,
                custom_providers=config.get('custom_providers'))
