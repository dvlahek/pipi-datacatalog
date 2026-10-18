# Second-corpus human answer-drift audit V1

**Status:** FROZEN BEFORE ANY C2 HUMAN RATINGS  
**Date:** 2026-10-18  
**Scientific status:** post-hoc human validation of the already-frozen C2 answer-drift endpoint; H1/H2/H3 and the frozen LLM judgments remain unchanged

## Motivation

The C2 answer-drift endpoint was judged under blinded model-based judging and was robust across additional LLM judges. This human audit tests whether the semantic-change endpoint is also supported by human assessment. It is a validation analysis, not a replacement endpoint and not a new confirmatory hypothesis.

## Assessors

The C2 audit uses **three blinded human raters**:

1. colleague 1
2. colleague 2
3. the study author

All three rate every sampled pair separately. The two colleagues and the author must not discuss individual pairs until all three completed files have been returned and frozen.

Because one rater is the study author, the manuscript must not describe all three as independent external assessors. The primary report therefore includes a three-rater consensus and a colleague-only sensitivity analysis. It also reports how many binary material/non-material cases have disagreeing colleague votes and are consequently decided by the author's third vote.

## Sampling frame

The sampling frame is the frozen 81-pair context-feasible Qwen3-8B C2 answer set.

The audit sample is fixed before ratings as:

- **all 19 strict hidden-drift pairs** satisfying `dataset Jaccard@10 = 1` and `chunk churn@10 > 0`
- **25 control pairs** selected deterministically without replacement from the remaining 62 context-feasible pairs
- **44 pairs total**

The deterministic sampling seed is:

`SECOND_CORPUS_C2_HUMAN_AUDIT_V1`

The 25 controls are selected by ascending SHA-256 of `seed|CONTROL|pair_id`. The final 44-pair presentation order is determined by ascending SHA-256 of `seed|ORDER|pair_id`.

The 19 strict hidden-drift cases are therefore a census of the answer-evaluable strict-hidden stratum, not a random sample from it. The 25 controls are included to assess judge agreement/calibration and must not be used as an unweighted prevalence estimate for the full 81-query answer set.

## Blinding

Each rater receives only:

- an audit ID
- the query
- Answer A
- Answer B
- an empty 0-3 grade field
- an optional notes field

The rater packet does **not** expose:

- retrieval-profile identity
- content-vs-metadata condition identity
- query ID or pair ID
- strict-hidden vs control stratum
- prior ChatGPT, Gemini, or Claude grades
- aggregate C2 answer-drift results
- retrieval churn values

A/B orientation is inherited from the already-frozen C2 blinded packet. The private audit sampling manifest remains local until all human ratings are frozen.

## Rating rubric

The same frozen semantic-change scale is used:

- **0** — semantically the same; wording-only differences
- **1** — minor difference; same substantive conclusion
- **2** — materially different content, support, qualification, or conclusion
- **3** — substantially different or contradictory

Grades 2 and 3 are material answer drift. The task is to assess semantic change between Answer A and Answer B, not to decide which retrieval profile is better or which answer is more correct.

## Frozen analysis

For each of the 44 pairs:

- three-rater ordinal consensus = median of the three 0-3 grades
- material consensus = at least two of three raters give grade 2 or 3

The analysis reports:

- three-rater consensus grade distribution
- three-rater material count/rate for all 44 audited pairs
- three-rater material count/rate for the complete 19-case strict-hidden stratum
- pairwise exact agreement, within-one agreement, quadratic weighted kappa, and binary material agreement
- colleague-1 vs colleague-2 agreement separately
- number of cases where the two colleagues disagree at the material/non-material threshold and the author vote therefore determines three-rater material consensus
- agreement of the three-rater consensus with the already-frozen primary C2 LLM grade, including exact agreement, within-one agreement, quadratic weighted kappa, binary agreement, and a 2x2 material/non-material table
- the same human-vs-LLM comparison within the 19 strict-hidden cases

No alternative consensus rule will be substituted after ratings are seen.

## Ethics and participation record

For the earlier C1 human audit, the assessor pool consisted of the study author, two colleagues, and seven students. According to the author-supplied study record, participants gave oral consent and were not paid or otherwise compensated. Formal ethics approval was not sought. The manuscript must report these facts accurately and must not claim a formal ethics exemption unless such a determination exists.

For this new C2 audit, the two colleague raters should be told that their participation is voluntary, that their anonymized ratings may be reported in the research, and that they may decline. Consent should be documented before rating. No assessor names are stored in the public repository.

## Frozen input anchors

- C2 blinded answer packet SHA-256: `0a3be9a0824e20c658bf2a23af1a8711edf44ede948d0ff5135dcbe67e6f52aa`
- C2 per-query retrieval metrics SHA-256: `794be7b504060580910fbc7f8e13274c604cfbdcffaa33781c333b7ad7e94b0b`
- frozen C2 primary judgments SHA-256: `61a82e092fc1ea62887061ada03c19c49fb4810332b8cb2a2f533e5acbd3b144`

All generated human-audit packets and ratings remain local because answer text may contain third-party material. Publication-safe aggregate summaries may be committed after analysis.
