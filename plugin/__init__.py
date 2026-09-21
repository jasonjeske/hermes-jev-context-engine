"""Native plugin. Registration performs no inference or credential lookup."""
from dataclasses import fields
import platform
import re
from pathlib import Path
from .engine import JevContextEngine, Settings
from .decisions import DecisionsScorer, Budget
from .storage import Archive, Metrics


def normalized_host(value):
    if not isinstance(value, str):
        return ''
    value = value.strip().rstrip('.').lower()
    return value if re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', value) else ''


def register(ctx):
    from hermes_cli.config import load_config_readonly
    from hermes_constants import get_hermes_home
    cfg = load_config_readonly() or {}
    native = cfg.get('compression', {})
    defaults = Settings()
    values = {f.name: ctx.get_config(f.name, getattr(defaults, f.name)) for f in fields(Settings)}
    for field, key in [('protect_first_n', 'protect_first_n'), ('protect_last_n', 'protect_last_n'),
                       ('threshold_percent', 'threshold'), ('summary_target_ratio', 'target_ratio')]:
        values[field] = ctx.get_config(field, native.get(key, getattr(defaults, field)))
    home = Path(get_hermes_home()).absolute()
    actual = normalized_host(platform.node())
    target = normalized_host(ctx.get_config('target_host', ''))
    profile_ok = ctx.get_config('target_home', '') == str(home)
    values['egress_authorized'] = values['egress_authorized'] is True and bool(actual) and target == actual and profile_ok
    settings = Settings(**values)
    # State can never be redirected into another profile by a copied config.
    state = home/'state'/'tao-jev'
    configured = ctx.get_config('state_dir', str(state))
    if configured != str(state) or any(p.is_symlink() for p in (state, *state.parents)):
        raise ValueError('state must be profile-bound and free of symlinks')
    budget = Budget(state/'budget.sqlite3', total_limit=ctx.get_config('total_limit_usd', 0.0),
                    daily_limit=ctx.get_config('daily_limit_usd', 0.0),
                    per_call_limit=ctx.get_config('per_call_limit_usd', .02),
                    max_requests=ctx.get_config('max_requests', 0))
    scorer = DecisionsScorer(budget=budget, egress_authorized=settings.egress_authorized,
                            spend_policy=ctx.get_config('spend_policy', 'disabled'),
                            session_scope=settings.session_scope,
                            employer_data_excluded=settings.employer_data_excluded,
                            secrets_excluded=settings.secrets_excluded)
    ctx.register_context_engine(JevContextEngine(settings=settings, scorer=scorer,
        native_config={k: cfg[k] for k in ('compression', 'max_tokens', 'custom_providers') if k in cfg},
        archive=Archive(state/'archives'), metrics=Metrics(state/'metrics.jsonl')))
