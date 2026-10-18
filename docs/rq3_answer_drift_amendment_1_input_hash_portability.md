# RQ3 Answer-Drift Protocol Amendment 1 — input-hash portability

Date: 2026-10-14

## Status

Technical reproducibility amendment made after the RQ3 input freeze and before any benchmark answer generation.

No RQ3 benchmark answer was generated before this amendment. The first attempted generator invocation stopped at the fail-closed gate with:

`RQ3_GENERATION_REFUSED_INPUT_SHA_MISMATCH`

The retrieval conditions, 192 cases, 384 frozen contexts, evidence content/order, model set, model hashes, prompt, decoding configuration, top-k, endpoints, and analysis plan are unchanged.

## Cause

`prepare_benchmark_v2_rq3_inputs.py` constructed the frozen input artifact as UTF-8 JSON with `indent=2` and a final LF and calculated SHA-256 over that in-memory serialization before writing the file.

On Windows, text-mode file writing can translate line endings from LF to CRLF. The original generator then calculated SHA-256 over the raw file bytes. The JSON object was unchanged, but its platform-specific line endings produced a different raw-byte hash and the gate correctly refused generation.

## Resolution

The frozen input identity remains:

`e554461b90cdfe8f01c944b4164984c53a1e2c088d82cb6fe30cd2d6417d8bcf`

The generator now parses the JSON and reconstructs exactly the serialization used by the preparation step:

- UTF-8
- `ensure_ascii=False`
- `indent=2`
- one final LF newline

It then hashes that normalized serialization. This makes verification independent of Windows CRLF/LF checkout or text-write translation while preserving the originally frozen input identity.

Hash scheme label:

`normalized-json-indent2-lf-final-newline`

## Scientific boundary

This amendment changes only cross-platform hash verification. It does not change any scientific input or generation parameter. The frozen RQ3 protocol SHA remains:

`6cbb8b07be1d759ca609260e5af5ffc708416e1e54673f135ccb859fbfd61082`

The frozen RQ3 input SHA remains:

`e554461b90cdfe8f01c944b4164984c53a1e2c088d82cb6fe30cd2d6417d8bcf`

The frozen input manifest remains the pre-generation provenance record. This amendment is an implementation portability fix only.
