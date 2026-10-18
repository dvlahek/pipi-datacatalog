# PiPi Benchmark V2 — full confirmation retrieval replay gate

Date frozen: 2026-10-14

## Purpose

This gate tests the computational-replay part of the retrieval-provenance claim after the Benchmark V2 confirmation analysis has been frozen. It is a reproducibility/mechanism check. It does not alter qrels, profile definitions, retrieval ranks, or any reported retrieval-quality result.

The target is the already-frozen 192-query × 5-profile confirmation retrieval ledger.

## Frozen inputs

- catalog snapshot: `068e1b0df74acd8b91d04a5161f4413d57d07bfef5c8c9ce2b8d1100ae780419`
- corpus fingerprint: `f04239fe6df52ab2604ab45a8c08cc83d5bafe79203a4b16c20a2d2a307e2dc6`
- confirmation query-set SHA: `c725fba20382b6d7707b0f1b9bfaba8ac131ebb9c0a461ce7ab4a8988bc26ed5`
- confirmation retrieval-ledger file SHA: `335555045685798fc27f781b39092d1b1b9f17af8c53dd16d0e2f757db18a1c0`
- expected runs: `960`
- expected cases: `192`
- expected profiles: `5`

The validator uses the persisted `db_run_id` from the frozen confirmation ledger and the existing strict `replay_retrieval_run` implementation.

## Pass condition

`CONFIRMATION_STRICT_REPLAY_PASS` requires all of the following:

1. the ledger byte hash matches the frozen SHA;
2. the current catalog snapshot matches the frozen snapshot;
3. there are exactly 960 unique `(case_id, profile_id)` runs covering 192 cases and the five frozen profiles;
4. every ledger row has a persisted database run ID;
5. the recorded profile ID and profile hash match the ledger;
6. the ordered evidence identity stored in the database matches the publication-safe frozen ledger identity;
7. fresh computational replay reproduces the exact ordered evidence for every run;
8. no run raises a replay refusal or other error.

A single mismatch is a failure. There is no tolerance threshold and no tuning after seeing replay output.

## Interpretation

A pass supports the claim that, while the frozen catalog snapshot and immutable retrieval profile remain available, the historical evidence selection is computationally replayable. It does not imply that a future fresh upstream re-harvest will recreate the same catalog snapshot. The open-data cohort caveat remains unchanged.

## Command

From the repository root on Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe scripts\validate_benchmark_v2_confirmation_replay.py
```

The default ledger is:

`results/benchmark_v2_confirmation_retrieval_ledger_c725fba20382.json`

The default output is:

`results/benchmark_v2_confirmation_strict_replay_c725fba20382.json`
