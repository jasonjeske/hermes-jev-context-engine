# Hermes + Jev: selective context, measurable trade-offs

![Original community artwork: a messenger-inspired engineer and Jev companion sorting context cards](assets/hero.png)

**What if an agent could drop clearly obsolete search results before summarizing everything else?**

This is a small, experimental context-engine plugin for [Hermes Agent](https://github.com/NousResearch/hermes-agent). At compaction time, it asks [TypeSafe Jev](https://openrouter.ai/typesafe/jev-1.13) which eligible older tool results are no longer needed. If the answer passes the local checks, it archives the original transcript and replaces selected result bodies with archive markers. Otherwise, it uses Hermes's normal compressor, or retains the input when proceeding is unsafe.

**The goal is less unnecessary context work without losing what matters. The benefit is a hypothesis, not a benchmark result.**

> Experimental community project. Not an official Nous Research, Hermes Agent, OpenRouter or TypeSafe release. Keep it away from employer, confidential and sensitive data. Read the [data-flow and security notes](SECURITY.md) before enabling scoring.

## Why build this?

Long research sessions accumulate search results that were useful ten turns ago but may no longer matter. Summarizing all of them costs work too. This experiment tests a narrower alternative: score a few eligible old results, keep uncertain evidence, and prune only when the resulting context is meaningfully smaller.

It is not a replacement for Hermes, its memory system or your main model. It is one selectable context engine using Hermes's native plugin interface. No core patches, model router, background daemon or memory migration.

## What is in the box?

- **Full plugin source:** selection policy, Jev Decisions client, bounded transport, local accounting, archival and native-compression fallback.
- **Portable installer:** previews changes first, requires explicit application and separate consent for paid external scoring.
- **`/jev-status` skill:** read-only configuration, metrics and budget visibility. It does not call a provider.
- **Offline tests:** synthetic fixtures for policy, budgets, native integration and the install/rollback lifecycle.
- **Complete documentation:** [installation and rollback](docs/INSTALL.md), [how it works](docs/OVERVIEW.md), [testing](docs/TESTING.md), and [how to evaluate it fairly](docs/EVALUATION.md).

## Know the limits before trying it

| Question | Honest answer |
|---|---|
| Does it run on every message? | No. It runs when Hermes invokes compaction. |
| What can it prune? | The supported personal setup considers older `web_search` tool results only, outside protected history. |
| Will a big coding session benefit? | Not necessarily. File reads, terminal output and memory are not eligible in this setup. |
| Is the latest request protected? | Yes. The latest user turn and everything after it are excluded from pruning. |
| Is this a memory system? | No. It does not read or write Hindsight or other memory stores. |
| Does it preserve everything correctly? | That is what needs testing. Conservative checks reduce risk; they do not prove the scorer is right. |
| Are savings proven? | No. Integration tests and candidate-byte reductions are not whole-task savings. |
| Can I turn it off? | Yes. Select `compressor` and relaunch. That stops future use; it does not reconstruct context already pruned. |

The internal plugin identifier is **`tao-jev`**, retained for compatibility. The repository name is `hermes-jev-context-engine`.

## Get started

You need an existing compatible Hermes installation and its native Python environment. Follow the [step-by-step installation guide](docs/INSTALL.md). It covers cloning this repository, an offline dry run, installation, optional bounded activation, verification and removal.

**Start with offline tests and a disposable personal-only profile.** Installation alone does not authorize sending data to Jev. A working OpenRouter credential is required only for explicitly enabled live scoring. Never paste a key into an issue, command example or this repository.

Once the skill is installed and discovered:

```text
/jev-status
```

For a session that has not discovered the direct skill name yet:

```text
/skill jev-status
```

Saved selection is not proof that an already-running chat loaded the engine. Relaunch the affected Hermes process after changing engines.

To return to the built-in compressor, with the intended Hermes home/profile already selected:

```sh
hermes config set context.engine compressor
```

See [INSTALL.md](docs/INSTALL.md) for profile-safe commands and safe removal.

## What we need from community testing

1. **Does it run?** Capture the engine selection, eligibility and outcome. Missing metrics means unknown usage, not zero use.
2. **Does it help?** Compare matched tasks against the native compressor, including Jev latency and charges.
3. **Does it preserve quality?** Check facts, citations, constraints and task completion. Report lost evidence and extra recovery work, not just shorter context.

A `pruned` metric means the plugin produced a candidate. It does not establish host-committed compaction. Candidate bytes are not tokens or dollars, and Jev's reported charge excludes your main model and native summarizer.

Use the [evaluation protocol](docs/EVALUATION.md) and [issue templates](.github/ISSUE_TEMPLATE). An honest “no benefit” or “not enough eligible activity” result is useful.

## Current evidence

The original bounded pilot exercised native loading, a real public-data Decisions request, synthetic pruning/archive/resume and switching back to the stock compressor. Those checks establish integration paths, not a performance improvement. Private machine records and usage databases are deliberately excluded from this distribution.

This portable package has its own verification record in [TESTING.md](docs/TESTING.md). Compatibility is tied to the tested Hermes revision, not a promise that every past or future version works. There is a documented stock-shared rollback bookkeeping limitation; see the testing notes before relying on recovery behavior.

## Project map

| Start here | Purpose |
|---|---|
| [INSTALL.md](docs/INSTALL.md) | Prerequisites, install, consent, status, rollback and uninstall |
| [OVERVIEW.md](docs/OVERVIEW.md) | Algorithm, protections, configuration and data flow |
| [EVALUATION.md](docs/EVALUATION.md) | Matched testing, quality checks and honest reporting |
| [TESTING.md](docs/TESTING.md) | Reproducible commands, checks and known limitations |
| [SECURITY.md](SECURITY.md) | External data, credentials, archives and disclosure |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Small changes, tests and useful reports |
| [DEVELOPMENT.md](docs/DEVELOPMENT.md) | Scope and release acceptance contract |

Built by Jason Jeske with Hermes Agent. Released under the [MIT License](LICENSE). Names and trademarks belong to their respective owners; see [NOTICE](NOTICE). The header is original AI-generated community artwork, not an official Hermes mascot or an endorsement.
