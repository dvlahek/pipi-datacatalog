# PiPi Benchmark V2 confirmation replicate judging — Pass 2

Use **only** the attached blinded Pass-2 JSON as evidence. Do not use memory, prior chats,
retrieval rankings, profile identities, target identifiers, authoring-seed status, or any
previous relevance grades.

Grade every query–candidate pair independently on this frozen ordinal scale:

- 3 — directly answers the information need or contains decisive evidence needed for the answer
- 2 — clearly contributes useful supporting evidence but is incomplete on its own
- 1 — topically related but insufficient or weak evidence
- 0 — irrelevant

For relation/comparison queries, evidence that clearly supports one side may receive 2.
Use 3 only when the candidate directly satisfies the information need on its own.

Return one JSON artifact with:
- artifact = `pipi-benchmark-v2-confirmation-pass2-judgments`
- pass2_blinded_input_sha256 = `0c1dd9bd553e4159aa33493dd0c44383c344b7c7e232a91203c206d26481f0f9`
- case_count = 48
- candidate_count = 2252
- judgments = a flat array of objects with exactly:
  `case_id`, `candidate_id`, `dataset_identifier`, `dataset_version`, `chunk_index`, `judgment`

Do not compute retrieval-quality metrics. Do not compare against Pass 1.
