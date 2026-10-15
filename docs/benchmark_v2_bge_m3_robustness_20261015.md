# PiPi Benchmark V2 — BGE-M3 robustness result

Status: final post-hoc second-embedding-family robustness analysis after supplementary blinded judging.

## Judging closure

- 1,090 novel query–candidate pairs received final grades.
- 461 used exact S1/S2 consensus.
- 629 used fresh blinded Gemini adjudication.
- Final supplementary grades: 0=708, 1=210, 2=122, 3=50.
- BGE-M3 qrels coverage after extension: 7,680/7,680 top-10 slots.

## Overall retrieval quality

| Profile | nDCG@10 | MRR@10 | Recall@10 | Hit@1 | Hit@3 | Hit@10 |
|---|---:|---:|---:|---:|---:|---:|
| vector BGE-M3 content | 0.7393 | 0.8861 | 0.6872 | 0.8333 | 0.9375 | 0.9688 |
| vector BGE-M3 metadata | 0.8330 | 0.9345 | 0.7785 | 0.9010 | 0.9583 | 0.9896 |
| hybrid BGE-M3 content | 0.6686 | 0.8202 | 0.6567 | 0.7292 | 0.8854 | 0.9688 |
| hybrid BGE-M3 metadata | 0.7035 | 0.8501 | 0.6933 | 0.7708 | 0.9115 | 0.9792 |

## Metadata minus content

Vector BGE-M3:
- mean ΔnDCG@10 = 0.093699
- 95% bootstrap CI = [0.067815, 0.120893]
- Wilcoxon p = 1.468e-10
- rank-biserial = 0.6199
- positive / negative / ties = 99 / 43 / 50

Hybrid BGE-M3:
- mean ΔnDCG@10 = 0.034890
- 95% bootstrap CI = [0.021656, 0.048405]
- Wilcoxon p = 1.405e-07
- rank-biserial = 0.5632
- positive / negative / ties = 85 / 31 / 76

## Directional robustness conclusion

The metadata-sensitive retrieval effect retained the same positive direction under a second multilingual embedding family.

- Frozen E5 vector metadata−content ΔnDCG@10 = 0.074541
- BGE-M3 vector metadata−content ΔnDCG@10 = 0.093699
- Frozen E5 hybrid metadata−content ΔnDCG@10 = 0.028359
- BGE-M3 hybrid metadata−content ΔnDCG@10 = 0.034890

This is a post-hoc robustness analysis. It strengthens the evidence that the primary metadata-sensitive effect is not specific to the original E5 embedding backbone. It does not convert the BGE-M3 analysis into a preregistered confirmatory experiment.
