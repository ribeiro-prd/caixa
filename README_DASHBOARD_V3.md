# CAIXA Joias Intelligence Dashboard v3

Upgrade package for the local dashboard.

Main improvements:
- Light theme and card-based layout.
- Date filters for Vitrine and Histórico.
- Gold purity / teor extraction and filtering: 999 / 24k, 986, 900, 750 / 18k, etc.
- Minerando-style analytical sections using local data:
  - Início
  - Vitrine
  - Histórico
  - Lances / Inteligência
  - Explorar
  - Compradores
  - Universo
- Extra analysis where source screenshots were blurred:
  - Opportunity score
  - Premium by material/type/purity
  - Sweet spot by price and weight
  - Gem hidden-value comparison
  - Geography competition table
  - Buyer concentration

Install from repo root:

```bash
cp -r /d/leilao/caixa_joias_dashboard_v3_package/* .
pip install -r requirements-dashboard.txt
python scripts/install_dashboard_v3.py
python -m py_compile src/caixa_joias/warehouse/build.py src/caixa_joias/dashboard/app.py
```

Build:

```bash
caixa-joias build-warehouse \
  --processed-dir data/processed \
  --raw-dir data/raw/caixa \
  --out-db data/warehouse/caixa_joias.duckdb \
  --out-exports-dir data/exports/warehouse
```

Serve:

```bash
caixa-joias serve
```
