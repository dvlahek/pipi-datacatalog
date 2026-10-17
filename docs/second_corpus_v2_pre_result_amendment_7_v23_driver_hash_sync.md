# Second-corpus V2 pre-result amendment 7: V2.3 selector-driver hash synchronization

Date: 2026-10-17

Status: pre-corpus-freeze, pre-query, pre-retrieval amendment.

## Trigger

The first invocation of `scripts/second_corpus_dataeuropa_select_v2_3.py` terminated immediately at its selector-driver SHA-256 guard:

- expected: `57b45bcd1e6426481eeb3b16a04f0defb64fe060e3ebeb1c6bd443a92eb36d55`
- actual: `7791a661bdb26ee16a1e59f4c0db7a0a68246edf1bf138e80c1d115c70b16e87`

No candidate selection, distribution download, corpus freeze, query authoring, retrieval, generation, or evaluation occurred in that V2.3 invocation.

## Cause

The V2.3 driver was modified after the expected driver hash had been inserted into `config/second_corpus_frozen_config_v2_3.json`. The guard therefore correctly rejected the stale expected hash.

## Correction

The driver itself is unchanged. The frozen V2.3 config now records the SHA-256 of the already-final driver:

`7791a661bdb26ee16a1e59f4c0db7a0a68246edf1bf138e80c1d115c70b16e87`

The parser-environment manifest contract is unchanged. Its expected SHA-256 remains:

`364acb942bb5ef2323a2725a849fdeb62000a80ffd4ee6bdf1208b6ccb56d5df`

for the exact dependency manifest containing:

- `fonttools = 4.67.0`
- `pypdf = 6.21.0`
- `requests = 2.34.2`

## Scientific impact

None. This change only synchronizes a stale execution-integrity hash with the already-final selector driver. Candidate-universe hashes, candidate order, selection criteria, license rules, payload limits, chunking, query design, confirmatory hypotheses, and retrieval/generation protocols are unchanged.
