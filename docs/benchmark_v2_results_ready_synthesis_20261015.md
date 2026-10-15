# PiPi Benchmark V2 — Results-ready synthesis with BGE-M3 robustness

## RQ1 — Retrieval-profile design changes retrieval effectiveness

Across 192 frozen confirmation queries, hybrid metadata retrieval with the preregistered E5 backbone improved nDCG@10 over hybrid content retrieval by 0.0284 (95% bootstrap CI 0.0134 to 0.0441; Wilcoxon p=0.000967; rank-biserial=0.369). The vector metadata-versus-content contrast was larger, with ΔnDCG@10=0.0745.

A post-hoc second-backbone robustness analysis repeated the same representation comparison using BGE-M3 while preserving the frozen corpus, confirmation query set, evaluation depth, representation definitions, source/file diversity rule, and RRF parameters. The metadata-sensitive effect retained the same positive direction for both vector retrieval (ΔnDCG@10=0.0937, 95% CI 0.0678 to 0.1209, Wilcoxon p=1.468e-10) and hybrid retrieval (ΔnDCG@10=0.0349, 95% CI 0.0217 to 0.0484, Wilcoxon p=1.405e-07). This robustness result does not replace the preregistered E5 analysis and is reported separately as post-hoc evidence that the representation effect is not specific to one embedding family.

## RQ2 — Retrieval provenance supports exact replay and exposes below-source evidence drift

Changing the frozen E5 hybrid retrieval profile produced 23.0% chunk churn at rank 10 and changed the top-ranked chunk for 26.0% of queries. Source-level churn was lower at 10.4%. Strict replay reproduced the exact ordered evidence set for 960/960 frozen retrieval runs, with 0 failures. Chunk churn was associated with the magnitude of the retrieval-quality change (Spearman ρ=0.313, p=9.56e-06).

The BGE-M3 robustness analysis showed the same qualitative distinction between chunk-level and source-level change. For the hybrid comparison, metadata versus content produced 19.9% chunk churn, changed the top-ranked chunk for 13.5% of queries, and produced 11.8% source churn under the frozen drift definitions. This again shows that source-level summaries can hide larger changes in the specific evidence chunks supplied downstream.

## RQ3 — Retrieval evidence drift propagates to final answers

The preregistered Qwen primary endpoint identified material answer change in 22/192 queries (11.5%, Wilson 95% CI 7.7% to 16.7%). The replication rates were 11.5% for Ministral and 10.4% for Gemma. Same-evidence deterministic repeats were exact in 48/48 controls for every generator.

For Qwen, material drift occurred in 24.5% of queries when the top-ranked evidence chunk changed, compared with 7.0% when it remained stable (Fisher OR=4.31, p=0.00287). Ministral replicated this direction more strongly. Gemma showed a similar overall material-drift rate but weaker query-level churn association, indicating generator-specific sensitivity to changed evidence.

## RQ4 — Descriptive sensitivity patterns

Institutional documents showed the largest descriptive retrieval benefit from metadata-aware hybrid retrieval in the frozen E5 experiment and the highest material-answer-drift rate for Qwen and Ministral. In the BGE-M3 robustness analysis, the hybrid metadata advantage was again largest for institutional documents (+0.0889 nDCG@10), followed by software documentation (+0.0470), structured data (+0.0182), and a small negative descriptive difference for open-data catalogs (-0.0145). These BGE subgroup values are descriptive and were not preregistered.

## Robustness interpretation

The second embedding family strengthens the main retrieval result without changing its evidential status. The primary confirmatory claims remain tied to the frozen E5 protocol. BGE-M3 is a post-hoc robustness analysis added after the primary experiment to test sensitivity to the embedding backbone. The direction of the metadata-sensitive effect was retained for both vector and hybrid retrieval, with confidence intervals fully above zero.

## Claim boundary

The semantic-drift endpoint is symmetric. It establishes that the answer changed materially, not that the metadata-profile answer was necessarily more correct or better grounded. Groundedness/support remains a separate secondary question.

The study still evaluates one deployed heterogeneous Data Space corpus. The second-backbone analysis addresses embedding-model dependence, but it does not establish corpus-independent generalization.
