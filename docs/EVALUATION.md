# Evaluate the trade-off, not just the byte count

The hypothesis is that selective removal of obsolete search results can reduce context work without reducing task quality. An installation test cannot answer that. Neither can a smaller candidate transcript.

## Start with one bounded comparison

Use public or synthetic material with a known expected answer. Prepare a multi-turn task that naturally includes older `web_search` output outside protected history. Do not lower protection or compression thresholds just to manufacture pruning.

Run the same task in fresh, isolated profiles with identical main model, provider, compression settings, tools and inputs:

- **Baseline:** Hermes's native `compressor`.
- **Experiment:** the `tao-jev` engine with explicitly bounded scoring.

Keep local state and ledgers separate. Do not export a real personal profile to make the fixture. Control changing web results with a documented public fixture where possible. Label replay or synthetic inputs as such. Use repeated paired runs if the cost/time budget allows; a single run is a case report, not a general benchmark.

## Record before and after

| Area | Record |
|---|---|
| Environment | Hermes revision, plugin commit, operating system, model/provider and relevant settings |
| Input | Public fixture identity or hash, expected output, exact instructions, fixed tools |
| Eligibility | Whether compaction occurred; candidate groups; skip/fallback reasons |
| Correctness | Required facts, citations, constraints, completion and any lost evidence |
| Recovery | Repeated searches, corrections, retries and extra user intervention |
| Time | End-to-end task duration separately from compaction/Jev scoring duration |
| Usage | Provider-reported input/output/cache tokens if available; identify missing coverage |
| Cost | Main-model and native-summary charges plus Jev charge where actually measurable |
| State | Host-committed compaction separately from plugin candidate metrics |

Do not estimate a subscription cash saving from token counts alone. If your provider or plan does not expose usable billing/usage, mark that field unknown.

## Read the metrics carefully

- `outcome: pruned` is a plugin-generated candidate, not proof the native host committed it.
- `candidate_bytes_saved` is measured before archive-reference overhead. It is not final serialized savings, token savings, a percentage or a cash saving.
- `elapsed_ms` includes native fallback where used. It is not exclusively Jev latency.
- Shadow-mode observations can overlap fallback counts. Shadow mode can still incur paid scoring.
- Missing metrics means unknown recorded usage. An empty readable file means no records observed, not proof of no activity.
- Schema 1 has no per-event timestamps or original-size denominator. You cannot derive a 14-day percentage from it.
- Status's generation timestamp is the time of the report, not the event time.
- Ledger and metrics costs may describe the same calls. Do not add them together.

For interval comparisons, preserve start/end snapshots and verify the same source files, schema and continuity. Rotation, truncation, missing records or copied state make a reliable interval delta impossible. Report lower bounds and unknown fields instead of filling gaps.

## Success, failure and inconclusive results

**Promising:** repeated matched tasks retain required facts and finish correctly, with a measured improvement in the outcome you care about after including Jev's overhead.

**Not beneficial:** no meaningful improvement, extra latency or cost, more recovery work, or worse correctness. Report it.

**Inconclusive:** no eligible activity, incomparable inputs, insufficient runs, missing usage, or only synthetic pruning evidence. Do not relabel “installed and enabled” as a successful performance trial.

There is no baked-in success percentage. Choose your practical threshold before the comparison and report it alongside the data. A correctness regression can outweigh a large byte reduction.

## Sharing a report

Use the [evaluation template](../.github/ISSUE_TEMPLATE/evaluation.md). Include only public/synthetic fixtures and sanitized aggregates. Never upload transcripts, archival originals, a live budget database or personal status paths. The maintainer cannot reproduce a claim from a screenshot of a smaller context meter alone.
