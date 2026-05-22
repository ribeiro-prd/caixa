from __future__ import annotations
from pathlib import Path
import pandas as pd
import typer
from rich.console import Console
from caixa_joias.core.pricing import add_pricing_metrics
from caixa_joias.core.scoring import add_basic_score
from caixa_joias.exports.excel import write_analysis_excel
from caixa_joias.parsers.catalogo_pdf import parse_catalog_pdf
from caixa_joias.parsers.resultado_pdf import parse_results_pdf

app = typer.Typer(no_args_is_help=True)
console = Console()

@app.command()
def parse_catalog(pdf_path: Path, out: Path = typer.Option(..., '--out', '-o')) -> None:
    df = parse_catalog_pdf(pdf_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False, encoding='utf-8-sig')
    console.print(f'Catalog parsed: {len(df)} lots -> {out}')

@app.command()
def parse_results(pdf_path: Path, out: Path = typer.Option(..., '--out', '-o')) -> None:
    df = parse_results_pdf(pdf_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False, encoding='utf-8-sig')
    console.print(f'Results parsed: {len(df)} rows -> {out}')

@app.command()
def analyze_catalog(pdf_path: Path, out: Path = typer.Option(..., '--out', '-o'), spot_24k: float = typer.Option(729.0, '--spot-24k'), fee_rate: float = typer.Option(0.06, '--fee-rate'), bid_markup: float = typer.Option(0.05, '--bid-markup')) -> None:
    catalog = parse_catalog_pdf(pdf_path)
    priced = add_pricing_metrics(catalog, spot_24k=spot_24k, fee_rate=fee_rate, bid_markup=bid_markup)
    scored = add_basic_score(priced)
    moedas = scored[scored['tipo_lote'].eq('moeda')].copy()
    barras = scored[scored['tipo_lote'].eq('barra')].copy()
    ouro_986 = scored[scored['teor_detectado'].eq(0.986)].copy()
    sort_cols = ['score_basico', 'spread_objetivo_vs_spot']
    for frame in [scored, moedas, barras, ouro_986]:
        frame.sort_values(sort_cols, ascending=[False, False], inplace=True)
    summary = pd.DataFrame([{'source_file': pdf_path.name, 'lots': len(catalog), 'moedas': len(moedas), 'barras': len(barras), 'ouro_986': len(ouro_986), 'spot_24k': spot_24k, 'fee_rate': fee_rate, 'bid_markup': bid_markup}])
    write_analysis_excel(out, {'README': summary, 'ranking_all': scored, 'moedas': moedas, 'barras': barras, 'ouro_986': ouro_986})
    console.print(f'Analysis exported -> {out}')

@app.command()
def merge_catalog_results(catalog_pdf: Path, results_pdf: Path, out: Path = typer.Option(..., '--out', '-o')) -> None:
    catalog = parse_catalog_pdf(catalog_pdf)
    results = parse_results_pdf(results_pdf)
    merged = catalog.merge(results, on='lote', how='left', suffixes=('', '_result'))
    merged['vendido'] = merged['total'].notna()
    merged['agio_vs_minimo'] = merged['lance'] / merged['valor_minimo'] - 1
    write_analysis_excel(out, {'merged': merged, 'catalog': catalog, 'results': results})
    console.print(f'Merged catalog/results exported -> {out}')
