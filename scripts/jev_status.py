#!/usr/bin/env python3
"""Read-only Jev disk status. No plugin, config-loader, agent or API imports."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
import math
from pathlib import Path
import sqlite3
import sys

# Prevent import bytecode writes, including the native import-safe constants module.
sys.dont_write_bytecode = True
NAME = 'tao-jev'
NUMBERS = ('groups_pruned', 'candidate_groups', 'candidate_bytes_saved',
           'cost_usd', 'input_tokens', 'output_tokens', 'elapsed_ms')
LIMITS = ('total_limit_usd', 'daily_limit_usd', 'per_call_limit_usd', 'max_requests')
REASONS = frozenset(('busy', 'no_candidates', 'native_failed', 'input_limit',
    'invalid_structure', 'off', 'privacy_not_authorized', 'task_unavailable',
    'excluded_data', 'scorer_unavailable', 'decisions_busy', 'deadline',
    'scorer_failed', 'insufficient_reduction', 'insufficient_runway',
    'invalid_candidate', 'shadow_authoritative_native', 'archive_failed', 'selected'))
NOTES = [
    'Disk configuration only; current-process activation is unverified.',
    'Attempts are recorded compressor events, not all turns or confirmed API calls. Missing metrics do not mean no use.',
    'Pruned means plugin candidate output, not host commit. Candidate/pre-archive bytes exclude archive-marker overhead; not final bytes or token savings.',
    'Shadow-mode events and shadow candidates overlap fallback; do not add those counts together.',
    'Metrics cost is provider-reported Jev cost where present, not total task cost. Ledger actual may be untrusted/unsettled; reservations are not measured charges. Do not add metrics and ledger costs.',
    'Metrics schema 1 has no timestamps or before-size denominator: no 14-day attribution or reduction percentage. Compare saved JSON snapshots only for unchanged files/schema, allowing for truncation/rotation; quality and net benefit require separate evidence.',
    'Read-only best-effort snapshot, not an atomic cross-file view. No APIs, credentials, raw history, archives or memory were accessed.',
]


def number(value, integer=False):
    try:
        return type(value) in ((int,) if integer else (int, float)) and math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def safe_path(path):
    # Avoid following a telemetry/config symlink into another data source.
    return not any(p.is_symlink() for p in (path, *path.parents))


def file_state(path):
    try:
        if not safe_path(path):
            return 'unsafe_path'
        if not path.exists():
            return 'missing'
        return 'ok' if path.is_file() else 'malformed'
    except OSError:
        return 'unreadable'


def config_status(home):
    result = dict(status='unknown', installed=None, enabled=None, selected=None,
                  mode=None, session_scope=None, budget={k: None for k in LIMITS})
    target = home/'plugins'/NAME
    try:
        files = [file_state(target/f) for f in ('plugin.yaml', '__init__.py')]
        result['installation_status'] = 'present' if all(s == 'ok' for s in files) else ('missing' if 'missing' in files else 'unverified')
        result['installed'] = True if result['installation_status'] == 'present' else (False if result['installation_status'] == 'missing' else None)
    except OSError:
        result['installation_status'] = 'unreadable'
    path = home/'config.yaml'
    result['status'] = file_state(path)
    if result['status'] != 'ok':
        return result, None
    try:
        import yaml  # Safe parser only; native load_config can create backups/state.
        if path.stat().st_size > 2_000_000:
            raise ValueError('oversize')
        cfg = yaml.safe_load(path.read_text(encoding='utf-8'))
        if not isinstance(cfg, dict):
            raise ValueError('mapping required')
        plugins, context = cfg.get('plugins', {}), cfg.get('context', {})
        if not isinstance(plugins, dict) or not isinstance(context, dict):
            raise ValueError('invalid sections')
        entries = plugins.get('entries', {})
        entry = entries.get(NAME, {}) if isinstance(entries, dict) else None
        settings = entry.get('settings', {}) if isinstance(entry, dict) else None
        if not isinstance(settings, dict):
            raise ValueError('invalid settings')
        enabled, disabled = plugins.get('enabled'), plugins.get('disabled', [])
        if enabled is not None and (not isinstance(enabled, list) or any(not isinstance(x, str) for x in enabled)):
            raise ValueError('invalid enabled list')
        if not isinstance(disabled, list) or any(not isinstance(x, str) for x in disabled):
            raise ValueError('invalid disabled list')
        if 'enabled' in entry and type(entry['enabled']) is not bool:
            raise ValueError('invalid entry flag')
        if NAME in disabled or entry.get('enabled') is False:
            result['enabled'] = False
        elif enabled is not None:
            result['enabled'] = NAME in enabled
        # Missing values remain unknown: do not impersonate runtime defaults.
        engine = context.get('engine')
        if isinstance(engine, str):
            result['selected'] = engine == NAME
        for key, allowed in [('mode', ('off', 'shadow', 'active')),
                             ('session_scope', ('disabled', 'public_synthetic', 'personal_pilot'))]:
            value = settings.get(key)
            if isinstance(value, str) and value in allowed:
                result[key] = value
            elif key in settings:
                result['status'] = 'partial'
        for key in LIMITS:
            if number(settings.get(key), integer=key == 'max_requests'):
                result['budget'][key] = settings[key]
            elif key in settings:
                result['status'] = 'partial'
        for key in ('egress_authorized', 'employer_data_excluded', 'secrets_excluded'):
            result[key] = settings.get(key) if type(settings.get(key)) is bool else None
        result['spend_policy'] = settings.get('spend_policy') if settings.get('spend_policy') in ('disabled', 'bounded_local_trial') else None
        state = home/'state'/NAME
        configured = settings.get('state_dir')
        if configured is not None and configured != str(state):
            result['state_path_status'] = 'foreign_path_refused'
            return result, None
        if not safe_path(state):
            result['state_path_status'] = 'unsafe_path'
            return result, None
        result['state_path_status'] = 'profile_bound'
        return result, state
    except ImportError:
        result['status'] = 'parser_unavailable'
    except (ValueError, TypeError, UnicodeError, RecursionError):
        result['status'] = 'malformed'
    except OSError:
        result['status'] = 'unreadable'
    except Exception:
        # Parser messages can echo config lines containing credentials.
        result['status'] = 'malformed'
    return result, None


def metrics_status(path):
    result = dict(status='unknown', attempts=None, pruned=None, fallback=None,
                  retained=None, shadow=None, shadow_candidates=None, invalid_records=None, reasons={}, totals={})
    if path is None:
        return result
    result['status'] = file_state(path)
    if result['status'] != 'ok':
        return result
    count = 0
    invalid = 0
    counts = dict(pruned=0, fallback=0, retained=0, shadow=0, shadow_candidates=0)
    sums = {k: 0 for k in NUMBERS}
    known = {k: 0 for k in NUMBERS}
    try:
        before = path.stat()
        if before.st_size > 64_000_000:
            result['status'] = 'too_large'
            return result
        with path.open(encoding='utf-8') as stream:
            for line in stream:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    if (not isinstance(record, dict) or type(record.get('schema')) is not int or record['schema'] != 1
                            or record.get('outcome') not in ('pruned', 'retained', 'fallback')
                            or record.get('mode') not in ('active', 'off', 'shadow')):
                        raise ValueError('unsupported record')
                except (ValueError, TypeError):
                    invalid += 1
                    continue
                count += 1
                counts[record['outcome']] += 1
                counts['shadow'] += record['mode'] == 'shadow'
                counts['shadow_candidates'] += record.get('shadow') is True
                reason = record.get('reason')
                reason = reason if isinstance(reason, str) and reason in REASONS else 'unknown'
                result['reasons'][reason] = result['reasons'].get(reason, 0) + 1
                for key in NUMBERS:
                    if number(record.get(key), integer=key not in ('cost_usd', 'elapsed_ms')):
                        sums[key] += record[key]
                        known[key] += 1
        after = path.stat()
        result.update(counts, attempts=count, invalid_records=invalid)
        result['status'] = 'partial' if invalid else 'ok'
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            result['status'] = 'changed_during_read'
        result['totals'] = {k: dict(known_sum=sums[k] if known[k] or count == 0 else None,
                                   known_records=known[k], unknown_records=count-known[k],
                                   total=sums[k] if known[k] == count and not invalid else None)
                            for k in NUMBERS}
    except (OSError, UnicodeError):
        result['status'] = 'unreadable'
    return result


def budget_status(path):
    result = dict(status='unknown', rows=None, accounted_usd=None, reported_actual_usd=None,
                  conservative_reservations_usd=None, unknown_actual_rows=None,
                  unsettled_rows=None, admission_blocked_by_unsettled=None)
    if path is None:
        return result
    result['status'] = file_state(path)
    if result['status'] != 'ok':
        return result
    sidecars = [Path(str(path)+s) for s in ('-wal', '-shm', '-journal')]
    try:
        # immutable avoids even read-only SQLite creating SHM/WAL files. Refuse
        # journaled state rather than ignore potentially newer committed data.
        if any(p.exists() or p.is_symlink() for p in sidecars):
            result['status'] = 'busy_or_uncheckpointed'
            return result
        before = path.stat()
        c = sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1', uri=True, timeout=.25)
        try:
            rows = c.execute('SELECT day, amount, actual, settled FROM spend').fetchall()
        finally:
            c.close()
        daily = {}
        for day, amount, actual, settled in rows:
            if (not isinstance(day, str) or date.fromisoformat(day).isoformat() != day
                    or not number(amount) or (actual is not None and not number(actual))
                    or type(settled) is not int or settled not in (0, 1)):
                raise ValueError('invalid ledger row')
            daily[day] = daily.get(day, 0) + amount
        after = path.stat()
        if ((before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns)
                or any(p.exists() for p in sidecars)):
            result['status'] = 'changed_during_read'
            return result
        known = [r[2] for r in rows if r[2] is not None]
        result.update(rows=len(rows), accounted_usd=sum(r[1] for r in rows),
                      reported_actual_usd=sum(known) if known or not rows else None,
                      conservative_reservations_usd=sum(r[1] for r in rows if r[2] is None),
                      unknown_actual_rows=sum(r[2] is None for r in rows),
                      unsettled_rows=sum(r[3] == 0 for r in rows),
                      admission_blocked_by_unsettled=any(r[3] == 0 for r in rows),
                      accounted_by_utc_day=dict(sorted(daily.items())))
    except (sqlite3.Error, ValueError, TypeError, OverflowError):
        result['status'] = 'malformed'
    except OSError:
        result['status'] = 'unreadable'
    return result


def collect(home):
    home = Path(home).absolute()
    config, state = config_status(home)
    return dict(schema=1, generated_at_utc=datetime.now(timezone.utc).isoformat(),
                home=str(home), state_dir=str(state) if state else None,
                config=config, metrics=metrics_status(state/'metrics.jsonl' if state else None),
                budget=budget_status(state/'budget.sqlite3' if state else None), limitations=NOTES)


def text_report(r):
    def show(x):
        return 'unknown' if x is None else str(x)
    c, m, b = r['config'], r['metrics'], r['budget']
    lines = [f"Jev disk status | {r['generated_at_utc']}", f"Profile home: {r['home']}",
             f"Config: {c['status']} | installed files: {show(c['installed'])} | enabled: {show(c['enabled'])} | selected: {show(c['selected'])}",
             f"Mode: {show(c['mode'])} | scope: {show(c['session_scope'])}",
             'Configured local budget: '+json.dumps(c['budget'], sort_keys=True),
             f"Metrics: {m['status']} | recorded attempts: {show(m['attempts'])} | pruned candidates: {show(m['pruned'])} | fallback: {show(m['fallback'])} | retained: {show(m['retained'])} | shadow-mode: {show(m['shadow'])}"]
    for key in NUMBERS:
        item = m['totals'].get(key)
        label = 'Candidate/pre-archive bytes' if key == 'candidate_bytes_saved' else key
        lines.append(f"{label}: "+(f"known sum={show(item['known_sum'])}; unknown records={item['unknown_records']}; complete total={show(item['total'])}" if item else 'unknown'))
    lines += ['Recorded reasons: '+json.dumps(m['reasons'], sort_keys=True),
              f"Ledger: {b['status']} | requests recorded: {show(b['rows'])} | accounted USD: {show(b['accounted_usd'])}",
              f"Reported actual USD: {show(b['reported_actual_usd'])} | conservative reservations USD: {show(b['conservative_reservations_usd'])} | unknown actual rows: {show(b['unknown_actual_rows'])} | unsettled: {show(b['unsettled_rows'])}"]
    return '\n'.join(lines+['Limitations:']+['- '+note for note in NOTES])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='Print a non-content JSON snapshot')
    args = parser.parse_args()
    try:
        from hermes_constants import get_hermes_home
    except ImportError:
        parser.exit(2, 'Native hermes_constants unavailable: use target Hermes venv and source PYTHONPATH. No fallback profile was read.\n')
    result = collect(get_hermes_home())
    print(json.dumps(result, indent=2, allow_nan=False) if args.json else text_report(result))


if __name__ == '__main__':
    main()
