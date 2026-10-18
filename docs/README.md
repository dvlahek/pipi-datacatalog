# PiPi documentation map

This directory contains both frozen research records and implementation notes. The files below are the shortest path into the current project state.

## Current retrieval-provenance paper line

Start here:

1. `benchmark_v2_results_ready_synthesis_20261015.md` — C1 results synthesis, including answer drift and BGE-M3 robustness.
2. `benchmark_v2_reproducibility_20261015.md` — frozen C1 identifiers, result anchors and publication boundary.
3. `second_corpus_confirmation_results_20261018.md` — C2 independent-corpus confirmatory retrieval results and C1–C2 comparison.
4. `second_corpus_answer_drift_results_20261018.md` — final C2 Qwen answer-drift extension, context-feasible coverage, blinded judging and hidden-drift answer propagation.
5. `second_corpus_confirmation_protocol_v2.md` — prospective C2 confirmation protocol.
6. `second_corpus_v2_preretrieval_adapter_10_distribution_identity.md` — C2 dataset/distribution/chunk identity adapter frozen before retrieval.
7. `second_corpus_c2_answer_drift_extension_v1.md` — original post-confirmatory Qwen answer-drift extension boundary.
8. `second_corpus_c2_answer_drift_context_feasible_amendment_v2.md` — frozen technical amendment after the 16,384-token feasibility audit.

## C1 benchmark support records

- `benchmark_v2_bge_m3_robustness_20261015.md`
- `benchmark_v2_retrieval_provenance_negative_controls_20261015.md`
- `benchmark_v2_rq4_descriptive_synthesis_20261015.md`
- `retrieval_benchmark_v2_confirmation_authoring_audit.md`
- `retrieval_benchmark_v2_amendment_*.md`

These records preserve protocol changes, robustness analyses and audit decisions. They should not be silently merged into one evidential category.

## C2 evidence status

The C2 confirmatory retrieval result is frozen:

- H1 granularity effect: supported
- H2 frozen multiplicity mechanism: positive direction, not statistically supported
- H3 exact ordered-evidence replay: 192/192

The Qwen C2 answer-drift result is a separate post-confirmatory descriptive extension. The unchanged 16,384-token C1 generation contract was feasible for 81/96 complete query pairs. Within that context-feasible subset, material answer drift occurred in 31/81 pairs (38.27%). Under the strict hidden-drift condition of an identical retrieved dataset set with changed chunk evidence, 9/19 pairs (47.37%) produced material answer drift.

These answer-level values must not be relabeled as prospectively confirmatory or generalized to all 96 C2 queries without the context-feasible qualification.

## Publication-safe answer-drift reproduction

`../scripts/second_corpus_answer_drift_reporting_v2.py` verifies the frozen local input hashes and recomputes aggregate C2 answer-drift results without emitting answer text, evidence text or the private A/B orientation.

The raw local answer/evidence artifacts are intentionally outside the publication surface because publicly accessible source material does not automatically imply redistribution rights.

## Implementation / deployment notes

- `online_mvp.md` — deployment-facing MVP notes
- DCAT, retrieval, replay and benchmark implementation details are primarily documented alongside their configs and scripts under `config/` and `scripts/`.

## Publication boundary

Some local benchmark artifacts contain third-party source or chunk text. The public repository should prefer publication-safe manifests, hashes, aggregate results, configs and replay/audit code. Raw third-party content should only be redistributed when its licence explicitly permits that redistribution.

The frozen C1 reproducibility record is itself used as a hashed source in later C2 reporting. Do not edit historical frozen records merely to make documentation wording more current. Add a new dated record instead.
