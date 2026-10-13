# Benchmark V2 handoff — frozen pre-Pass2 boundary (2026-10-13)

This repository checkpoint records the confirmation benchmark state immediately before independent
replicate judging Pass 2.

## Frozen identities

- catalog snapshot: `068e1b0df74acd8b91d04a5161f4413d57d07bfef5c8c9ce2b8d1100ae780419`
- corpus fingerprint: `f04239fe6df52ab2604ab45a8c08cc83d5bafe79203a4b16c20a2d2a307e2dc6`
- base protocol SHA-256: `d277465bb9572bf6bbff82a5d5bf6f29fd1d9ebd9a5b9940d890d87b87df2dde`
- development query-set SHA-256: `c60d2f6083873bb76591ffdd10d19cfe32f4900c20a4117ca39ecc3d2c40b4e9`
- confirmation query-set SHA-256: `c725fba20382b6d7707b0f1b9bfaba8ac131ebb9c0a461ce7ab4a8988bc26ed5`
- augmented confirmation-pool SHA-256: `04e8a7b25d0a38d8412d6e2e7ff91887848d1ce04943f6e2c20b0cea605f1a4c`
- Pass-1 blinded-input SHA-256: `6f47c16eb59de2179c1d300e6c2e9ab929f858ea5ae4d6896fbaed977b46655d`
- sealed Pass-1 judgments SHA-256: `85ced352b8a7dce34465718895a1c418966df6568d7fd467c88673b01135e8af`
- sealed Pass-1 qrels SHA-256: `65d404e14c60b34b1135c1a8afcb521a58c8485dba2719e6df5c587d8a8049b9`
- Pass-1 judge-criteria SHA-256: `3020848ef8f388103d31e5117f2d7686f77571ce87e6b1297e6f9f85dc898f37`
- Pass-2 blinded-input SHA-256: `0c1dd9bd553e4159aa33493dd0c44383c344b7c7e232a91203c206d26481f0f9`

## Confirmation state

The confirmation query set contains 192 frozen queries. Retrieval completed as 960 runs
(192 queries × five frozen profiles, depth 20). Protocol Amendment 2 authoring-seed augmentation
produced a final 9170-candidate confirmation judgment pool without modifying retrieval ranks.

Primary confirmation judging Pass 1 is complete and cryptographically sealed. Its grade values and
aggregate grade distribution are intentionally not reproduced here before Pass 2.

Pass 2 is frozen for the preregistered 48-query replicate subset, with 2252 query–candidate pairs.
It uses an independently derived candidate order and must be judged in a fresh context with no
access to Pass-1 grades, Pass-1 criteria, repository result summaries, or confirmation quality metrics.

No confirmation retrieval-quality metric has been computed yet.

## Required next sequence

1. Run independent blinded Pass 2 from the frozen Pass-2 input.
2. Freeze/hash Pass-2 judgments.
3. Only then compare Pass 1 and Pass 2 and report replicate-judge consistency.
4. Create a blinded Pass-3 package for all disagreements.
5. Run independent Pass 3.
6. Freeze final qrels using the preregistered median rule.
7. Only after the final qrels hash exists, compute confirmatory retrieval quality and drift metrics.

## Independence warning

Do not expose the full local handoff archive or any Pass-1 judgment/criteria artifact to the Pass-2
judging context. The full archive is a continuity/backup artifact, not a Pass-2 judge input.

The public repository should continue to contain publication-safe manifests, hashes, protocols,
scripts and aggregate results only. Source-text annotation pools and blinded judging inputs remain
local until publication/privacy review.
