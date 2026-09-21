# Install, use and remove

Experimental POSIX package for macOS/Linux. Use an existing Hermes installation and its Python environment with PyYAML. This package does not install dependencies, download code, patch Hermes core, change your main model or memory provider, restart services, or make test-provider calls.

## Get the package

During private review, cloning requires repository access and your usual GitHub authentication. After an approved public release, the same URL works without private-repository access.

```sh
git clone https://github.com/jasonjeske/hermes-jev-context-engine.git
cd hermes-jev-context-engine
```

Install Hermes separately using its [official documentation](https://hermes-agent.nousresearch.com/docs/) if needed. This package expects the native context-engine API and the compressor behavior documented in [TESTING.md](TESTING.md). Use that guide's offline test command before changing a profile. It does not require an OpenRouter key.

## Select a profile deliberately

Run from this distribution's root. Substitute your verified native source path and intended profile home:

```sh
export NATIVE="<installed-hermes-source>"
export HERMES_HOME="<intended-profile-home>"
export PYTHONPATH="$NATIVE"
export PYTHONDONTWRITEBYTECODE=1
PY="$NATIVE/venv/bin/python"
"$PY" -B scripts/install.py install
```

The installer uses native `hermes_constants.get_hermes_home()`, not a guessed default. Without `PYTHONPATH`, pass `--native-source "$NATIVE"` on each installer invocation. Inspect the printed `home` before applying. Preserve the selected environment on every command. This does not change Hermes's sticky profile selection.

All operations are **dry-run by default**. `--apply` authorizes writes. The dry-run's `config_sha256` can be supplied with `--expect-config-sha256 <digest>` when applying, rejecting a changed plan. Do not run concurrent configuration editors during installation.

```sh
"$PY" -B scripts/install.py install --apply
"$PY" -B scripts/jev_status.py --json
```

Installation copies the native plugin to `$HERMES_HOME/plugins/tao-jev/` and the callable `/jev-status` skill to `$HERMES_HOME/skills/jev-status/`. The historical `tao-jev` identifier is retained for compatibility. It enables plugin discovery but leaves context selection unchanged, mode off and Jev egress disabled. All state stays under `$HERMES_HOME/state/tao-jev/`. Existing main-model, memory and unrelated configuration values remain unchanged; YAML formatting/comments are not preserved.

## Two distinct opt-ins

**Active selection** alone permits no Jev provider requests:

```sh
"$PY" -B scripts/install.py activate --opt-in-active
"$PY" -B scripts/install.py activate --opt-in-active --apply
```

**Jev egress/spending authorization** is a separate operation. The following values are an example finite local allowance, not a recommended budget or a provider-side billing cap:

```sh
"$PY" -B scripts/install.py authorize-egress --opt-in-egress \
  --scope personal_pilot --exclude-employer-and-secrets \
  --total-usd 0.10 --daily-usd 0.05 --per-call-usd 0.02 --max-requests 2
# Repeat the reviewed command with --apply to authorize.
```

Choose `public_synthetic` only for genuinely public/synthetic sessions. `personal_pilot` explicitly permits ordinary personal tasks, never employer data or secrets. Both CLI scopes require the exclusion acknowledgement. Selected older `web_search` groups and the latest short user request can go to TypeSafe through OpenRouter Decisions. Injected memory/profile markers, recognized secrets and other exclusions are refused; these checks are not a complete classifier. Archives contain original full history and are sensitive local data. Native fallback uses your existing native compression configuration and may make its own model calls; Jev's egress flag is not a global network block.

The installer selects only `web_search`, leaves algorithm thresholds unchanged, and preserves native protected-tail settings. Personal scope uses the original narrow personal policy; public scope explicitly selects the same single-tool allowlist. Mode `shadow` is supported by the engine but can still score and spend when egress is authorized. The CLI intentionally offers off/active, not an ambiguous free shadow mode.

Limits must be finite and satisfy `0.02 <= per-call <= daily <= total`, with a positive request count. Daily accounting uses UTC. Reservations survive crashes/timeouts. Unknown/unsettled requests block future admissions; do not delete or reset the ledger to resume. Changing limits does not erase spending. OpenRouter credentials are resolved by Hermes only when a scoring request is actually admitted; use native credential configuration, never put credentials in these commands.

Authorization is bound to the complete normalized hostname and exact native profile-home path. Wildcards and blank hostnames are refused. Moving config to another hostname/home does not transfer Jev authorization. A configured foreign `state_dir` is refused, not followed. Reauthorize deliberately on a new installation. This is an accidental-copy safety control, not a cryptographic machine identity or protection against a same-user attacker.

## Verify and use

Relaunch the affected Hermes CLI or deliberately restart its gateway through native controls when appropriate; this installer never interrupts running work. Use native `hermes plugins list`, then `/jev-status` in a fresh chat. If required use `/reload-skills` for skill discovery. The skill invokes its bundled read-only helper. You can also run:

```sh
"$PY" -B scripts/jev_status.py
"$PY" -B scripts/jev_status.py --json
```

Installed, enabled, selected and current-process adoption are different facts. Status reports disk state and recorded attempts, not confirmed host commits or measured task savings. See [TESTING.md](TESTING.md).

## Stock rollback and uninstall

```sh
"$PY" -B scripts/install.py stock
"$PY" -B scripts/install.py stock --apply
# Relaunch affected Hermes process to use the built-in compressor.
"$PY" -B scripts/install.py remove
"$PY" -B scripts/install.py remove --apply
```

`stock` selects `compressor` only if Jev is currently selected, sets Jev mode off and disables its egress/spend policy. It does not overwrite another newer engine selection. `remove` also removes owned plugin/skill files and its enabled-list membership. Both preserve accounting, archives, metrics and owner-only backups. Neither reconstructs already-pruned in-memory context or restores an entire old config. Reinstall retains existing accounting. Repeated unchanged install/stock/remove is harmless.

Unrelated config edits and unowned file additions survive. Edits to owned plugin settings/files are conflicts: the installer refuses rather than overwrite them, including during removal. For an urgent stock switch despite a conflict, use native `hermes config set context.engine compressor` with the same selected profile, then relaunch. Review/reconcile owned edits manually before retrying removal; do not restore an entire backup over newer config. Remove unowned additions only after deliberate review.

## Recovery boundaries

Before config changes, a full local preimage is saved with mode 0600 under `state/tao-jev/backups/`; it can contain secrets and must never be published. An installer lock plus config/manifest byte comparison detects ordinary concurrent changes. Writes use same-directory replacement. This is not a filesystem-wide transaction or a hostile-process sandbox: power loss or a race from a noncooperating writer can leave staged files. Stop, compare the owner-only manifest/backup and reconcile rather than force installation. A stale `installer.lock` may be removed only after confirming no installer is running. Symlinked destination paths are refused; do not bypass refusal by resolving them into another profile.

The native rollback bookkeeping limitation in [TESTING.md](TESTING.md) remains unresolved. Do not treat a successful stock switch as proof that every cancelled compression restores all native private attributes.
