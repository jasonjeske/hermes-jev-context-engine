# Security and privacy

## Do not use this with sensitive work

This experiment is for ordinary non-confidential personal tasks and public or synthetic tests. Do not enable it for employer information, customer records, financial or health records, private correspondence, credentials or other material you are not authorized to send to the configured external providers.

Use a separate personal-only Hermes profile if you also work with restricted data. A profile-wide setting cannot reliably infer the sensitivity of each future conversation. Keyword checks and redaction are defense in depth, not reliable classification or automatic authorization.

## What leaves the machine

With explicit live-scoring consent, a short task description and selected older tool groups go to **OpenRouter's Decisions API**, routed to **TypeSafe Jev**. Projected groups contain tool names, arguments and result text. Search queries and URLs can be sensitive too. Normal Hermes compression continues to use your existing configured provider when fallback occurs.

The plugin requests `zdr: true`, `data_collection: deny`, `allow_fallbacks: false` and `require_parameters: true`. These are requested routing controls, not a guarantee that the maintainer has independently audited provider retention. Recheck current provider terms before use.

The code does not deliberately export the system prompt or unrelated memory stores. If protected information appears within an otherwise eligible result or task, filtering can miss it. Do not rely on filtering to make a confidential session safe.

## Credentials

Use Hermes's existing supported credential configuration for `OPENROUTER_API_KEY`. The repository contains no keys and the installer must not accept a key as a command-line argument. Never commit `.env`, credentials, auth files, provider responses containing private content, or diagnostic output that includes them.

The transport sends authorization to the fixed OpenRouter endpoint. It does not put the key in process command-line arguments and does not broadly propagate the parent's environment to the transport child. Credentials are still sensitive in process memory and should be protected by the host operating system.

## Local data is sensitive too

Before active pruning, the archive stores the **original transcript**, not just the removed search results. That can include more information than the scoring payload. Protect the profile's local state and backups. New archival files are owner-readable/writable; filesystem permissions are not encryption.

Metrics contain allowlisted operational fields rather than conversation content. The ledger records accounting. Keep all three out of Git and public bug reports. Rollback/removal intentionally preserves state for recovery and accounting rather than deleting it.

## Spending and network failures

A local budget reservation is not a provider-side cap. In-flight billing may continue after a local timeout. Missing or untrusted costs remain unresolved and block more scoring. Do not clear the ledger to bypass this protection. This project does not create or manage provider-side credit limits.

## Dependencies and upgrades

This uses Hermes's native context-engine plugin interface, but also relies on native compressor behavior. No framework patch is required. That does not guarantee compatibility with every update. Run the offline suite and native discovery checks after upgrading Hermes before re-enabling live scoring.

Review the installed source, the selected profile and the dry-run plan before applying changes. Do not install over a conflicting plugin or skill. Avoid running the installer as root.

## Reporting a problem

For non-sensitive bugs, use the repository issue templates with synthetic reproductions. For a security issue, use GitHub's **Report a vulnerability** flow if available, or contact the repository owner privately through an existing trusted channel. If private reporting is unavailable, do not post exploit details or private data in a public issue. A security reporting feature being described here does not mean it has been enabled.

Never attach raw archives, real transcripts, `.env`, auth files or an entire Hermes home. Redact account identifiers and machine paths from status output before sharing. Rotate any exposed credential through its provider and preserve local evidence securely.
