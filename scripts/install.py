#!/usr/bin/env python3
"""Profile-scoped Jev installer. Every mutation requires --apply."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import sys
import uuid
import yaml

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
NAME = 'tao-jev'


def safe(path):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('symlink refused')


def read(path):
    safe(path)
    return path.read_bytes() if path.exists() else None


def digest(data):
    return hashlib.sha256(data or b'').hexdigest()


def private_write(path, data):
    safe(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = path.with_name('.'+path.name+'.'+uuid.uuid4().hex)
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists(): temp.unlink()


def sources():
    out = {}
    for folder, target in [('plugin', 'plugins/'+NAME), ('skill/jev-status', 'skills/jev-status')]:
        base = ROOT/folder
        for p in sorted(base.rglob('*')):
            safe(p)
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc':
                out[str(Path(target)/p.relative_to(base))] = p.read_bytes()
    if not out: raise ValueError('package files missing')
    return out


def host_name():
    value = platform.node().strip().rstrip('.').lower()
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', value):
        raise ValueError('nonempty normalized host required')
    return value


def settings(home):
    return dict(mode='off', egress_authorized=False, session_scope='disabled',
                spend_policy='disabled', target_host=host_name(), target_home=str(home),
                eligible_tools=['web_search'], tool_policy='explicit_public_session_tools',
                task_source='latest_user', employer_data_excluded=False, secrets_excluded=False,
                total_limit_usd=0.0, daily_limit_usd=0.0, per_call_limit_usd=.02, max_requests=0)


def validate_egress(args):
    limits = (args.total_usd, args.daily_usd, args.per_call_usd)
    if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in limits):
        raise ValueError('positive finite total/daily/per-call limits required')
    if not .02 <= args.per_call_usd <= args.daily_usd <= args.total_usd:
        raise ValueError('require .02 <= per-call <= daily <= total')
    if args.max_requests is None or args.max_requests <= 0 or args.scope is None:
        raise ValueError('explicit scope and positive request count required')
    if not args.exclude_employer_and_secrets:
        raise ValueError('explicit employer/secrets exclusion required')


def execute(args):
    if args.native_source:
        source = args.native_source.absolute()
        if not (source/'hermes_constants.py').is_file(): raise ValueError('native source unavailable')
        sys.path.insert(0, str(source))
    from hermes_constants import get_hermes_home
    home = Path(get_hermes_home()).absolute()
    safe(home)
    cfgpath = home/'config.yaml'
    raw = read(cfgpath)
    if raw and len(raw) > 2_000_000: raise ValueError('config too large')
    if args.expect_config_sha256 and digest(raw) != args.expect_config_sha256:
        raise ValueError('config changed since reviewed plan')
    cfg = yaml.safe_load(raw) if raw else {}
    if not isinstance(cfg, dict): raise ValueError('config must be a mapping')
    original = copy.deepcopy(cfg)
    state = home/'state'/NAME
    manifest_path = state/'installation.json'
    manifest_raw = read(manifest_path)
    manifest = json.loads(manifest_raw) if manifest_raw else None
    if manifest and manifest.get('home') != str(home): raise ValueError('foreign installation manifest')
    payload = sources()
    for rel in payload: safe(home/rel)
    plugins = cfg.setdefault('plugins', {})
    if not isinstance(plugins, dict): raise ValueError('plugins must be a mapping')
    entries = plugins.setdefault('entries', {})
    if not isinstance(entries, dict): raise ValueError('entries must be a mapping')
    context = cfg.setdefault('context', {})
    if not isinstance(context, dict): raise ValueError('context must be a mapping')
    enabled = plugins.get('enabled')
    disabled = plugins.get('disabled', [])
    for value in (enabled, disabled):
        if value is not None and (not isinstance(value, list) or any(not isinstance(x, str) for x in value)):
            raise ValueError('plugin lists malformed')
    installed = bool(manifest and manifest.get('installed'))
    if installed:
        if entries.get(NAME) != manifest['entry']: raise ValueError('plugin settings edited; refusing overwrite')
        for rel, sha in manifest['files'].items():
            data = read(home/rel)
            if data is None or digest(data) != sha: raise ValueError('installed file edited or missing; refusing overwrite')
    elif args.command == 'install':
        if NAME in entries: raise ValueError('existing plugin config conflict')
        for rel in ('plugins/'+NAME, 'skills/jev-status'):
            safe(home/rel)
            if (home/rel).exists(): raise ValueError('existing installation conflict')
    elif args.command in ('stock', 'remove'):
        print(json.dumps({'action': args.command, 'changed': False, 'installed': False})); return
    else:
        raise ValueError('install first')
    added_enabled = manifest.get('added_enabled', False) if manifest else False
    if args.command == 'install':
        if NAME in disabled: raise ValueError('plugin explicitly disabled; resolve deliberately first')
        if not installed:
            entries[NAME] = {'enabled': True, 'settings': settings(home)}
            if enabled is None:
                enabled = []
                plugins['enabled'] = enabled
            if NAME not in enabled:
                enabled.append(NAME); added_enabled = True
        elif any(digest(data) != manifest['files'].get(rel) for rel, data in payload.items()):
            raise ValueError('package differs; stock/remove before installing another version')
    elif args.command == 'activate':
        if not args.opt_in_active: raise ValueError('--opt-in-active required')
        if context.get('engine', 'compressor') not in ('compressor', NAME):
            raise ValueError('another context engine selected')
        entries[NAME]['settings']['mode'] = 'active'
        context['engine'] = NAME
    elif args.command == 'authorize-egress':
        if not args.opt_in_egress: raise ValueError('--opt-in-egress required')
        validate_egress(args)
        s = entries[NAME]['settings']
        s.update(egress_authorized=True, spend_policy='bounded_local_trial', session_scope=args.scope,
                 tool_policy='public_search' if args.scope == 'personal_pilot' else 'explicit_public_session_tools',
                 employer_data_excluded=True, secrets_excluded=True, target_host=host_name(), target_home=str(home),
                 total_limit_usd=args.total_usd, daily_limit_usd=args.daily_usd,
                 per_call_limit_usd=args.per_call_usd, max_requests=args.max_requests)
    elif args.command in ('stock', 'remove'):
        if context.get('engine') == NAME: context['engine'] = 'compressor'
        s = entries[NAME]['settings']
        s.update(mode='off', egress_authorized=False, spend_policy='disabled')
        if args.command == 'remove':
            del entries[NAME]
            if added_enabled and enabled is not None and NAME in enabled: enabled.remove(NAME)
    # Do not invent empty sections for configurations we did not change.
    for section in ('context', 'plugins'):
        if not cfg.get(section) and section not in original: cfg.pop(section, None)
    changed = cfg != original or (args.command == 'install' and not installed) or args.command == 'remove'
    plan = {'action': args.command, 'home': str(home), 'apply': args.apply, 'changed': changed,
            'config_sha256': digest(raw), 'state_preserved': True}
    if not args.apply or not changed:
        print(json.dumps(plan)); return
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    safe(state)
    lock = state/'installer.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    os.close(fd)
    try:
        # Optimistic CAS plus installer lock: never replay a stale config snapshot.
        if read(cfgpath) != raw or read(manifest_path) != manifest_raw:
            raise ValueError('concurrent configuration/installation change')
        if raw is not None:
            private_write(state/'backups'/('config-'+uuid.uuid4().hex+'.yaml'), raw)
        if args.command == 'install' and not installed:
            for rel, data in payload.items():
                if (home/rel).exists(): raise ValueError('concurrent file conflict')
                private_write(home/rel, data)
        if read(cfgpath) != raw: raise ValueError('concurrent config change; files may be staged, selection unchanged')
        if cfg != original:
            private_write(cfgpath, yaml.safe_dump(cfg, sort_keys=False).encode())
        if args.command == 'remove':
            for rel, sha in manifest['files'].items():
                if digest(read(home/rel)) != sha: raise ValueError('concurrent installed-file edit')
            for rel in manifest['files']: (home/rel).unlink()
            for folder in (home/'plugins'/NAME, home/'skills/jev-status/scripts', home/'skills/jev-status'):
                try: folder.rmdir()
                except OSError: pass  # Unowned additions remain untouched.
        record = {'schema': 1, 'home': str(home), 'installed': args.command != 'remove',
                  'entry': entries.get(NAME), 'added_enabled': added_enabled,
                  'files': {rel: digest(data) for rel, data in payload.items()}}
        private_write(manifest_path, json.dumps(record, indent=2).encode())
        if yaml.safe_load(read(cfgpath)) != cfg: raise ValueError('config readback mismatch')
        print(json.dumps(plan))
    finally:
        lock.unlink()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command', choices=['install', 'activate', 'authorize-egress', 'stock', 'remove'])
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--native-source', type=Path, help='Trusted installed Hermes source, if not already importable')
    ap.add_argument('--expect-config-sha256', help='Require the dry-run config digest before applying')
    ap.add_argument('--opt-in-active', action='store_true')
    ap.add_argument('--opt-in-egress', action='store_true')
    ap.add_argument('--scope', choices=['public_synthetic', 'personal_pilot'])
    ap.add_argument('--exclude-employer-and-secrets', action='store_true')
    ap.add_argument('--total-usd', type=float)
    ap.add_argument('--daily-usd', type=float)
    ap.add_argument('--per-call-usd', type=float)
    ap.add_argument('--max-requests', type=int)
    args = ap.parse_args(argv)
    try: execute(args)
    except Exception as exc:
        # YAML exceptions may contain secrets. Never print config or exception bodies.
        ap.exit(2, 'Refused ('+type(exc).__name__+'). Check conflicts, profile, opt-ins and finite limits.\n')


if __name__ == '__main__': main()
