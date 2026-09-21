---
name: jev-status
description: "Use for read-only Jev status, usage and budget checks."
version: 0.1.0
license: MIT
platforms: [linux, macos]
---

# Jev status

Use `/jev-status` to report saved configuration and recorded activity. This is a callable Hermes skill, not a plugin slash-command hook. Never enable egress, change configuration, read archives or call a provider to obtain status.

Preserve the intended profile's `HERMES_HOME`. Resolve the installed Hermes Python and source and this skill's directory; do not guess another profile. With verified paths:

```sh
HERMES_HOME="<intended-profile-home>" PYTHONPATH="<native-hermes-source>" PYTHONDONTWRITEBYTECODE=1 "<native-hermes-source>/venv/bin/python" -B "<this-skill-directory>/scripts/jev_status.py"
```

Append `--json` for a machine-readable snapshot. Native `hermes_constants.get_hermes_home()` selects the profile. The helper does not import plugin/agent code, contact APIs, read credentials, inspect archives or initialize memory. It reads only profile-bound config, metrics and budget state. It refuses symlinks and journaled SQLite state rather than repairing them.

Report installed, enabled, selected and mode separately. Saved config does not prove current-process adoption; relaunch is required after changes. Missing metrics are unknown usage, not zero. `pruned` means candidate output, not host commit. Candidate bytes exclude archive-reference overhead and are not token savings. Shadow counts overlap fallback. Metrics have no event timestamps or whole-context denominator, so do not infer period totals or reduction percentages. Costs exclude native summary and main-model calls. Reservations are not measured charges or provider-enforced caps; do not add ledger and metrics costs together.

Surface unknown, partial and malformed sources. Report local ledger unsettled requests as an admission block, never delete them. Compare snapshots only when file/schema continuity is established. Whole-task quality and net benefit require separate evaluation. Keep the bundled helper identical to package `scripts/jev_status.py`.
