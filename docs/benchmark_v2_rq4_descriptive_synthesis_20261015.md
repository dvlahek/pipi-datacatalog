# RQ4 descriptive synthesis

RQ4 is descriptive. No subgroup result was used to change a retrieval profile, prompt, model, threshold, or benchmark.

## Retrieval-profile sensitivity

The institutional-document family showed the largest metadata-aware hybrid gain, with ΔnDCG@10=0.1037. The other source-family changes were much smaller: software documentation 0.0110, open-data catalogs 0.0013, and structured data -0.0025.

By query type, the largest descriptive metadata gains occurred for entity/document lookup (0.0465) and relation/comparison (0.0450). Cross-language queries showed ΔnDCG@10=0.0409, compared with 0.0242 for same-language queries.

## Answer-drift sensitivity

Institutional documents also showed the highest material-answer-drift rate for the Qwen primary endpoint (22.9%) and Ministral replication (22.9%). Gemma showed 16.7% for the same family.

Top-ranked evidence changes were associated with higher material-drift rates in every generator: Qwen 24.5% versus 7.0%, Ministral 28.6% versus 5.6%, and Gemma 18.4% versus 7.7%. The Gemma contrast was weaker and borderline in its model-specific Fisher test.

## Provenance below source level

For the Qwen primary endpoint, 8/64 queries with an unchanged source set but changed chunks produced material answer drift. This supports recording concrete chunk identities and their ordered selection, not only the source-document identity.

## Cross-generator heterogeneity

Material drift occurred in at least one generator for 46/192 queries, in at least two generators for 13/192, and in all three for 5/192. The overall material-drift rate was similar across the three generators, but the affected query set was not identical. This indicates generator-specific sensitivity to changed retrieval evidence.
