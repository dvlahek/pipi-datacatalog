# PiPi Benchmark V2 — Confirmation Stage B history archive

**Frozen:** 2026-10-14  
**Repository branch:** `feature/sensor-hub-bootstrap`  
**Parent HEAD before this archive:** `15fb84414098e738638706e8288888808afa5233`

This directory is the durable Git history record for the Benchmark V2 confirmation Stage B: independent Pass 2 validation, Pass-3 adjudication, final-qrels freeze, and the preregistered confirmation retrieval analysis.

## Canonical Stage-B package

`PIPI_V2_CONFIRMATION_STAGE_B_FINAL_20261014.zip`

- size: `1006058` bytes
- SHA-256: `589aaf562b7e0fa2608db9d0f82ccc3b431fb719a900da2ef1aa48b58a4f5c71`

The GitHub connector used for this archive can commit UTF-8 repository files but cannot upload binary ZIP bytes from the working container. Therefore the repository stores the complete byte-level package manifest plus the scientifically critical readable freeze/results artifacts. The canonical ZIP remains verified by the SHA above; `MANIFEST.json` lists every file in it with size and SHA-256.

## Frozen judgment chain

- Pass-1 judgments: `85ced352b8a7dce34465718895a1c418966df6568d7fd467c88673b01135e8af`
- Pass-1 qrels: `65d404e14c60b34b1135c1a8afcb521a58c8485dba2719e6df5c587d8a8049b9`
- normalized Pass-2 judgments: `2a974b8d4e9a23f1d9cd8ffd565fc333f865223bc1909e57790def019fd455d5`
- replicate consistency: `1ce9efa1cbbbdbd3f2451bcff00b35b77ffecb9dc4e07ce96c8f83d3644b7c62`
- Pass-3 judgments: `34b93aacc236e76a37f9cc986f763eb4cc302f7bc375ac86ed14f80be352be08`
- final qrels: `a0946546b7b0109bfc8f0920b7cd8de6412c210cbe26ffb36f155f4a0a5637ad`
- final judgments: `a2d742e9b685735ed40f9f26a45ab7fd5389716f68ff9620b1861ba7d19c93e4`
- final results: `8a1b601906eb52539cf36dae6b7c1c02a5493e1c0801b6fbff1f02a7f1be84e9`

## Replicate validation

- 48 preassigned replicate cases / 2252 candidate pairs
- exact Pass-1 ↔ Pass-2 agreement: `0.788632`
- within-one-grade agreement: `0.930728`
- quadratic-weighted Cohen κ: `0.648177`
- 476 disagreements, all adjudicated in blinded Pass 3

## Final qrels

- 192 confirmation cases / 9170 unique query-candidate pairs
- 6918 nonreplicate pairs preserved exactly from Pass 1
- 403 P1 grades changed after the frozen replicate/adjudication protocol
- final grade counts: 0=`7500`, 1=`668`, 2=`666`, 3=`336`

## Primary confirmatory result

Hybrid metadata minus hybrid content:

- ΔnDCG@10 = **+0.028359**
- paired-bootstrap 95% CI = **[+0.013399, +0.044078]**
- Wilcoxon p = **0.000966736**
- rank-biserial = **0.369247**

## Evidence drift

- chunk churn@10 = **0.230208**
- top-1 chunk change rate = **0.260417**
- source churn@10 = **0.103669**
- relevant-evidence retention (grade ≥2) = **0.958360**
- Spearman ρ(chunk churn, |ΔnDCG|) = **0.313436**, p = **9.564×10⁻⁶**

The development set remains diagnostic only. Confirmation retrieval-quality metrics were opened only after the final qrels hash was frozen.