# PiPi Benchmark V2 — Frozen RQ3 Answer-Drift Protocol

Date: 2026-10-14  
Status: **frozen before any benchmark answer generation**

## Goal

RQ3 tests whether changing only the frozen retrieval profile changes the downstream grounded answer. The corpus, confirmation query set, embedding model, generator prompt, decoding, evidence depth, and model files are fixed.

The primary retrieval contrast is:

`hybrid-e5-content-v1` vs `hybrid-e5-metadata-v1`

The retrieval stage is already frozen and the full confirmation replay gate passed exactly for 960/960 retrieval runs.

## Generator panel

Three compact, distinct model families are used:

1. **Qwen3-8B Q4_K_M** — primary generator.
2. **Ministral 3 8B Instruct Q4_K_M** — robustness replication.
3. **Gemma 3 4B IT Q4_K_M** — robustness replication.

All models are executed locally through the same llama.cpp OpenAI-compatible API, one model at a time. The exact GGUF SHA-256 values are frozen in `config/rq3_answer_drift_protocol.json`.

## Main experiment

For each of the 192 frozen confirmation queries and each generator:

- generate one answer from top-10 `hybrid-e5-content-v1` evidence;
- generate one answer from top-10 `hybrid-e5-metadata-v1` evidence.

Main generation count:

`192 queries × 2 retrieval conditions × 3 generators = 1152 answers`.

The primary inferential RQ3 result is defined on the Qwen3-8B primary generator. Ministral and Gemma are prespecified robustness replications and all results must be reported.

## Same-evidence control

The 48 frozen `double_annotation=true` cases receive one additional repeated generation from the exact same `hybrid-e5-content-v1` context for each model.

Additional count:

`48 × 3 = 144`.

With deterministic decoding this is interpreted as a platform/determinism control, not as an estimate of free-running sampling variance.

## Prompt and decoding

The exact system prompt and user template are frozen in the JSON protocol. Evidence is serialized deterministically as `[E1]` ... `[E10]` with dataset identifier, dataset version, chunk index, file path, and chunk text. Retrieval scores are not shown to the generator.

Frozen decoding:

- temperature: 0
- top_p: 1
- seed: 20261014
- max_tokens: 384
- maximum requested answer length: 180 words
- context size: 16384
- Qwen reasoning mode: off

## Input-freeze boundary

No benchmark answer may be generated immediately after preparing the RQ3 inputs.

Required sequence:

1. run `scripts/prepare_benchmark_v2_rq3_inputs.py`;
2. record the printed RQ3 protocol SHA and RQ3 input SHA;
3. record the local llama.cpp version and verified GGUF hashes;
4. commit a `pipi-benchmark-v2-rq3-input-freeze` manifest;
5. only then run `scripts/run_benchmark_v2_rq3_llamacpp.py`.

The generation runner refuses to operate without a matching freeze manifest.

Generic non-benchmark smoke prompts are allowed before the input freeze.

## Primary endpoint

A blinded judge compares the two answers for the same query without knowing which answer came from content or metadata retrieval.

Frozen ordinal material-change scale:

- 0 — semantically the same answer; wording-only differences
- 1 — minor difference; same substantive conclusion
- 2 — materially different content, support, qualification, or conclusion
- 3 — substantially different or contradictory answer

The primary RQ3 endpoint is the paired material-answer-change result for the primary generator.

Secondary analyses include groundedness/support, evidence-reference change, deterministic text/semantic similarity, the relation between chunk churn and answer drift, the relation between absolute retrieval-quality change and answer drift, and cross-model robustness/heterogeneity.

## Prohibited after generation begins

Do not change the model panel, quantization, prompt, top-k, evidence serialization, retrieval profiles, generation parameters, or primary endpoint after the first benchmark answer is generated. Do not omit a model because its result is weak. Subgroup findings remain descriptive unless already preregistered.
