# Verification

## Reproduce offline

From the distribution root, use your installed Hermes environment, not system Python:

```sh
NATIVE="<installed-hermes-source>"
"$NATIVE/venv/bin/python" -B scripts/test.py --native-source "$NATIVE"
```

The runner sets synthetic `HOME`, `HERMES_HOME` and temporary storage under `.test-work/`, removes inherited Hermes/credential routing variables, disables bytecode writes and denies network socket connections in its test process. Fresh native-discovery children install their own network denial. Transport uses controlled doubles; the real worker is exercised only with a refused non-provider endpoint. No copied Hermes core or historical private fixture is included. Do not run the test modules directly against a live home.

**Verified distribution suite: 69 tests passed, exit 0**, using installed Hermes revision `2c0b2a980c2d0e92f0452500089f5af91208f94c` on macOS. This is one tested revision, not proof of compatibility with every `>=0.21` build or a Linux execution result.

Covered behavior:

- Dry-run without target writes; default-off installation; repeat install; explicit active selection and separate finite-budget egress authorization.
- Actual native plugin discovery, native selector/deepcopy, callable `/jev-status` discovery, installed status helper execution, stock selection and removal in isolated homes.
- Preserved main-model/memory values, unrelated newer configuration edits, archive/accounting retention and owner-only config backups.
- Edited owned-file/config conflicts, symlink refusal, stale-plan digest refusal and an injected concurrent config change.
- Full original candidate algorithm: group validity, error/evidence/recency protection, archive originals, malformed probability/route/usage refusal, timeouts, busy admission, fallback and cancellation checks.
- Personal-scope exclusions, no file/terminal/mailbox/memory candidates, persistent daily/lifetime/request accounting, unsettled-request blocking and no credential resolution before privacy checks.
- Transport timeout kills and reaps the worker; credential/proxy environment scrubbing; endpoint refusal. No live Decisions API request was made.
- Status privacy whitelist, no network/import side effects, unchanged input files, symlink/journal refusal and honest unknown/partial accounting. The no-plugin-import assertion runs in a fresh interpreter so suite ordering cannot create a false failure.

Some unit fixtures deliberately reduce the protected tail to create candidates. The production default remains 40, and the installer never lowers it. Synthetic pruning does not demonstrate usefulness on real tasks.

## Separate known native rollback invariant

Run this diagnostic separately:

```sh
"$NATIVE/venv/bin/python" -B scripts/rollback_probe.py --native-source "$NATIVE"
```

**Observed exit 1 for the stronger full-restoration invariant, for both stock and Jev.** Both report `snapshot_restored: true` but `full_restoration: false`. Native rollback omits:

- `_last_feasibility_skip`
- `_last_compress_refused_would_grow`
- `_structural_no_op_backoff_until`

This is deliberately not relabeled a passing product test, hidden with `xfail`, or repaired by a core patch. The standalone diagnostic exits nonzero when the stronger invariant fails. The green distribution suite is a bounded acceptance result, **not an assertion that all native rollback behavior is correct**.

The stock case uses a short no-op transcript; Jev uses synthetic scoring and pruning. Both restore the native allowlisted snapshot, but the comparison does not establish identical downstream effects or universal cancellation safety. Cleared structural backoff can permit an earlier retry; feedback flags can differ after a cancelled attempt. Local candidate archives/metrics and remote billing are outside the native rollback transaction. An unused archive or a `pruned` metric is not a confirmed commit. Returning to stock prevents future Jev selection after relaunch; it cannot reconstruct already-pruned in-memory context.

## Limits and release review

These checks do not exercise full live AIAgent/provider continuation, gateway or Desktop UI interaction, provider-side spend enforcement, performance savings, all native lifecycle races, Windows permissions, or all filesystem crash races. No paid inference, live install, service restart, private memory read or core modification was performed for this package build.

The installer uses optimistic byte comparisons plus its own lock, not a cross-application transactional lock. Review conflicts manually. YAML comments/formatting are not preserved. Status snapshots are best-effort across files. See [INSTALL.md](INSTALL.md) for recovery.

Before release, independently review source and privacy, rerun against the intended native revision, inspect package contents, and distinguish local checks from any separately authorized live smoke/evaluation. A native source change invalidates compatibility assumptions until retested.
