#!/usr/bin/env bash
# Uso: ./run_grupo2.sh <caminho para clone de Sistema-MicServ-SD> <dir de saída>
set -u
REPO=${1:?clone do Sistema-MicServ-SD}; OUT=${2:-./resultados}; AQUI=$(cd "$(dirname "$0")" && pwd); mkdir -p "$OUT"
for svc in produtos fornecimentos; do
  SD="$REPO/servicos/$svc-service"
  echo "== Suíte dos desenvolvedores: $svc-service"
  (cd "$SD" && python -m pytest -q --junitxml="$OUT/dev-$svc.xml")
  echo "== Suíte QA independente: $svc-service"
  (cd "$SD" && PYTHONPATH="$SD" python -m pytest -q -p no:cacheprovider --rootdir="$SD" -c /dev/null \
     "$AQUI/test_qa_$svc.py" --junitxml="$OUT/qa-$svc.xml" -rf)
done
