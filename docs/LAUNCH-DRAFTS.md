# Launch drafts for owner review

These drafts are not published. The repository is private during review. Do not
post the link until the owner chooses to make it public. No community feedback
has been collected yet.

## X post

I built an experimental Jev context engine for Hermes. It scores older search results before compaction, with local archives and native fallback. No core patches. Savings are unproven; I want tests, not hype.

[Add the public repository link after approval. Attach assets/social-card.png.]

## Hermes development discussion

I've been testing a small context-engine plugin for Hermes using TypeSafe Jev
through OpenRouter Decisions. It looks at eligible older web-search results when
Hermes compacts, rather than touching the main model or memory system.

The idea is to remove clearly obsolete result bodies before the normal compressor
has to summarize them. It archives the original transcript locally first and
uses native compression when the eligibility, scoring or reduction checks fail.
It is conservative, but it can still make a bad decision.

The package includes the complete source, a preview-first installer, an explicit
paid-scoring opt-in, local budget accounting, a read-only /jev-status skill and
offline tests. No Hermes core patches are required. Compatibility still needs
checking against the Hermes revision you run.

I am not claiming token, cost or speed savings yet. I'd like help testing matched
tasks, especially whether citations and important constraints survive. Reports
of no benefit or regressions are welcome too. Please use public or synthetic
inputs, not employer or sensitive data.

[Add public repository link after approval.]

## Before posting

- Review the README, installation and privacy disclosures.
- Review the final verification and known native limitations.
- Confirm the intended public license and original artwork.
- Re-run release checks on the final commit.
- Change visibility only with the owner's approval and verify it afterward.
- Optionally upload assets/social-preview.jpg as the GitHub social-preview image.
- Publish through the owner's approved channel only after approving the text.
