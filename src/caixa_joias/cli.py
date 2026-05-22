from __future__ import annotations
from pathlib import Path
import pandas as pd
import typer
import json

from caixa_joias.scrapers.caixa.fetch_vitrine import fetch_vitrine
from caixa_joias.scrapers.caixa.fetch_resultados import fetch_resultados_to_disk
from rich.console import Console
from caixa_joias.scrapers.caixa.fetch_metadata import (
    fetch_all_cidades,
    fetch_cidades,
    fetch_periodos,
    fetch_ufs,
    save_payload,
)
from caixa_joias.core.pricing import add_pricing_metrics
from caixa_joias.core.scoring import add_basic_score
from caixa_joias.exports.excel import write_analysis_excel
from caixa_joias.parsers.catalogo_pdf import parse_catalog_pdf
from caixa_joias.parsers.resultado_pdf import parse_results_pdf
from caixa_joias.parsers.history_catalogs import parse_history_catalogs
from caixa_joias.parsers.pdf_inventory import build_pdf_inventory
from caixa_joias.exports.opportunity_report import build_report
from caixa_joias.scrapers.caixa.download_history import build_history

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
@app.command("fetch-metadata")
def fetch_metadata_command(
    uf: list[str] = typer.Option(["SP"], "--uf"),
    all_ufs: bool = typer.Option(False, "--all-ufs"),
    out_dir: Path = typer.Option(Path("data/raw/caixa/metadata"), "--out-dir"),
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    ufs_payload = fetch_ufs()
    save_payload(ufs_payload, out_dir / "ufs.json", out_dir / "ufs.csv")

    if all_ufs:
        cidades = fetch_all_cidades()
        cidades_path = out_dir / "cidades_ALL.csv"
    else:
        cidades = fetch_all_cidades(uf)
        cidades_path = out_dir / f"cidades_{'_'.join(x.upper() for x in uf)}.csv"

    cidades.to_csv(cidades_path, index=False, encoding="utf-8-sig")

    console.print(f"UF metadata -> {out_dir / 'ufs.csv'}")
    console.print(f"Cities -> {cidades_path}")
    console.print(f"Cities fetched: {len(cidades)}")
@app.command("list-cities")
def list_cities_command(
    uf: str = typer.Option("SP", "--uf"),
) -> None:
    cidades = fetch_cidades(uf)
    df = pd.json_normalize(cidades)

    if df.empty:
        console.print("No cities returned.")
        return

    console.print(df.to_string(index=False))
@app.command("fetch-vitrine-batch")
def fetch_vitrine_batch_command(
    cities_csv: Path = typer.Option(Path("data/raw/caixa/metadata/cidades_SP.csv"), "--cities-csv"),
    data_inicio: str = typer.Option(..., "--data-inicio"),
    data_fim: str | None = typer.Option(None, "--data-fim"),
    quantidade: int = typer.Option(81, "--quantidade"),
    out_dir: Path = typer.Option(Path("data/raw/caixa/api/batch"), "--out-dir"),
) -> None:
    data_fim = data_fim or data_inicio
    out_dir.mkdir(parents=True, exist_ok=True)

    cities = pd.read_csv(cities_csv)
    all_rows = []

    for _, city in cities.iterrows():
        codigo = int(city["codigo"])
        nome = str(city["nome"])
        uf = str(city.get("siglaUf", city.get("source_uf", "")))

        console.print(f"Fetching {uf} / {nome} / {codigo}")

        try:
            items = fetch_vitrine(
                codigo_cidade=codigo,
                data_inicio=data_inicio,
                data_fim=data_fim,
                quantidade=quantidade,
            )
        except Exception as exc:
            console.print(f"Failed {codigo} {nome}: {exc}")
            continue

        for item in items:
            item["source_codigo_cidade"] = codigo
            item["source_cidade"] = nome
            item["source_uf"] = uf
            all_rows.append(item)

        city_json = out_dir / f"vitrine_{uf}_{codigo}_{data_inicio}.json"
        city_csv = out_dir / f"vitrine_{uf}_{codigo}_{data_inicio}.csv"

        city_json.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        pd.json_normalize(items).to_csv(city_csv, index=False, encoding="utf-8-sig")

    combined_json = out_dir / f"vitrine_ALL_{data_inicio}.json"
    combined_csv = out_dir / f"vitrine_ALL_{data_inicio}.csv"

    combined_json.write_text(json.dumps(all_rows, ensure_ascii=False, indent=2), encoding="utf-8")

    df = pd.json_normalize(all_rows)
    df.to_csv(combined_csv, index=False, encoding="utf-8-sig")

    console.print(f"Fetched total rows: {len(all_rows)}")
    console.print(f"Combined JSON -> {combined_json}")
    console.print(f"Combined CSV  -> {combined_csv}")

@app.command("list-periods")
def list_periods_command(
    codigo_cidade: int = typer.Option(..., "--codigo-cidade"),
) -> None:
    periodos = fetch_periodos(codigo_cidade)
    df = pd.json_normalize(periodos)

    if df.empty:
        console.print("No periods returned.")
        return

    console.print(df.to_string(index=False))
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
def opportunities(
    out: Path = typer.Option(Path("data/exports/opportunities.xlsx"), "--out", "-o"),
    catalog: Path = typer.Option(Path("data/processed/catalogo.csv"), "--catalog"),
    vitrine: Path = typer.Option(Path("data/raw/caixa/api/vitrine_9859_2026-05-22.csv"), "--vitrine"),
    spot_24k: float = typer.Option(729.0, "--spot-24k"),
    fee_rate: float = typer.Option(0.06, "--fee-rate"),
    bid_markup: float = typer.Option(0.05, "--bid-markup"),
    contains: list[str] = typer.Option([], "--contains"),
    contains_mode: str = typer.Option("any", "--contains-mode"),
    not_contains: list[str] = typer.Option([], "--not-contains"),
    uf: list[str] = typer.Option([], "--uf"),
    centralizadora: list[str] = typer.Option([], "--centralizadora"),
    location_contains: list[str] = typer.Option([], "--location-contains"),
    min_value: float | None = typer.Option(None, "--min-value"),
    max_value: float | None = typer.Option(None, "--max-value"),
    min_weight: float | None = typer.Option(None, "--min-weight"),
    max_weight: float | None = typer.Option(None, "--max-weight"),
    tipo: list[str] = typer.Option([], "--tipo"),
    teor: list[float] = typer.Option([], "--teor"),
    visibility: str = typer.Option("all", "--visibility"),
    lote: list[str] = typer.Option([], "--lote"),
    contrato: list[str] = typer.Option([], "--contrato"),
    min_score: float | None = typer.Option(None, "--min-score"),
    min_spread: float | None = typer.Option(None, "--min-spread"),
    max_cost_fino: float | None = typer.Option(None, "--max-cost-fino"),
    sort_by: str = typer.Option("score", "--sort-by"),
    limit: int | None = typer.Option(None, "--limit"),
) -> None:
    build_report(
        catalog_csv=catalog,
        vitrine_csv=vitrine,
        out_xlsx=out,
        spot_24k=spot_24k,
        fee_rate=fee_rate,
        bid_markup=bid_markup,
        contains=contains,
        contains_mode=contains_mode,
        not_contains=not_contains,
        uf=uf,
        centralizadora=centralizadora,
        location_contains=location_contains,
        min_value=min_value,
        max_value=max_value,
        min_weight=min_weight,
        max_weight=max_weight,
        tipo=tipo,
        teor=teor,
        visibility=visibility,
        lote=lote,
        contrato=contrato,
        min_score=min_score,
        min_spread=min_spread,
        max_cost_fino=max_cost_fino,
        sort_by=sort_by,
        limit=limit,
    )

    console.print(f"Opportunity report exported -> {out}")
@app.command("fetch-vitrine")
def fetch_vitrine_command(
    codigo_cidade: int = typer.Option(..., "--codigo-cidade"),
    data_inicio: str = typer.Option(..., "--data-inicio"),
    data_fim: str | None = typer.Option(None, "--data-fim"),
    quantidade: int = typer.Option(81, "--quantidade"),
    out_dir: Path = typer.Option(Path("data/raw/caixa/api"), "--out-dir"),
) -> None:
    data_fim = data_fim or data_inicio
    out_dir.mkdir(parents=True, exist_ok=True)

    items = fetch_vitrine(
        codigo_cidade=codigo_cidade,
        data_inicio=data_inicio,
        data_fim=data_fim,
        quantidade=quantidade,
    )

    raw_path = out_dir / f"vitrine_{codigo_cidade}_{data_inicio}.json"
    csv_path = out_dir / f"vitrine_{codigo_cidade}_{data_inicio}.csv"

    raw_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    df = pd.json_normalize(items)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    console.print(f"Fetched {len(items)} Vitrine rows")
    console.print(f"JSON -> {raw_path}")
    console.print(f"CSV  -> {csv_path}")
@app.command("extract-history")
def extract_history_command(
    uf: list[str] = typer.Option(["SP"], "--uf"),
    all_ufs: bool = typer.Option(False, "--all-ufs"),
    max_periods_per_city: int | None = typer.Option(None, "--max-periods-per-city"),
    out_dir: Path = typer.Option(Path("data/raw/caixa/history"), "--out-dir"),
) -> None:
    selected_ufs = None if all_ufs else uf

    build_history(
        out_dir=out_dir,
        ufs=selected_ufs,
        max_periods_per_city=max_periods_per_city,
    )

    console.print(f"Historical extraction completed -> {out_dir}")
@app.command()
def merge_catalog_results(catalog_pdf: Path, results_pdf: Path, out: Path = typer.Option(..., '--out', '-o')) -> None:
    catalog = parse_catalog_pdf(catalog_pdf)
    results = parse_results_pdf(results_pdf)
    merged = catalog.merge(results, on='lote', how='left', suffixes=('', '_result'))
    merged['vendido'] = merged['total'].notna()
    merged['agio_vs_minimo'] = merged['lance'] / merged['valor_minimo'] - 1
    write_analysis_excel(out, {'merged': merged, 'catalog': catalog, 'results': results})
    console.print(f'Merged catalog/results exported -> {out}')

@app.command("parse-history-catalogs")
def parse_history_catalogs_command(
    history_dir: Path = typer.Option(..., "--history-dir"),
    out_csv: Path = typer.Option(Path("data/processed/history_catalog_lots.csv"), "--out-csv"),
    summary_csv: Path = typer.Option(Path("data/processed/history_catalog_parse_summary.csv"), "--summary-csv"),
) -> None:
    parse_history_catalogs(
        history_dir=history_dir,
        out_csv=out_csv,
        out_summary_csv=summary_csv,
    )

@app.command("pdf-inventory")
def pdf_inventory_command(
    history_dir: Path = typer.Option(..., "--history-dir"),
    out_csv: Path = typer.Option(Path("data/processed/pdf_inventory.csv"), "--out-csv"),
) -> None:
    build_pdf_inventory(history_dir=history_dir, out_csv=out_csv)

@app.command("fetch-resultados")
def fetch_resultados_command(
    codigo_cidade: int = typer.Option(..., "--codigo-cidade"),
    data_inicio: str = typer.Option(..., "--data-inicio"),
    data_fim: str = typer.Option(..., "--data-fim"),
    out_dir: Path = typer.Option(Path("data/raw/caixa/resultados"), "--out-dir"),
) -> None:
    fetch_resultados_to_disk(
        codigo_cidade=codigo_cidade,
        data_inicio=data_inicio,
        data_fim=data_fim,
        out_dir=out_dir,
    )

