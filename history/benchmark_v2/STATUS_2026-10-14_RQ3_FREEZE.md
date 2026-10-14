# PiPi Benchmark V2 — RQ3 freeze checkpoint, 2026-10-14

Repository: `dvlahek/pipi-datacatalog`  
Branch: `feature/sensor-hub-bootstrap`

## Closed before RQ3

- RQ1 retrieval-profile effect: closed by frozen confirmation analysis.
- RQ2 strict computational replay: **PASS 960/960 exact ordered-evidence replays, 0 failures**.
- strict replay source JSON SHA-256: `e68bcdf2b1538d644f0988542552d332b11ea37d4edfcc74da194fdfb1d41ea1`.
- RQ4 source/query/language heterogeneity remains prespecified descriptive analysis.

## RQ3 protocol frozen before benchmark answer generation

Primary generator:
- `qwen3-8b-q4km`
- `Qwen/Qwen3-8B-GGUF`, `Q4_K_M`
- GGUF SHA-256 `d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785`

Robustness generators:
- `ministral3-8b-q4km`, GGUF SHA-256 `33e7a72cf5e6e2cfc2f2847075acc013d68bba023e35310cef86b5cf8fdca761`
- `gemma3-4b-q4km`, GGUF SHA-256 `882e8d2db44dc554fb0ea5077cb7e4bc49e7342a1f0da57901c0802ea21a0863`

Main experiment:
- 192 queries
- `hybrid-e5-content-v1` vs `hybrid-e5-metadata-v1`
- top-k 10 evidence
- 3 generator families
- 1152 primary answer generations
- 144 additional same-evidence deterministic control generations

Frozen protocol files:
- `config/rq3_answer_drift_protocol.json`
- `docs/rq3_answer_drift_protocol_frozen_20261014.md`

Local tooling:
- `scripts/setup_rq3_models.ps1`
- `scripts/start_rq3_model.ps1`
- `scripts/prepare_benchmark_v2_rq3_inputs.py`
- `scripts/run_benchmark_v2_rq3_llamacpp.py`

## Mandatory next boundary

Generic smoke tests are permitted. Benchmark answer generation is **not** permitted yet.

Run input preparation, then freeze:
1. RQ3 protocol SHA-256
2. RQ3 input artifact SHA-256
3. llama.cpp version
4. all three verified GGUF hashes

Only after the matching `pipi-benchmark-v2-rq3-input-freeze` manifest is committed may the RQ3 generation runner be executed.
