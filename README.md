# Caixa Joias Scraper

Parser, scraper, warehouse builder, and local dashboard for CAIXA jewelry auctions.

The project turns CAIXA catalog PDFs, current Vitrine API data, downloaded active
auction files, and historical result PDFs into analysis-ready CSV files, a local
DuckDB warehouse, Excel summaries, and a Streamlit dashboard.

## What this repo contains

- `src/caixa_joias/scrapers/caixa`: CAIXA API clients for metadata, Vitrine lots,
  historical periods, file downloads, and result reports.
- `src/caixa_joias/parsers`: PDF parsers for catalog lots, result reports, and
  downloaded historical/current catalog folders.
- `src/caixa_joias/analysis`: result-report parsing and merge workflows.
- `src/caixa_joias/exports`: Excel opportunity reports and catalog/API merges.
- `src/caixa_joias/warehouse`: DuckDB warehouse build and analytical views.
- `src/caixa_joias/dashboard`: local Streamlit dashboard.
- `data/raw/caixa`: local raw API responses, PDF downloads, metadata, and file maps.
- `data/processed`: parsed catalog/result CSV files.
- `data/warehouse`: generated DuckDB database.
- `data/exports`: generated Excel/CSV analysis outputs.
- `tests`: focused parser and warehouse regression tests.

Generated data files can be large and may contain operational scrape state. Keep raw
PDFs, result reports, cookies, sessions, downloaded API payloads, generated DuckDB
files, and generated Excel exports out of commits unless there is a deliberate reason
to version a small fixture.

## Setup

From the repo root:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
pip install -r requirements-dashboard.txt
playwright install
```

The package exposes the `caixa-joias` command.

## Typical full workflow

The current end-to-end flow is:

1. Fetch CAIXA city/UF metadata.
2. Extract active/current auction files and Vitrine JSON into `data/raw/caixa/current_all_active`.
3. Parse current active catalog PDFs into `data/processed/current_all_active_catalog_lots.csv`.
4. Fetch or analyze historical result reports.
5. Build the local DuckDB warehouse.
6. Open the dashboard.

The post-scrape processing script performs the local processing steps after raw data
has already been collected:

```bash
./run_processing_after_scrape.sh
```

It writes a timestamped log under `logs/`.

## Useful commands

Fetch metadata for every UF:

```bash
caixa-joias fetch-metadata --all-ufs --out-dir data/raw/caixa/metadata
```

List cities for one UF:

```bash
caixa-joias list-cities --uf SP
```

List available auction periods for a city:

```bash
caixa-joias list-periods --codigo-cidade 9859
```

Fetch Vitrine rows for one city/date window:

```bash
caixa-joias fetch-vitrine \
  --codigo-cidade 9859 \
  --data-inicio 2026-05-22 \
  --data-fim 2026-05-22 \
  --out-dir data/raw/caixa/api
```

Fetch Vitrine rows for a batch of cities:

```bash
caixa-joias fetch-vitrine-batch \
  --cities-csv data/raw/caixa/metadata/cidades_ALL.csv \
  --data-inicio 2026-05-22 \
  --data-fim 2026-05-22 \
  --out-dir data/raw/caixa/api/batch
```

Extract active or historical CAIXA files for selected UFs:

```bash
caixa-joias extract-history \
  --uf SP \
  --out-dir data/raw/caixa/current_all_active
```

Use `--all-ufs` to collect every UF, and `--max-periods-per-city` for a small test run.

Parse a single catalog PDF:

```bash
caixa-joias parse-catalog data/raw/caixa/Catalogo.pdf \
  --out data/processed/catalogo.csv
```

Parse one result report PDF:

```bash
caixa-joias parse-results data/raw/caixa/Relatorio.pdf \
  --out data/processed/resultados.csv
```

Parse all catalog PDFs in a downloaded history/current folder:

```bash
caixa-joias parse-history-catalogs \
  --history-dir data/raw/caixa/current_all_active \
  --out-csv data/processed/current_all_active_catalog_lots.csv \
  --summary-csv data/processed/current_all_active_catalog_parse_summary.csv
```

Analyze a folder of result PDFs:

```bash
caixa-joias analyze-resultados \
  --pdf-dir data/raw/caixa/resultados_all_2025/pdf \
  --out-dir data/processed/resultados_all_2025_analysis \
  --out-xlsx data/exports/resultados_all_2025_analysis.xlsx
```

Build an opportunity workbook from a catalog:

```bash
caixa-joias opportunities \
  --catalog data/processed/current_all_active_catalog_lots.csv \
  --contains OURO \
  --not-contains RELOGIO \
  --not-contains "METAL NAO NOBRE" \
  --out data/exports/current_all_active_opportunities.xlsx
```

Build the warehouse:

```bash
caixa-joias build-warehouse \
  --processed-dir data/processed \
  --raw-dir data/raw/caixa \
  --out-db data/warehouse/caixa_joias.duckdb \
  --out-exports-dir data/exports/warehouse
```

Serve the dashboard:

```bash
caixa-joias serve
```

## Warehouse inputs

The warehouse builder is intentionally tolerant of partial data, but the richest
dashboard requires these inputs:

- `data/processed/current_all_active_catalog_lots.csv`: parsed current catalog rows.
- `data/raw/caixa/current_all_active/lots.csv`: active Vitrine rows from CAIXA.
- `data/raw/caixa/current_all_active/vitrine/*.json`: active Vitrine JSON files,
  named with UF, city code, and date when available.
- `data/raw/caixa/current_all_active/lot_file_map.csv`: file-level map from lot,
  contract, and PDF file id to UF, city, city code, and auction dates.
- `data/raw/caixa/current_all_active/periods.csv`: current period metadata.
- `data/raw/caixa/current_all_active/unique_files.csv`: downloaded active file index.
- `data/processed/resultados_all_2025_analysis/resultados_lances_merged_catalog_keyed.csv`:
  historical winning bids merged to catalog keys.
- `data/processed/resultados_all_2025_analysis/resultados_catalog_lots.csv`:
  historical catalog rows.
- `data/raw/caixa/resultados_all_2025/batch_result_files.csv`: result-file metadata.

Older SP-only fallback filenames are still supported in parts of the builder for
development and migration.

## Current metadata enrichment

`current_lots` metadata comes from two layers:

1. Lot/contract match against active Vitrine API rows.
2. File-level fallback through `current_file_id` and
   `data/raw/caixa/current_all_active/lot_file_map.csv`.

The second layer is important because some parsed catalog rows do not match the
active Vitrine JSON by lot/contract even though the downloaded PDF file carries the
right UF, city, city code, start date, and end date. The fallback fills only missing
metadata fields, so good lot-level Vitrine matches are preserved.

Expected coverage check after a rebuild:

```sql
SELECT
  COUNT(*) AS total,
  COUNT(*) FILTER (
    WHERE uf IS NOT NULL
      AND cidade IS NOT NULL
      AND data_inicio_norm IS NOT NULL
  ) AS with_uf_city_date
FROM current_lots;
```

With the current active file map, every row in
`current_all_active_catalog_lots.csv` should have a matching `current_file_id`.

## Warehouse outputs

The warehouse build writes:

- `data/warehouse/caixa_joias.duckdb`
- `data/exports/warehouse/warehouse_summary.xlsx`
- one CSV per analytical view in `data/exports/warehouse`

Main warehouse tables:

- `current_lots`: active/current catalog rows with features and metadata.
- `historical_lots`: historical catalog rows with sale status when available.
- `lances`: historical winning bids/results with price and premium metrics.
- `buyers`: buyer-level aggregation.
- `history_periods`, `history_files`, `result_files`: supporting scrape indexes.

Main views:

- `v_market_summary`
- `v_universe`
- `v_current_opportunities`
- `v_current_value_by_material`
- `v_current_value_by_type`
- `v_current_value_by_purity`
- `v_price_sweet_spot`
- `v_weight_sweet_spot`
- `v_premium_bands`
- `v_premium_by_material`
- `v_premium_by_type`
- `v_premium_by_purity`
- `v_geography`
- `v_buyer_concentration`
- `v_strategy_backtest`
- `v_gem_value`

## Dashboard

The dashboard reads `data/warehouse/caixa_joias.duckdb` and exposes:

- overview metrics for current Vitrine and historical results
- filters by date, UF, city, material, purity, item type, gem group, weight, and value
- current opportunity ranking
- historical premium and sweet-spot analysis
- geography and buyer concentration views
- downloadable filtered Vitrine CSVs

Run `caixa-joias build-warehouse` before `caixa-joias serve` whenever raw or processed
data changes.

## Testing

Run the focused tests:

```bash
pytest
```

If `pytest` is not on PATH:

```bash
python -m pytest
```

Useful smoke checks:

```bash
python -m py_compile src/caixa_joias/warehouse/build.py src/caixa_joias/dashboard/app.py
caixa-joias build-warehouse
```

## Troubleshooting

If current dashboard rows are missing UF/city/date, rebuild the warehouse and check
that `data/raw/caixa/current_all_active/lot_file_map.csv` exists and has `file_id`,
`uf`, `cidade`, `codigo_cidade`, `data_inicio`, and `data_fim` columns.

If historical geography is sparse, confirm that
`data/raw/caixa/resultados_all_2025/batch_result_files.csv` exists and that parsed
result rows have a result file id that can be mapped back to that file index.

If sweet-spot views look wrong, confirm that both historical catalog rows and result
rows are present. The sweet-spot views compare all historical catalog lots with sold
lots by price and weight band, so missing catalog coverage will distort sale rates.

If Streamlit opens but shows empty charts, run `caixa-joias build-warehouse` again
and confirm `data/warehouse/caixa_joias.duckdb` was updated.

If CAIXA API calls fail, retry later and keep the raw files already downloaded. The
local warehouse/dashboard steps can be rerun without hitting the network.
