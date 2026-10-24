# PiPi Benchmark V2 confirmation judging — Pass 2

Pass 2 is an independent blinded relevance-judgment pass over a fixed 48-query subset. The judge receives only the frozen Pass-2 candidate packet and the grading rubric below. Pass-1 grades, retrieval-profile identities, retrieval rankings, target identifiers, authoring-seed status, and previously computed evaluation results are withheld.

Each query–candidate pair is graded independently on the following ordinal scale:

- 3 — directly answers the information need or contains decisive evidence needed for the answer;
- 2 — clearly contributes useful supporting evidence but is incomplete on its own;
- 1 — topically related but insufficient or weak evidence;
- 0 — irrelevant.

For relation/comparison queries, evidence that clearly supports one side may receive grade 2. Grade 3 is reserved for candidates that directly satisfy the information need on their own.

The output artifact contains:

- `artifact = pipi-benchmark-v2-confirmation-pass2-judgments`;
- `pass2_blinded_input_sha256 = 0c1dd9bd553e4159aa33493dd0c44383c344b7c7e232a91203c206d26481f0f9`;
- `case_count = 48`;
- `candidate_count = 2252`;
- a flat `judgments` array containing `case_id`, `candidate_id`, `dataset_identifier`, `dataset_version`, `chunk_index`, and `judgment`.

Retrieval-quality metrics and Pass-1/Pass-2 agreement statistics are computed only after the Pass-2 output has been frozen.