#!/usr/bin/env bash
set -euo pipefail

mkdir -p logs
LOG="logs/post_scrape_processing_$(date +%Y%m%d_%H%M%S).log"

{
  echo "Starting post-scrape processing: $(date)"

  echo ""
  echo "1) Analyze all historical result PDFs"
  caixa-joias analyze-resultados \
    --pdf-dir data/raw/caixa/resultados_all_2025/pdf \
    --out-dir data/processed/resultados_all_2025_analysis \
    --out-xlsx data/exports/resultados_all_2025_analysis.xlsx

  echo ""
  echo "2) Parse current active catalogs"
  caixa-joias parse-history-catalogs \
    --history-dir data/raw/caixa/current_all_active \
    --out-csv data/processed/current_all_active_catalog_lots.csv \
    --summary-csv data/processed/current_all_active_catalog_parse_summary.csv

  echo ""
  echo "3) Generate current active opportunity report"
  caixa-joias opportunities \
    --catalog data/processed/current_all_active_catalog_lots.csv \
    --contains OURO \
    --not-contains RELÓGIO \
    --not-contains "METAL NÃO NOBRE" \
    --out data/exports/current_all_active_opportunities.xlsx

  echo ""
  echo "4) Generate current active heavy-lot opportunity report"
  caixa-joias opportunities \
    --catalog data/processed/current_all_active_catalog_lots.csv \
    --contains OURO \
    --not-contains RELÓGIO \
    --not-contains "METAL NÃO NOBRE" \
    --min-weight 20 \
    --out data/exports/current_all_active_opportunities_20g_plus.xlsx

  echo ""
  echo "5) Build local DuckDB warehouse"
  caixa-joias build-warehouse \
    --processed-dir data/processed \
    --raw-dir data/raw/caixa \
    --out-db data/warehouse/caixa_joias.duckdb \
    --out-exports-dir data/exports/warehouse

  echo ""
  echo "Finished post-scrape processing: $(date)"
} 2>&1 | tee "$LOG"
