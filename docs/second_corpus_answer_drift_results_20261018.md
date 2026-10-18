# C2 Qwen answer-drift extension — final results record

**Date:** 2026-10-18  
**Scientific status:** post-confirmatory descriptive context-feasible subset  
**Generator:** Qwen3-8B Q4_K_M  
**Role in the paper:** secondary answer-level propagation evidence after the frozen C2 retrieval confirmation

## Scope and boundary

The C2 confirmatory family remains H1/H2/H3 only. This answer-drift extension was defined after the frozen C2 retrieval results and must not be relabeled as confirmatory or preregistered.

The original C2 answer-drift plan reused the C1 generation contract exactly: Qwen3-8B Q4_K_M, reasoning off, temperature 0, top-p 1, seed 20261014, context size 16,384 and maximum output length 384 tokens. A token-count audit showed that 27 of 192 frozen retrieval conditions could not fit the unchanged context window. No evidence was truncated and the context window was not increased.

The V2 technical amendment therefore retained a query only when **both** frozen evidence conditions satisfied:

```text
input_tokens + 384 <= 16384
```

This produced 81 complete query pairs out of 96 frozen C2 queries, for **84.375% coverage**. Fifteen queries were excluded before V2 answer generation. The analyzed denominator is therefore 81, not 96.

Excluded queries by type were: relation/comparison 5, topic discovery 3, exact lookup 2, entity/dataset lookup 2, constraint-filtered lookup 2 and semantic paraphrase 1. By theme, exclusions were ECON 4, ENVI 2, HEAL 4 and TRAN 5.

## Frozen generation and judging chain

V2 generation completed all 162 required answers and froze before pair judging.

Key generation anchors:

- V2 answer-drift input SHA-256: `43af919a2b6321858e052f6e8dd0ca51a91d08c7ff4f6745153a9902655a824a`
- V2 input freeze SHA-256: `ec3bb5e56a4ab72639e299cdd4e2beaaf259808ff459408110fb2ac4dc94f5ed`
- context-exclusion record SHA-256: `191e7312cf7c53737f4967b2168b3a3a9558215f55fbfca0a6fcc9d3d57d21b7`
- context audit SHA-256: `4af1779c50cc05a7a688fb08014f1a3e7f60cdd37bea1a2ec2523ed3ba7937cc`
- Qwen GGUF SHA-256: `d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785`
- generated answers SHA-256: `c59a19c51cb05395cb4fbee23edb601f8f3b68e23940c14a54fbac5d434627b3`
- answer freeze SHA-256: `e03a321671b7e5f243d033ff506862c12c5b089ad2066a5b99711ed131df64ed`
- generation summary SHA-256: `c449e4ec0a9383a710cf9fa90d55bfce91f5f55f4be310a8f3bbef423761bbf7`

The 81 answer pairs were then deterministically blinded before judging. Profile identity remained hidden during all 81 judgments. The four-level rubric was unchanged from C1:

- 0 — semantically the same; wording-only differences
- 1 — minor difference; same substantive conclusion
- 2 — materially different content, support, qualification or conclusion
- 3 — substantially different or contradictory

Grades 2 and 3 define material answer drift.

Judging anchors:

- blinded packet SHA-256: `0a3be9a0824e20c658bf2a23af1a8711edf44ede948d0ff5135dcbe67e6f52aa`
- private A/B mapping SHA-256: `4adca69ad1f496536e967f7174d8214296686214aebc50ba0945ce31c2f93fbb`
- frozen judgments JSONL SHA-256: `61a82e092fc1ea62887061ada03c19c49fb4810332b8cb2a2f533e5acbd3b144`
- frozen judgments JSON SHA-256: `64ef877052b6892f5b2072d62181422d09b3bff2d9045059061fdedde9d23564`
- judgment freeze SHA-256: `ce42a2840e189a4efe8555550ae861f0d57a49ea227e9c9c8cfc285ed4280b20`

The judgment freeze explicitly preceded opening the private A/B mapping.

## Overall answer drift

Across the 81 context-feasible query pairs:

| Grade | Count |
|---|---:|
| 0 | 15 |
| 1 | 35 |
| 2 | 11 |
| 3 | 20 |

Material answer drift occurred in **31/81 = 38.27%** of pairs. The Wilson 95% interval is **28.45% to 49.16%**.

This is a semantic-change endpoint. It establishes that the two frozen retrieval conditions produced materially different answers. It does **not** establish that one profile produced a more correct answer.

## Theme breakdown

| Theme | Material | n | Rate |
|---|---:|---:|---:|
| ECON | 11 | 20 | 55.0% |
| ENVI | 4 | 22 | 18.2% |
| HEAL | 9 | 20 | 45.0% |
| TRAN | 7 | 19 | 36.8% |

These subgroup values are descriptive only.

## Query-type breakdown

| Query type | Material | n | Rate |
|---|---:|---:|---:|
| semantic paraphrase | 9 | 15 | 60.0% |
| topic discovery | 7 | 13 | 53.8% |
| exact lookup | 5 | 14 | 35.7% |
| entity/dataset lookup | 4 | 14 | 28.6% |
| relation/comparison | 3 | 11 | 27.3% |
| constraint-filtered lookup | 3 | 14 | 21.4% |

Because context feasibility excluded query types unevenly, these values should not be generalized to the full 96-query design without qualification.

## Hidden-drift answer propagation

The frozen C2 retrieval analysis already showed that dataset-level stability can coexist with chunk-level evidence change. The answer-level join uses the frozen per-query retrieval metrics file with SHA-256:

`794be7b504060580910fbc7f8e13274c604cfbdcffaa33781c333b7ad7e94b0b`

Two definitions are reported.

### Directional frozen definition

For queries satisfying:

```text
dataset churn@10 = 0
chunk churn@10 > 0
```

24 of the 81 answer-evaluable queries met the condition. **9/24 = 37.50%** produced material answer drift. The Wilson 95% interval is **21.16% to 57.29%**.

The full 96-query C2 retrieval set contains 27 such cases, so 24/27 of them remained in the context-feasible answer subset.

### Strict identical-dataset-set definition

A stricter operational definition requires:

```text
dataset Jaccard@10 = 1
chunk churn@10 > 0
```

This guarantees the retrieved dataset set is exactly unchanged while the specific chunk evidence differs. Nineteen answer-evaluable queries met this condition. **9/19 = 47.37%** produced material answer drift. The Wilson 95% interval is **27.33% to 68.29%**.

This is the clearest C2 demonstration of hidden evidence drift: coarse dataset-level provenance can identify the executions as source-stable while finer evidence changes survive to the generated answer.

Only two answer-evaluable queries had both dataset Jaccard@10 = 1 and chunk Jaccard@10 = 1; neither produced material answer drift. This n=2 comparison is too small for inference.

## Exploratory association with churn magnitude

Across the 81 answer-evaluable queries, chunk churn and ordinal answer grade had:

- Spearman rho = **0.199**
- two-sided p = **0.0744**

Mean chunk churn was **0.416** for material-answer cases and **0.366** for non-material cases.

This exploratory association is not statistically strong and is not a frozen C2 mechanism endpoint. Together with the unsupported frozen H2 multiplicity test, it suggests that simple drift magnitude or source multiplicity alone is insufficient to explain answer propagation. Which evidence changes, its ranking position, redundancy and query alignment remain plausible mechanisms for later work.

## C1 descriptive context

The frozen C1 Qwen endpoint produced material answer drift in **22/192 = 11.46%** of queries. C2 produced **31/81 = 38.27%** in the context-feasible subset, a descriptive difference of +26.81 percentage points.

No cross-corpus answer-drift significance test is reported. C1 and C2 differ in corpus construction, evidence content, retrieval-drift magnitude and answer-evaluable selection. The defensible cross-corpus statement is that answer-level propagation was also observed in C2 and was descriptively larger under the higher C2 retrieval drift.

The strict hidden-drift pattern also reproduced qualitatively: C1 had material Qwen drift in 10/70 cases with an unchanged dataset set and changed chunk set, while C2 had 9/19 in the context-feasible subset. These magnitudes are descriptive and are not treated as a formal cross-corpus effect-size comparison.

## Publication and redistribution boundary

Raw answer files and raw evidence contexts can contain third-party text and remain local artifacts. The public repository should expose:

- configs and frozen technical amendments
- generation, blinding and reporting code
- hashes of local frozen artifacts
- aggregate publication-safe results

It should not assume redistribution rights for source evidence merely because the source was publicly accessible.

Relevant source-controlled files:

- `docs/second_corpus_c2_answer_drift_extension_v1.md`
- `docs/second_corpus_c2_answer_drift_context_feasible_amendment_v2.md`
- `config/second_corpus_answer_drift_qwen_v1.json`
- `config/second_corpus_answer_drift_qwen_v2_context_feasible.json`
- `scripts/second_corpus_answer_drift_context_audit_v1.py`
- `scripts/second_corpus_prepare_answer_drift_v2_context_feasible.py`
- `scripts/second_corpus_run_answer_drift_qwen_v2.py`
- `scripts/second_corpus_prepare_answer_drift_judging_v2.py`
- `scripts/second_corpus_answer_drift_reporting_v2.py`

The reporting script recomputes publication-safe aggregate results from the locally frozen blinded packet, private mapping, judgments and per-query retrieval metrics while emitting no answer or evidence text.

## Reporting guardrails

Do not report this extension as:

- a C2 confirmatory endpoint
- an estimate over all 96 C2 queries without the context-feasible qualification
- evidence that metadata retrieval is necessarily more accurate
- proof of corpus-independent, embedding-independent or generator-independent behavior
- a successful confirmation of the frozen H2 multiplicity mechanism

A concise paper-level formulation is:

> In the context-feasible C2 answer subset, 24 of 81 queries exhibited chunk-level evidence drift despite zero dataset-level churn, and 9 of these 24 cases (37.5%) produced materially different answers. Under the stricter condition that the retrieved dataset set was exactly unchanged (dataset Jaccard@10 = 1), chunk-level evidence still changed for 19 queries, of which 9 (47.4%) produced materially different answers.
