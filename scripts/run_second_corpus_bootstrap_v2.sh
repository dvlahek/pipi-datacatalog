#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
mkdir -p results

if [[ ! -d .venv-second-corpus ]]; then
  python3 -m venv .venv-second-corpus
fi
source .venv-second-corpus/bin/activate
python -m pip install 'requests==2.34.2' 'pypdf==6.21.0'

python scripts/second_corpus_dataeuropa_bootstrap_v2.py \
  --stage all \
  2>&1 | tee results/second_corpus_bootstrap_v2.log

cat results/second_corpus_dataeuropa_v2/SHA256SUMS.prequery.txt
