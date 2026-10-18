# PiPi Benchmark V2 — ONE-CHAT MAIN HANDOFF
Date: 2026-10-13
Project: PiPi / pipi-datacatalog
Repository: dvlahek/pipi-datacatalog
Branch: feature/sensor-hub-bootstrap
PR: #1 remains open/draft/unmerged. DO NOT MERGE without explicit user approval.

## CRITICAL ONE-CHAT TRANSITION RULE

The user wants ONE new chat only.

That one new chat must be used in two stages:

### Stage A — FIRST, independent confirmation Pass 2
Before the new chat sees this full handoff, Pass-1 material, development results, GitHub history, or any full archive, give it ONLY:
1. `PIPI_V2_PASS2_NEW_CHAT_PROMPT.md` / the repo fresh-context instructions
2. the frozen blinded Pass-2 JSON

It must grade all 2252 query–candidate pairs independently, return the frozen Pass-2 judgments JSON, and compute its SHA-256.
It MUST NOT compute retrieval-quality metrics and MUST NOT compare against Pass 1.

This preserves the intended independent replicate. The frozen Pass-2 input is:
- case_count = 48
- candidate_count = 2252
- pass2_blinded_input_sha256 = `0c1dd9bd553e4159aa33493dd0c44383c344b7c7e232a91203c206d26481f0f9`
- candidate order rule = `pipi-v2-confirmation-pass2-v1`
- Pass-1 grades invisible
- quality metrics not computed

The repo fresh-context instruction is:
`docs/retrieval_benchmark_v2_confirmation_pass2_fresh_context.md`

### Stage B — SAME CHAT, after Pass 2 is frozen
Only after the new chat has produced the complete Pass-2 judgment artifact + SHA, give that SAME chat this full handoff / full archive and continue the main project there.

Do not create a second chat.

After unlocking full context:
1. validate Pass 2 against the frozen input hash and exact 2252 candidate IDs
2. compare Pass 1 vs Pass 2 only for the preassigned 48 replicate queries
3. compute replicate consistency: exact agreement, within-one-grade agreement, quadratic-weighted Cohen kappa, 4×4 confusion matrix
4. create Pass 3 input ONLY for actual Pass1/Pass2 disagreements
5. Pass 3 is a fresh blinded adjudication of disagreement candidates only
6. final grade for disagreement = median(Pass1, Pass2, Pass3), as frozen in Amendment 4
7. freeze final confirmation qrels + SHA
8. ONLY THEN compute/open confirmatory retrieval-quality and drift results

Never expose the full archive to the Pass-2 judge before Stage A is finished.

---

# 1. RESEARCH THESIS / ARTICLE DIRECTION

Working thesis:
**Retrieval is part of provenance: versioned retrieval profiles for reproducible RAG over evolving heterogeneous Data Spaces.**

Stronger form:
**RAG reproducibility requires retrieval provenance. Data provenance alone is insufficient if the retrieval configuration that selected the evidence is not itself versioned/provenanced.**

Possible titles:
- The Missing Provenance Layer in RAG: Versioned Retrieval Profiles for Evolving Data Spaces
- Retrieval Is Part of the Provenance: Reproducible RAG over Evolving Data Spaces

Preferred journal direction:
1. IEEE TKDE
2. The VLDB Journal if systems/provenance/versioning emphasis dominates
3. ACM TOIS if IR emphasis dominates
4. Information Systems fallback

Do not make novelty claims such as first RAG for Data Spaces or first metadata-aware RAG.
RAG4DS (2025), MCompassRAG (2026), VersionRAG/ReproRAG and related work constrain novelty.

Novelty to protect:
**retrieval configuration as a first-class immutable provenance artifact tied to execution/replay over evolving heterogeneous Data Spaces.**

Useful RQs:
- RQ1: To what extent does retrieval-profile design alter evidence selection under fixed data and embedding models?
- RQ2: Can versioned retrieval provenance identify and reproduce evidence-set drift?
- RQ3: How much retrieval-profile drift propagates into downstream answer drift?
- RQ4: Which query/source characteristics make RAG sensitive to retrieval-profile changes?

Long-term decomposition:
same data + same LLM + different retrieval profile -> retrieval-induced drift
same retrieval + same LLM + different data version -> data-induced drift
same data + same retrieval + different LLM -> generation-induced drift

Provenance chain:
query
 -> immutable RetrievalProfile + hash
 -> catalog/dataset snapshot
 -> specific chunk versions / embedding representations
 -> candidate ranks + fusion/diversity
 -> final evidence set + context/evidence hash
 -> later LLM run
 -> answer

---

# 2. REPO / OPERATING CONSTRAINTS

Repo: `dvlahek/pipi-datacatalog`
Branch: `feature/sensor-hub-bootstrap`
Base: `main`
PR #1 open/draft. Do not merge without explicit user approval.

Current branch HEAD at handoff:
`6e4a7d473cd6e6102530721c9e90571b688a63cc`
message: `Record local V2 handoff archive hashes`

CI for this HEAD:
GitHub Actions run #473, completed SUCCESS.

Important current commits near the confirmation judging boundary:
- `ae78e8ce6dee4ada26b34fd288c75c9bf4cec6d6`
  `Record V2 confirmation pass-1 judgment manifest`
- `9c0493f943db131282395f81619bf5b8d274cdc1`
  `Freeze V2 confirmation replicate pass-2 input`
- `64fbfec6f902c0fd71babdcc3c2350fe2d5e0fae`
  `Record V2 Pass-2 fresh-context handoff`
- `6e4a7d473cd6e6102530721c9e90571b688a63cc`
  `Record local V2 handoff archive hashes`

Do not rewrite old scientific/protocol commits or relabel old outcomes.

Windows repo:
`C:\Develope\PIPI\pipi-datacatalog`

Use Python without venv activation:
`.\.venv\Scripts\python.exe ...`

Docker/Postgres:
- Docker Desktop / WSL2
- pgvector image `pgvector/pgvector:pg17`
- container `pipi-datacatalog-postgres`
- host port 5433 -> container 5432
- pgvector 0.8.7
- expected DB URL:
  `postgresql+psycopg://pipi:pipi_dev@127.0.0.1:5433/pipi_catalog`
- migrations 001–008 applied

Do not ask for or expose secrets/tokens/passwords.

---

# 3. DATA / ARCHITECTURE

PiPi is a compact semantic metadata catalog / Data Space, not a claim of full IDS/Gaia-X implementation.

Metadata standards:
DCAT / DCAT-AP primary, SOSA/SSN, QUDT, SKOS, Schema.org, minimal PiPi custom vocabulary.

Source families in Benchmark V2:
1. structured-data
2. software-documentation
3. institutional-documents
4. open-data-catalogs

Frozen V2 corpus:
- catalog snapshot:
  `068e1b0df74acd8b91d04a5161f4413d57d07bfef5c8c9ce2b8d1100ae780419`
- corpus fingerprint:
  `f04239fe6df52ab2604ab45a8c08cc83d5bafe79203a4b16c20a2d2a307e2dc6`
- base protocol SHA:
  `d277465bb9572bf6bbff82a5d5bf6f29fd1d9ebd9a5b9940d890d87b87df2dde`
- datasets: 274
- chunks: 3974

Approx family counts at freeze:
- structured: 33 datasets / 35 chunks
- software: 1 dataset / 1546 chunks / 100 unique file paths
- institutional: 40 datasets / 2163 chunks
- open-data: 200 datasets / 230 chunks

Important reproducibility caveat:
The exact current open-data cohort is frozen and identifiable by manifest/fingerprint.
Future fresh re-harvesting of “first 200” is not guaranteed to recreate the same cohort because upstream ordering may be nondeterministic.
Do not claim full from-scratch regeneration until deterministic upstream selection or frozen cohort-by-ID is implemented.

---

# 4. RETRIEVAL PROFILES — IMMUTABLE

Profiles and hashes:

`lexical-v1`
`4234a9a6691d7f0c004eb7b6469662675db35f66fe04dd8eb5b053b1d7a31a54`

`vector-e5-content-v1`
`8c00e6326839a8e0e798083197225d1fd90b60db7d6a9e974fe8667de5f0562f`

`hybrid-e5-content-v1`
`04fd11fb3c56e9273f7b312a376d5c975a852489276f87fc796f7e0c716f7a45`

`vector-e5-metadata-v1`
`e250344e567f85c3dc8ac36b0cd68663f570e322bed7686de99a270ffa0e1628`

`hybrid-e5-metadata-v1`
`7b63711593b091d1c21a1548f1b672f4572c69b4fca380779114cad6163211e4`

Neural retrieval:
- `intfloat/multilingual-e5-small`
- 384 dimensions
- query/passages use E5 prefixes
- normalized vectors

Hybrid:
- lexical + exact pgvector cosine
- RRF v1, k=60
- deterministic ties
- source/file soft cap = 2
- do NOT tune these after seeing benchmark outcomes

`content-v1` embeds stored chunk text.
`metadata-v1` prepends dataset title and optional file path to content.
Stored metadata-first chunks may already contain metadata and metadata-v1 can repeat title; document this, do not silently change profile semantics.

---

# 5. HISTORICAL PILOTS

## P0 exact profile comparison, 16-query pilot
Historical results:
lexical-v1:
Hit@1=.688 Hit@3=.875 Hit@10=1.000 MRR=.799

vector-e5-content-v1:
Hit@1=.688 Hit@3=.938 Hit@10=1.000 MRR=.818

hybrid-e5-content-v1:
Hit@1=.812 Hit@3=1.000 Hit@10=1.000 MRR=.906

vector-e5-metadata-v1:
Hit@1=.562 Hit@3=.812 Hit@10=.938 MRR=.703

hybrid-e5-metadata-v1:
Hit@1=.875 Hit@3=.938 Hit@10=1.000 MRR=.912

These were pilot diagnostics, not the confirmatory V2 result.

## P1 evidence drift, same 16 queries
hybrid content vs metadata top10:
chunk retention = .750
chunk churn = .250
chunk Jaccard = .625
top1 chunk change = .3125
mean rank shift shared ~1.7673

source retention = 1.000
source churn = 0
source Jaccard = .953
top1 source change = .062

Interpretation:
chunk evidence can drift substantially while source documents remain stable.

## P2 strict replay
Exact ordered evidence replay:
`STRICT_REPLAY_PASS`
retention@10=1
churn@10=0
Jaccard@10=1
mean rank shift=0

This is a controlled mechanism proof, not broad statistical evidence.

---

# 6. BENCHMARK V2 BASE PROTOCOL

`config/rag_benchmark_v2_protocol.json`, revision 2.

Total 240 queries:
- dev = 48
- confirmation = 192

Each source family:
- 12 dev
- 48 confirmation
- 60 total

Six query types:
- exact-lookup
- semantic-paraphrase
- topic-discovery
- entity-document-lookup
- relation-comparison
- constraint-filtered-lookup

Each type:
- 8 dev
- 32 confirmation
- 40 total

24 family × query-type cells:
- 2 dev
- 8 confirmation

Cross-language:
- dev 24
- confirmation 48
- total 72

Relevance scale:
- 3 direct / decisive evidence
- 2 clearly useful support, incomplete alone
- 1 topical but weak/insufficient
- 0 irrelevant

Pooling:
top20 from all five profiles, deduplicated, plus frozen authoring evidence seeds under Amendment 2.

Statistics planned:
- primary nDCG@10
- MRR / Recall@10 / Hit@1,3,10
- paired bootstrap 10k
- Wilcoxon on paired nDCG@10
- rank-biserial effect size
- Holm adjustment for planned secondary comparisons
- subgroup descriptive/bootstrap diagnostics
- Spearman drift-quality association

Confirmation is confirmatory; development is diagnostic.

---

# 7. AMENDMENTS / JUDGING

Amendment 2:
Top20 profile union plus frozen retrieval-blind authoring evidence seeds.
Seeds are NOT automatic relevance labels.
Retrieval ranks are never modified by seed augmentation.

Amendment 3:
Development qrels can use blinded LLM judging and must not be described as human annotation.

Amendment 4:
Confirmation judging procedure was frozen BEFORE confirmation authoring/retrieval:
- blinded GPT-5.6 Sol
- same 0–3 ordinal scale
- profile identity/rank/score/seed status/target hints hidden
- all 192 get Pass 1
- 48 preassigned replicate queries get independent Pass 2
- if Pass1 != Pass2, fresh blinded Pass3 only for disagreements
- final disagreement grade = median(P1,P2,P3)
- report exact agreement, within-one-grade agreement, quadratic-weighted Cohen kappa, 4×4 grade confusion matrix
- call this replicate-judge consistency, not human inter-annotator agreement

Preassigned replicate queries:
cell positions 1 and 3 in every one of the 24 family × query-type cells.

---

# 8. DEVELOPMENT SET — COMPLETE DIAGNOSTIC PHASE

Frozen dev query-set SHA:
`c60d2f6083873bb76591ffdd10d19cfe32f4900c20a4117ca39ecc3d2c40b4e9`

48 dev queries, frozen retrieval-blind.

Development initial retrieval:
48 × 5 = 240 runs.

A2 development pool:
- before 2300 candidates
- 80 resolved seed specs
- 79 unique seed candidates
- 66 already present
- 14 added
- 8 queries received added seeds
- after 2314 candidates
- automatic grades = 0
- ranks modified = no

Development LLM judgment artifact:
2314 candidates
grade counts:
- 0 = 1918
- 1 = 194
- 2 = 121
- 3 = 81

Development overall metrics:
lexical-v1:
nDCG@10 .3917
MRR .4242
Recall@10 .4200
Hit@1 .3750
Hit@3 .4375
Hit@10 .5625

vector-e5-content-v1:
nDCG@10 .6736
MRR .7723
Recall@10 .6817
Hit@1 .7292
Hit@3 .7917
Hit@10 .8958

hybrid-e5-content-v1:
nDCG@10 .5907
MRR .6461
Recall@10 .6433
Hit@1 .5208
Hit@3 .7292
Hit@10 .8125

vector-e5-metadata-v1:
nDCG@10 .7249
MRR .8134
Recall@10 .7200
Hit@1 .7708
Hit@3 .8542
Hit@10 .8750

hybrid-e5-metadata-v1:
nDCG@10 .6087
MRR .6630
Recall@10 .6543
Hit@1 .5625
Hit@3 .7292
Hit@10 .8333

Preregistered primary development contrast:
hybrid content -> hybrid metadata
.5907 -> .6087
mean delta +.0180
95% paired bootstrap CI [-.0110, +.0508]
Wilcoxon p=.2691
rank-biserial +.243

Interpretation:
small positive development signal, not confirmatory, CI crosses zero.

Development primary drift:
chunk churn@10 = .235
top1 chunk change = .208
source churn@10 = .154
top1 source change = .125
relevant evidence retention grades2-3 = .936

This supports the central provenance story:
retrieval-profile changes can alter evidence membership substantially while relevance metrics and retained relevant evidence change less.

Do NOT tune profiles from these development results.

---

# 9. CONFIRMATION QUERY SET — FROZEN

192 queries, authored retrieval-blind.

Confirmation query-set SHA:
`c725fba20382b6d7707b0f1b9bfaba8ac131ebb9c0a461ce7ab4a8988bc26ed5`

Structure:
- 48 structured-data
- 48 software-documentation
- 48 institutional-documents
- 48 open-data-catalogs
- 32 of each query type
- 48 cross-language
- 144 same-language
- 48 preassigned replicate queries

Authoring artifact explicitly states retrieval output was not inspected during confirmation authoring.

---

# 10. CONFIRMATION RETRIEVAL — FROZEN

192 queries × 5 profiles = 960 retrieval runs.
Depth 20 per profile.

The retrieval ledger is publication-safe and contains no chunk text.
Initial annotation pool contains chunk text and is not publication-safe.

All identity checks use:
snapshot `068e1b...`
corpus `f04239...`
base protocol `d27746...`
confirmation set `c725fb...`

---

# 11. CONFIRMATION A2 POOL — FROZEN BEFORE JUDGING

Initial pooled candidates:
9146

A2 augmentation:
- resolved seed specs = 262
- unique seed candidates across confirmation = 146
- seed specs already present = 238
- seed candidates added = 24
- cases with added seeds = 15
- final candidates = 9170
- automatic relevance grades assigned = 0
- retrieval ranks modified = NO
- quality metrics computed = NO

Final augmented confirmation pool SHA:
`04e8a7b25d0a38d8412d6e2e7ff91887848d1ce04943f6e2c20b0cea605f1a4c`

Input unaugmented pool SHA:
`cb25ae1a315df2f3652c6d23b81a6d1624f93350aeb546a4716bc11082a07ded`

---

# 12. CONFIRMATION PASS 1 — COMPLETE AND SEALED

Pass-1 blinded input:
- 192 cases
- 9170 candidates
- SHA:
`6f47c16eb59de2179c1d300e6c2e9ab929f858ea5ae4d6896fbaed977b46655d`

Pass-1 criteria SHA:
`3020848ef8f388103d31e5117f2d7686f77571ce87e6b1297e6f9f85dc898f37`

Pass-1 judgments SHA:
`85ced352b8a7dce34465718895a1c418966df6568d7fd467c88673b01135e8af`

Pass-1 qrels TSV SHA:
`65d404e14c60b34b1135c1a8afcb521a58c8485dba2719e6df5c587d8a8049b9`

Pass-1 grade counts:
- 0 = 7760
- 1 = 532
- 2 = 656
- 3 = 222

Judge label:
`OpenAI GPT-5.6 Sol blinded deterministic criteria-assisted pass`

CRITICAL:
No confirmation retrieval-quality metrics were computed before Pass 1 was frozen.
Do not expose these Pass-1 values to the independent Pass-2 judge.

Repo manifest:
`data/benchmark_v2/confirmation_pass1_judgment_manifest_c725fba20382.json`

Commit:
`ae78e8ce6dee4ada26b34fd288c75c9bf4cec6d6`

---

# 13. CONFIRMATION PASS 2 — NEXT SCIENTIFIC ACTION

Frozen Pass-2 input:
- exactly the 48 preassigned replicate queries
- 2252 query–candidate pairs
- Pass-1 grades hidden
- no quality metrics
- new deterministic blinded order

Pass-2 input SHA:
`0c1dd9bd553e4159aa33493dd0c44383c344b7c7e232a91203c206d26481f0f9`

Repo manifest:
`data/benchmark_v2/confirmation_pass2_input_manifest_c725fba20382.json`

Commit:
`9c0493f943db131282395f81619bf5b8d274cdc1`

Fresh-context instructions:
`docs/retrieval_benchmark_v2_confirmation_pass2_fresh_context.md`

Commit:
`64fbfec6f902c0fd71babdcc3c2350fe2d5e0fae`

Exact fresh Pass-2 instruction:
Use ONLY the attached blinded Pass-2 JSON as evidence.
Do not use memory, prior chats, retrieval rankings, profile identities, target identifiers, authoring-seed status, or previous grades.

Grade all 2252 pairs:
3 = direct/decisive
2 = clearly useful support, incomplete alone
1 = topical but insufficient
0 = irrelevant

For relation/comparison queries, evidence that clearly supports one side can receive 2.
Grade 3 only when the candidate directly satisfies the information need on its own.

Return:
artifact = `pipi-benchmark-v2-confirmation-pass2-judgments`
pass2_blinded_input_sha256 = exact frozen hash
case_count = 48
candidate_count = 2252
judgments = flat array containing:
case_id
candidate_id
dataset_identifier
dataset_version
chunk_index
judgment

Do NOT compute retrieval-quality metrics.
Do NOT compare with Pass 1.

---

# 14. LOCAL HANDOFF ARCHIVE PROVENANCE

The repo records the already-created local backup archive hashes:

Full archive:
`PIPI_V2_FULL_HANDOFF_ARCHIVE_20261013.zip`
SHA256:
`7bfa6e5268312d58246ad8f4eff6fdfcdac628170e660eb652299d0f5238c6cc`
size:
16482376 bytes

Fresh Pass-2 package:
`PIPI_V2_PASS2_FRESH_JUDGE_PACKAGE_20261013.zip`
SHA256:
`75306663af232410d9e1ce5364ab2dfd0e26d247e1d8e1e44a33d83a01e5aa90`
size:
863406 bytes

Full archive manifest:
`PIPI_V2_FULL_HANDOFF_ARCHIVE_MANIFEST_20261013.json`
SHA256:
`63584a02bb08b0c03939ce6c447e5dcf958162445d134fe7f292cea880a370d6`

Repo record:
`data/benchmark_v2/local_handoff_archive_reference_20261013.json`

Commit:
`6e4a7d473cd6e6102530721c9e90571b688a63cc`

The full archive contains sealed Pass-1 material.
It MUST NOT be exposed before Pass 2 is completed.

---

# 15. FILES THE NEW MAIN CHAT SHOULD INSPECT AFTER PASS 2

After Pass 2 is frozen, the SAME chat should inspect the full handoff archive and these repo files, preferably from branch `feature/sensor-hub-bootstrap`:

Core protocol:
- `config/rag_benchmark_v2_protocol.json`
- `docs/retrieval_benchmark_v2_amendment_1.md`
- `docs/retrieval_benchmark_v2_amendment_2.md`
- Protocol Amendment 3 documentation / development LLM judging record
- `docs/retrieval_benchmark_v2_amendment_4.md`
- `config/rag_benchmark_v2_confirmation_judging.json`
- `docs/retrieval_benchmark_v2_annotation_protocol.md`

Frozen profile/retrieval implementation:
- retrieval profile definitions and current relevant RAG files
- `scripts/run_benchmark_v2_confirmation_retrieval.py`
- confirmation seed augmentation script
- replay validator and pilot freeze scripts if needed for provenance

Development provenance/results:
- `data/benchmark_v2/dev_results_a3_c60d2f608387.json`
- `docs/retrieval_benchmark_v2_dev_results_a3.md`
- development query / retrieval / judgment manifests as needed

Confirmation:
- confirmation authoring freeze/hash record
- `data/benchmark_v2/confirmation_pool_a2_manifest_c725fba20382.json` or current equivalent
- `data/benchmark_v2/confirmation_pass1_judge_criteria_manifest_c725fba20382.json`
- `data/benchmark_v2/confirmation_pass1_judgment_manifest_c725fba20382.json`
- `data/benchmark_v2/confirmation_pass2_input_manifest_c725fba20382.json`
- `docs/retrieval_benchmark_v2_confirmation_pass2_fresh_context.md`
- `data/benchmark_v2/local_handoff_archive_reference_20261013.json`

Local/full-archive artifacts contain the large text-bearing pools and sealed judgment files that are intentionally not committed publicly.

---

# 16. AFTER PASS 2: EXACT ORDER OF WORK

Do not skip steps.

1. Freeze Pass-2 artifact and SHA.
2. Validate:
   - expected input SHA
   - 48 cases
   - 2252 judgments
   - no duplicate/missing candidate IDs
   - all grades integers in 0..3
3. Join Pass1/Pass2 by stable candidate ID.
4. Compute replicate consistency only, no retrieval profile metrics yet:
   - exact agreement
   - within-one-grade agreement
   - quadratic-weighted Cohen kappa
   - 4×4 confusion matrix
   - disagreement count
5. Generate blinded Pass-3 input only for disagreements.
6. Run Pass 3 without showing Pass1/Pass2 grades.
7. Finalize disagreement grades as median(Pass1,P2,P3).
8. Freeze final confirmation qrels and SHA.
9. Only then open confirmation retrieval-quality metrics.
10. Primary confirmatory contrast:
    `hybrid-e5-content-v1` vs `hybrid-e5-metadata-v1` on nDCG@10.
11. Compute planned metrics/statistics without changing profile parameters.
12. Compute evidence drift and drift-quality association.
13. Report family/query-type/language subgroup results as planned/descriptive unless explicitly confirmatory in frozen protocol.
14. Keep development and confirmation claims separate.

Do not change:
- query wording
- target seeds
- corpus
- snapshot
- profile definitions/hashes
- RRF k
- diversity cap
- embedding model/representation
- relevance threshold
in response to confirmation results.

---

# 17. SCIENTIFIC CLAIM DISCIPLINE

Safe central claim:
“Retrieval-profile changes can alter selected evidence and its provenance even when underlying data and the base embedding model remain unchanged.”

Potential stronger result, only if confirmation supports it:
“Aggregate retrieval quality can remain similar while evidence membership changes measurably, showing why retrieval provenance captures reproducibility information that relevance metrics alone do not.”

Do not conflate:
- chunk drift with source drift
- qrel/pool adequacy with retrieval improvement
- exact frozen-corpus reproducibility with guaranteed future fresh upstream re-harvesting
- replicate LLM judging with human inter-annotator agreement

Do not call LLM judgments human annotations.

---

# 18. USER WORKING STYLE

Respond primarily in Croatian unless manuscript text/code needs English.
Direct, practical, one milestone at a time.
For local actions, prefer exact PowerShell commands and expected output.
Avoid generic AI prose.
Problem-first and limitation-driven writing.
Avoid excessive semicolons and colon-heavy prose.
Avoid “whether”; avoid “rather/whereas” when practical.
Do not be falsely modest about strong results, but do not overclaim.
Do not merge PR without explicit approval.
Do not claim a local command passed until the user reports its output.
Do not claim CI green unless checked.

---

# 19. EXACT FIRST MESSAGE FOR THE ONE NEW CHAT

IMPORTANT: at first do NOT attach this full handoff.

Attach ONLY the fresh Pass-2 package / its two Pass-2 files and paste:

“Nastavljamo PiPi Benchmark V2 u JEDNOM novom glavnom chatu. Prvi zadatak u ovom chatu je namjerno fresh independent confirmation replicate judging Pass 2. Za ovaj prvi zadatak koristi isključivo priloženi `PIPI_V2_PASS2_NEW_CHAT_PROMPT.md` i blinded Pass-2 JSON. Nemoj koristiti memory, ranije chatove, GitHub, Pass-1 rezultate, full handoff archive ni vanjske izvore. Ocijeni svih 2252 query–candidate parova, napravi traženi frozen Pass-2 judgments JSON i izračunaj SHA-256. Nemoj još računati retrieval-quality metrike niti uspoređivati s Pass 1. Nakon što Pass 2 bude potpuno završen i frozen, u OVOM ISTOM chatu dat ću ti full PiPi handoff i tada ovaj chat postaje glavni chat za sav daljnji rad.”

After Pass 2 artifact + SHA are produced, in the SAME chat attach the full archive / this handoff and say:

“Pass 2 je sada frozen. Od ovog trenutka preuzmi puni PiPi kontekst iz priloženog handoffa/arhive i branch `feature/sensor-hub-bootstrap`. Ovo ostaje jedini glavni PiPi chat. Validiraj Pass 2, zatim nastavi strogo po handoff redoslijedu: replicate consistency -> Pass 3 samo za disagreemente -> final qrels freeze -> tek onda confirmation metrics. Ne mijenjaj frozen protokol, profile, queryje, corpus ili thresholdove.”

That gives the user exactly ONE new chat while retaining scientific independence of Pass 2.
