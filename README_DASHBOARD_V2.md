# CAIXA Joias Intelligence Dashboard v2

Full replacement package for the first basic dashboard.

It keeps everything local:

- raw PDFs / JSON / CSVs under `data/`
- DuckDB warehouse at `data/warehouse/caixa_joias.duckdb`
- Streamlit browser UI at `http://localhost:8501`

## Pages

- Inicio / Visao Geral
- Vitrine
- Historico
- Inteligencia de Lances
- Compradores
- Universo de Dados

## Install from repo root

```bash
cp -r /d/leilao/caixa_joias_dashboard_v2_package/* .
pip install -r requirements-dashboard.txt
python scripts/install_dashboard_v2.py
python -m py_compile src/caixa_joias/warehouse/build.py src/caixa_joias/dashboard/app.py
```

## Build and run

```bash
caixa-joias build-warehouse \
  --processed-dir data/processed \
  --raw-dir data/raw/caixa \
  --out-db data/warehouse/caixa_joias.duckdb \
  --out-exports-dir data/exports/warehouse

caixa-joias serve
```

This v2 package prioritizes the national all-2025 output over the old SP-only output.
