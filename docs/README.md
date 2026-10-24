# Research documentation

This directory contains the dated protocol records and analysis notes used during development of the retrieval-provenance study. The files are kept so that the sequence of design decisions can be checked against the final paper.

For a shorter publication-facing guide, start with [`../reproducibility/README.md`](../reproducibility/README.md).

## Corpus A

The main corpus-A records are:

- `retrieval_benchmark_v2_protocol.md` — benchmark design and evaluation plan;
- `retrieval_benchmark_v2_amendment_*.md` — changes made during benchmark construction;
- `benchmark_v2_reproducibility_20261015.md` — identifiers, profile hashes, and result anchors;
- `benchmark_v2_results_ready_synthesis_20261015.md` — final corpus-A result summary;
- `benchmark_v2_bge_m3_robustness_20261015.md` — BGE-M3 second-backbone analysis;
- `benchmark_v2_retrieval_provenance_negative_controls_20261015.md` — provenance mutation controls;
- `benchmark_v2_rq4_descriptive_synthesis_20261015.md` — source/query sensitivity analysis;
- `rq3_answer_drift_protocol_frozen_20261014.md` — answer-drift generation and judging protocol.

Corpus A contains 274 sampled datasets and 192 confirmation queries. Its provenance hierarchy is dataset → file-aware intermediate identity → chunk.

## Corpus B

The main corpus-B records are:

- `second_corpus_confirmation_protocol_v2.md` — confirmation protocol;
- `second_corpus_confirmation_results_20261018.md` — confirmatory retrieval results;
- `second_corpus_v2_preretrieval_adapter_10_distribution_identity.md` — dataset/distribution/chunk identity definition used for retrieval;
- `second_corpus_c2_answer_drift_extension_v1.md` — answer-drift extension;
- `second_corpus_c2_answer_drift_context_feasible_amendment_v2.md` — context-window feasibility amendment;
- `second_corpus_answer_drift_results_20261018.md` — answer-drift results;
- `second_corpus_c2_secondary_judge_replication_protocol_v1.md` — secondary blinded judging protocol;
- `second_corpus_c2_secondary_judge_results_20261018.md` — multi-judge sensitivity results;
- `second_corpus_posthoc_validation_protocol_v1.md` — additional diagnostic analysis.

Corpus B contains 400 selection records corresponding to 397 unique dataset IDs, 800 retained distributions, and 96 queries. A selection record is a sampling unit, not a provenance identity.

The corpus-B confirmation analysis supports H1, does not support the pre-specified H2 multiplicity association, and reproduces the exact ordered evidence for all 192 recorded corpus-B retrieval runs used for H3.

## Judging records

The relevance and answer-drift experiments used blinded model-based judging, with human validation for the downstream semantic-change endpoint. Provider-specific prompt files are retained because they are part of the recorded experimental procedure. They should be read as judge instructions, not as manuscript source text.

The primary paper results do not depend on model-based labels for the provenance-resolution or replay endpoints. Those endpoints are computed directly from recorded retrieval identities.

## Historical records

Some filenames contain earlier terminology such as `audit`, `replication`, or version-specific labels. These names are kept because they identify frozen scripts and dated records used during the experiment. The manuscript uses the final terminology consistently.

Implementation and deployment notes that are not specific to the paper remain in this directory as part of the underlying PiPi data-catalog project.