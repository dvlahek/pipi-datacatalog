# PiPi Benchmark V2 — reproducibility record

This document records the frozen identifiers and public result artifacts used for the PiPi Benchmark V2 retrieval-provenance study.

## Frozen parent state

- catalog snapshot SHA-256: `068e1b0df74acd8b91d04a5161f4413d57d07bfef5c8c9ce2b8d1100ae780419`
- corpus fingerprint SHA-256: `f04239fe6df52ab2604ab45a8c08cc83d5bafe79203a4b16c20a2d2a307e2dc6`
- 192-query confirmation-set SHA-256: `c725fba20382b6d7707b0f1b9bfaba8ac131ebb9c0a461ce7ab4a8988bc26ed5`
- original frozen confirmation qrels SHA-256: `a0946546b7b0109bfc8f0920b7cd8de6412c210cbe26ffb36f155f4a0a5637ad`
- E5 retrieval ledger SHA-256: `335555045685798fc27f781b39092d1b1b9f17af8c53dd16d0e2f757db18a1c0`
- E5 strict replay result SHA-256: `e68bcdf2b1538d644f0988542552d332b11ea37d4edfcc74da194fdfb1d41ea1`

The primary E5 result remains frozen. Later robustness artifacts do not modify these identifiers.

## Frozen E5 retrieval-profile hashes

- lexical-v1: `4234a9a6691d7f0c004eb7b6469662675db35f66fe04dd8eb5b053b1d7a31a54`
- vector-e5-content-v1: `8c00e6326839a8e0e798083197225d1fd90b60db7d6a9e974fe8667de5f0562f`
- hybrid-e5-content-v1: `04fd11fb3c56e9273f7b312a376d5c975a852489276f87fc796f7e0c716f7a45`
- vector-e5-metadata-v1: `e250344e567f85c3dc8ac36b0cd68663f570e322bed7686de99a270ffa0e1628`
- hybrid-e5-metadata-v1: `7b63711593b091d1c21a1548f1b672f4572c69b4fca380779114cad6163211e4`

Primary embedding model: `intfloat/multilingual-e5-small`, normalized 384-dimensional embeddings with E5 query/passage prefixes.

Hybrid retrieval uses lexical plus exact pgvector cosine retrieval, RRF `k=60`, deterministic ties and a source/file soft cap of 2.

## BGE-M3 robustness protocol

Model:

- `BAAI/bge-m3`
- pinned revision: `5617a9f61b028005a4858fdac845db406aefb181`
- dense component only
- 1,024 dimensions
- normalized embeddings
- maximum sequence length 512
- no query instruction

Frozen BGE profile hashes:

- vector content: `b05535cf87b152862aaafb7cdce5da96c9bacb59ef95cc49ad77450305a64cc9`
- vector metadata: `1c0a559e20eef4f2a216b20db38bdcda477e0b8269a48baedcfb582e2e270568`
- hybrid content: `4a9571e8cda92a7dc111a04d1281e74a574e3a2eab74ce9638ee4b68e2491763`
- hybrid metadata: `6bc3569eb2028b63a2e1e2e94284db679f46a7b2963a2b26d112de08ad9bcb08`

Observed frozen artifact hashes:

- BGE embedding preparation: `46d0380ba73c40351e3b99cd576a60d10654e37494616f1125ce5ca248ae4c70`
- BGE retrieval ledger: `e969c644a45796552ff2d0279ec8a70b457351841f9eb31a75c1c17bda6c949f`
- final supplementary judgments: `826609e7a5c3ba2a87b3c08d99f5f53fe2899cd4c87ae2ba82e2ca05db288d4e`
- final supplementary qrels: `2713de9adfb02d6a06dd0025403ab702f96d5994250246b90da474061b08a9ad`
- extended BGE qrels: `80532a1d2ac657efd261baf6cb38dde48f4b0f5b9bf6d720e6a85cf4b6d297f7`
- final BGE results: `6b7a6c54d7f2651a14a638f2ba2d28f5e0730609574aaa8c064d00d96b971385`
- final BGE manifest: `9a19e24aa23512725d7ea853a332c75741e5fb557bfd0bbe6b017fdeb39c77cb`

The robustness protocol file itself is stored in `config/rag_benchmark_v2_bge_m3_robustness.json`. The observed protocol file SHA during the run was `67b01d18a9f7ac70a3dff9002955530e3ad55f9af540fa0a4732da86257258a3`.

## Supplementary judging

BGE-M3 retrieved candidates outside the original frozen E5 judging pool. Unjudged candidates were never treated as non-relevant.

Coverage before supplementary judging:

- 6,080 / 7,680 top-10 slots already judged
- 1,090 unique novel query-candidate pairs
- 37 / 192 vector query pairs fully judged
- 79 / 192 hybrid query pairs fully judged

The 1,090 novel candidates were judged in two independent blinded passes. Exact S1/S2 agreement was 461/1,090. All 629 disagreements were adjudicated by a third fresh blinded judge. Final BGE top-10 qrels coverage was 7,680/7,680.

The original E5 qrels were not rewritten. Supplementary judgments are an extension used only for the post-hoc BGE-M3 robustness analysis.

## BGE-M3 result

Metadata representation retained the same positive direction as the primary E5 experiment.

Vector metadata minus content:

- ΔnDCG@10 = `+0.093699`
- 95% bootstrap CI = `[+0.067815, +0.120893]`
- Wilcoxon p = `1.468e-10`
- rank-biserial = `0.620`

Hybrid metadata minus content:

- ΔnDCG@10 = `+0.034890`
- 95% bootstrap CI = `[+0.021656, +0.048405]`
- Wilcoxon p = `1.405e-07`
- rank-biserial = `0.563`

This analysis is post-hoc robustness evidence and must not be described as a second preregistered confirmation experiment.

## Running the BGE-M3 runner

Install embedding dependencies:

```bash
python -m pip install -r requirements-embeddings.txt
```

Preflight:

```bash
python scripts/run_benchmark_v2_bge_m3_robustness.py \
  --phase preflight \
  --qrels <path-to-frozen-primary-qrels>
```

Prepare embeddings:

```bash
python scripts/run_benchmark_v2_bge_m3_robustness.py \
  --phase embed \
  --device cpu \
  --batch-size 8
```

Run retrieval:

```bash
python scripts/run_benchmark_v2_bge_m3_robustness.py \
  --phase retrieve \
  --device cpu \
  --batch-size 8 \
  --qrels <path-to-frozen-primary-qrels>
```

The runner deliberately stops before qrels-based quality metrics if any retrieved top-10 candidate is unjudged.

## Public result artifacts

The `data/benchmark_v2` directory contains the lightweight public artifacts needed to inspect the frozen statistical result without publishing retrieved chunk text.

Chunk text used in blinded judging is intentionally not included in the public result export. Retrieval ledgers are publication-safe only when stored without chunk text.
