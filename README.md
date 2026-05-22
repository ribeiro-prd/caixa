# Caixa Joias Scraper

Parser and analysis toolkit for CAIXA jewelry auction catalogs and result reports.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
playwright install
```

## Basic usage

```bash
caixa-joias parse-catalog data/raw/caixa/Catalogo.pdf --out data/processed/catalogo.csv
caixa-joias parse-results data/raw/caixa/Relatorio.pdf --out data/processed/resultados.csv
caixa-joias analyze-catalog data/raw/caixa/Catalogo.pdf --out data/exports/analise.xlsx --spot-24k 729 --bid-markup 0.05
```

Do not commit raw PDFs, result reports, cookies, sessions, or generated Excel files.
