#!/usr/bin/env bash
set -euo pipefail

caixa-joias build-warehouse \
  --processed-dir data/processed \
  --raw-dir data/raw/caixa \
  --out-db data/warehouse/caixa_joias.duckdb \
  --out-exports-dir data/exports/warehouse

caixa-joias serve
