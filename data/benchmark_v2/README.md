# PiPi Benchmark V2 data artifacts

This directory contains frozen manifests and publication-safe result artifacts for PiPi Benchmark V2.

Primary confirmation artifacts use the frozen confirmation query-set identifier `c725fba20382` and preserve the original E5 experiment as the confirmatory analysis.

BGE-M3 files are a separate post-hoc second-backbone robustness layer:

- `bge_m3_robustness_results_final_v1.json` — aggregate metrics, paired contrasts, subgroup summaries and drift statistics
- `bge_m3_robustness_final_manifest_v1.json` — SHA-256 chain for the retrieval ledger, blinded judging inputs and frozen outputs

The complete retrieved chunk text and local LLM answer artifacts are intentionally not committed here. The repository keeps hashes and publication-safe summaries so the primary experiment and later robustness analysis remain distinguishable.

See `../../docs/benchmark_v2_reproducibility_20261015.md` for the frozen identifiers, profile hashes and rerun commands.
