# Development and release contract

## Purpose

Make the complete selective-compaction plugin, status skill and test tooling usable by another Hermes operator without transferring anyone's live setup. The engine is experimental. Its hypothesis is that removing clearly obsolete older web-search output can reduce later context work while preserving task quality. That benefit still needs controlled measurement.

## Boundaries

Use the native context-engine plugin interface. Do not edit Hermes core, routing, memory providers or credentials. Install only into the operator-selected Hermes home. Paid scoring requires explicit opt-in and finite limits. Preserve source archives and accounting on rollback. Refuse conflicting files and configuration drift.

Keep the working distribution separate from deployment evidence. Do not include sessions, live configuration, private logs, state databases, backups, machine names, home-directory paths or historical task records. All examples and tests must be synthetic.

## Acceptance

- Include the whole runtime implementation and status helper, with dependencies and license notices.
- Exercise dry-run, install, repeated install, conflict refusal, activation consent, rollback and edited-file preservation in temporary homes.
- Verify native plugin discovery and status reporting against a named Hermes revision. Do not claim universal version compatibility from interface availability.
- Test invalid provider output, privacy refusal, missing credentials, timeouts, exhausted budgets and history structure offline.
- Document known native rollback bookkeeping limitations without hiding a failing invariant.
- Scan all package files and Git metadata before publication. Verify exact remote commit/tree and private visibility after push.
- Inspect artwork and check local documentation links. Keep launch text as drafts until public release is approved.

## State

Private review candidate. The distribution suite has passed 69 offline tests, including isolated native installation, discovery, status, stock selection and removal. Secret and local-artifact checks passed. See TESTING.md for reproducible commands, scope and the separately failing stock-shared rollback diagnostic. Public publication and community feedback remain pending owner approval.

## Recovery

Follow INSTALL.md to select the built-in compressor and relaunch the affected Hermes process. Reverting selection prevents future selective compaction; it does not automatically reconstruct context already pruned. Do not overwrite user edits or delete ledgers to make an uninstall succeed.
