# PiPi Benchmark V2 — final confirmation retrieval results

**Status:** confirmatory analysis opened only after final qrels freeze.

- final qrels SHA-256: `a0946546b7b0109bfc8f0920b7cd8de6412c210cbe26ffb36f155f4a0a5637ad`
- retrieval ledger SHA-256: `335555045685798fc27f781b39092d1b1b9f17af8c53dd16d0e2f757db18a1c0`
- confirmation cases: 192
- retrieval runs: 960

## Overall retrieval quality

| Profile | nDCG@10 | MRR | Recall@10 | Hit@1 | Hit@3 | Hit@10 |
|---|---:|---:|---:|---:|---:|---:|
| lexical-v1 | 0.4891 | 0.5469 | 0.5196 | 0.4375 | 0.6250 | 0.7396 |
| vector-e5-content-v1 | 0.7013 | 0.7902 | 0.6813 | 0.7083 | 0.8542 | 0.9323 |
| hybrid-e5-content-v1 | 0.6712 | 0.7770 | 0.6743 | 0.6771 | 0.8698 | 0.9167 |
| vector-e5-metadata-v1 | **0.7759** | **0.8644** | **0.7710** | **0.7969** | **0.9271** | **0.9635** |
| hybrid-e5-metadata-v1 | 0.6996 | 0.7970 | 0.6996 | 0.7083 | 0.8802 | 0.9427 |

## Primary confirmatory contrast

`hybrid-e5-metadata-v1 - hybrid-e5-content-v1`: ΔnDCG@10 = **+0.028359**, paired-bootstrap 95% CI **[+0.013399, +0.044078]**, Wilcoxon **p=0.000966736**, rank-biserial **0.3692**. Query directions: +68 / -38 / 0=86.

## Evidence drift

- chunk churn@10 = 0.2302
- chunk Jaccard@10 = 0.6550
- top-1 chunk change rate = 0.2604
- source churn@10 = 0.1037
- source Jaccard@10 = 0.8383
- relevant-evidence retention (rel>=2) = 0.9584
- Spearman(chunk churn, |nDCG delta|) rho = 0.3134, p = 9.56437e-06

## Planned secondary contrasts

- vector metadata − vector content: Δ=0.074541, 95% CI [0.042893, 0.108716], Wilcoxon p=1.1954e-05, Holm p=1.1954e-05, rank-biserial=0.4513.
- hybrid content − lexical: Δ=0.182076, 95% CI [0.143423, 0.220981], Wilcoxon p=2.82626e-17, Holm p=5.65252e-17, rank-biserial=0.8206.
- hybrid metadata − lexical: Δ=0.210434, 95% CI [0.170588, 0.250538], Wilcoxon p=2.8375e-20, Holm p=8.51249e-20, rank-biserial=0.8741.

Subgroup results are descriptive/bootstrap diagnostics as preregistered; see `confirmation_results.json` for full values.
