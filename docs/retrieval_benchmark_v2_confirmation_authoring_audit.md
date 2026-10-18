# PiPi Benchmark V2 — confirmation query authoring audit

**Decision: PASS — 192 confirmation queries frozen before confirmation retrieval.**

## Frozen context

- Catalog snapshot: `068e1b0df74acd8b91d04a5161f4413d57d07bfef5c8c9ce2b8d1100ae780419`
- Corpus fingerprint: `f04239fe6df52ab2604ab45a8c08cc83d5bafe79203a4b16c20a2d2a307e2dc6`
- Base protocol SHA-256: `d277465bb9572bf6bbff82a5d5bf6f29fd1d9ebd9a5b9940d890d87b87df2dde`
- Development query-set SHA-256: `c60d2f6083873bb76591ffdd10d19cfe32f4900c20a4117ca39ecc3d2c40b4e9`
- Confirmation query-set SHA-256: `c725fba20382b6d7707b0f1b9bfaba8ac131ebb9c0a461ce7ab4a8988bc26ed5`
- Confirmation judging config was frozen before authoring under Protocol Amendment 4.

## Structural checks

- Confirmation queries: **192**
- Source families: **48 per family**
- Query types: **32 per type**
- Language relation: **48 cross-language / 144 same-language**
- Query languages: **96 Croatian / 96 English**
- Preassigned replicate-judgment queries: **48**
- Replicate positions: **1 and 3 in every one of the 24 family × query-type cells**
- Missing dataset/file targets: **0**
- Language-relation violations: **0**

## Retrieval-blind boundary

The confirmation cases were authored from the frozen corpus inventory and source previews only. No lexical, vector, hybrid, rank, score, pooled-candidate, or confirmation-quality output was inspected while choosing targets or wording queries.

The frozen 16-query pilot wording was checked against the confirmation set. No pilot query wording was copied into confirmation.

## Near-duplicate screen

- Highest simple character-sequence similarity among confirmation query strings: **0.788**
- Pair: `v2-conf-institutional-semantic-05` vs `v2-conf-institutional-entity-05`

This lexical screen is only a warning diagnostic. The remaining highest-similarity pair does not differ only by punctuation, trivial word order, or one substituted keyword.

## Target reuse

- Confirmation dataset targets also used in development: **13**
- Confirmation software file targets also used in development: **3**

Target reuse across development and confirmation is allowed because the information needs and query wording are distinct. No target dominates a source-family × query-type cell.

## Decision

The 192-query confirmation set is frozen. From this point onward, query wording, target seeds, source-family allocation, language relation, corpus snapshot, and retrieval profiles must not be changed in response to confirmation retrieval output.
