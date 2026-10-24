# PiPi Benchmark V2 artifacts

This directory contains publication-safe manifests and retained result artifacts for the corpus-A benchmark.

The confirmation query set is identified by `c725fba20382`. The E5 retrieval experiment is the primary confirmation analysis reported in the paper. BGE-M3 was evaluated later as a second-backbone robustness analysis and does not replace the primary E5 judgments.

The BGE-M3 files are:

- `bge_m3_robustness_results_final_v1.json` — aggregate retrieval metrics, paired contrasts, subgroup summaries, and drift statistics;
- `bge_m3_robustness_final_manifest_v1.json` — hashes for the retrieval ledger, blinded judging inputs, and retained outputs.

The complete retrieved chunk text and local generator outputs are not committed here. Publication-safe artifacts retain hashes, identifiers, and aggregate results so that the primary experiment and the later robustness analysis remain distinguishable without redistributing source material unnecessarily.

See `../../docs/benchmark_v2_reproducibility_20261015.md` for the recorded identifiers, profile hashes, and analysis notes.