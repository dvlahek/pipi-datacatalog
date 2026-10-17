#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
mkdir -p results

if [[ ! -d .venv-second-corpus ]]; then
  python3 -m venv .venv-second-corpus
fi
source .venv-second-corpus/bin/activate
python -m pip install 'requests==2.34.2'

python scripts/second_corpus_dataeuropa_bootstrap_v1.py \
  --out results/second_corpus_dataeuropa_v1 \
  --per-theme 200 \
  --max-file-mib 5 \
  --raw-budget-gib 8 \
  --page-rows 500 \
  --max-sparql-rows-per-theme 40000 \
  2>&1 | tee results/second_corpus_bootstrap_v1.log

sha256sum \
  docs/second_corpus_confirmation_protocol_v1.md \
  docs/second_corpus_confirmation_amendment_1_transport.md \
  config/second_corpus_frozen_config_v1.json \
  scripts/second_corpus_dataeuropa_bootstrap_v1.py \
  results/second_corpus_dataeuropa_v1/dataeuropa_snapshot_manifest.jsonl \
  results/second_corpus_dataeuropa_v1/dataeuropa_snapshot_freeze.json \
  > results/SECOND_CORPUS_PREQUERY_FREEZE_SHA256.txt

cat results/SECOND_CORPUS_PREQUERY_FREEZE_SHA256.txt
