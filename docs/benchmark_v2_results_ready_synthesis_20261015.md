# PiPi Benchmark V2 — Results-ready synthesis

## RQ1 — Retrieval-profile design changes retrieval effectiveness

Across 192 frozen confirmation queries, hybrid metadata retrieval improved nDCG@10 over hybrid content retrieval by 0.0284 (95% bootstrap CI 0.0134 to 0.0441; Wilcoxon p=0.000967; rank-biserial=0.369). The vector metadata-versus-content contrast was larger, with ΔnDCG@10=0.0745.

## RQ2 — Retrieval provenance supports exact replay and exposes below-source evidence drift

Changing the hybrid retrieval profile produced 23.0% chunk churn at rank 10 and changed the top-ranked chunk for 26.0% of queries. Source-level churn was lower at 10.4%. Strict replay reproduced the exact ordered evidence set for 960/960 frozen retrieval runs, with 0 failures. Chunk churn was associated with the magnitude of the retrieval-quality change (Spearman ρ=0.313, p=9.56e-06).

## RQ3 — Retrieval evidence drift propagates to final answers

The preregistered Qwen primary endpoint identified material answer change in 22/192 queries (11.5%, Wilson 95% CI 7.7% to 16.7%). The replication rates were 11.5% for Ministral and 10.4% for Gemma. Same-evidence deterministic repeats were exact in 48/48 controls for every generator.

For Qwen, material drift occurred in 24.5% of queries when the top-ranked evidence chunk changed, compared with 7.0% when it remained stable (Fisher OR=4.31, p=0.00287). Ministral replicated this direction more strongly. Gemma showed a similar overall material-drift rate but weaker query-level churn association, indicating generator-specific sensitivity to changed evidence.

## RQ4 — Descriptive sensitivity patterns

Institutional documents showed the largest descriptive retrieval benefit from metadata-aware hybrid retrieval and the highest material-answer-drift rate for Qwen and Ministral. Cross-language queries also showed a larger descriptive metadata-retrieval gain than same-language queries. Material answer drift occurred even when the source-document set was unchanged but the selected chunks changed, supporting provenance below the source-document level.

## Claim boundary

The semantic-drift endpoint is symmetric. It establishes that the answer changed materially, not that the metadata-profile answer was necessarily more correct or better grounded. Groundedness/support remains a separate secondary question.
