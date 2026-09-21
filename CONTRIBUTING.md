# Contributing

Small, reproducible changes are welcome. The useful question is not whether this
can produce a smaller prompt; it is whether it preserves quality and improves
real work after its own overhead.

1. Read [the development contract](docs/DEVELOPMENT.md) and [security notes](SECURITY.md).
2. Use a disposable home and synthetic data. Never test a pull request against a live personal profile.
3. Follow [TESTING.md](docs/TESTING.md). Add a regression test for behavior changes.
4. Keep the plugin on native Hermes interfaces. Do not patch Hermes core, change model routing or integrate memory stores.
5. Preserve explicit external-data consent, finite budgets, archive-before-pruning and conservative fallback.
6. Keep the bundled status helper byte-identical to its canonical source.
7. Report the exact Hermes and plugin revisions and any known failures. Do not remove a failing invariant merely to obtain a green suite.

Use the issue templates for bug reports or paired evaluation results. Share only
public/synthetic fixtures and sanitized aggregates. No raw archives, credentials,
personal paths, real transcripts or full profile exports.

A change that broadens eligible tools, external payloads, automatic activation or
spending needs an explicit design discussion before implementation.
