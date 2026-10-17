#!/usr/bin/env bash
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
mkdir -p results

python3 -m venv .venv-second-corpus
source .venv-second-corpus/bin/activate
python -m pip install --upgrade pip
python -m pip install requests

python scripts/second_corpus_dataeuropa_bootstrap_v1.py \
  --out results/second_corpus_dataeuropa_v1 \
  --per-theme 200 \
  --max-file-mib 5 \
  --raw-budget-gib 8 \
  2>&1 | tee results/second_corpus_bootstrap_v1.log

sha256sum \
  docs/second_corpus_confirmation_protocol_v1.md \
  config/second_corpus_frozen_config_v1.json \
  scripts/second_corpus_dataeuropa_bootstrap_v1.py \
  results/second_corpus_dataeuropa_v1/dataeuropa_snapshot_manifest.jsonl \
  results/second_corpus_dataeuropa_v1/dataeuropa_snapshot_freeze.json \
  > results/SECOND_CORPUS_PREQUERY_FREEZE_SHA256.txt

cat results/SECOND_CORPUS_PREQUERY_FREEZE_SHA256.txt
