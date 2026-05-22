from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from caixa_joias.scrapers.caixa.fetch_metadata import fetch_all_cidades, fetch_periodos
from caixa_joias.scrapers.caixa.fetch_vitrine import fetch_vitrine

FILE_BASE_URL = "https://servicebus2.caixa.gov.br/vitrinearquivos/pdf"


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def download_pdf(file_id: str, out_path: Path) -> bool:
    if not file_id or str(file_id).lower() == "nan":
        return False

    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists() and out_path.stat().st_size > 0:
        return True

    url = f"{FILE_BASE_URL}/{file_id}.pdf"
    response = requests.get(url, timeout=90)

    if response.status_code != 200:
        return False

    content_type = response.headers.get("content-type", "").lower()
    if "pdf" not in content_type and not response.content.startswith(b"%PDF"):
        return False

    out_path.write_bytes(response.content)
    return True


def extract_file_ids(item: dict[str, Any]) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []

    for field in ["edital", "catalogo"]:
        file_id = item.get(field)
        if file_id:
            files.append({"tipo": field, "file_id": str(file_id)})

    published = item.get("arquivosPublicados") or []
    if isinstance(published, str):
        try:
            published = json.loads(published.replace("'", '"'))
        except Exception:
            published = []

    if isinstance(published, list):
        for obj in published:
            if not isinstance(obj, dict):
                continue
            file_id = obj.get("nome") or obj.get("id") or obj.get("arquivo")
            tipo = obj.get("tipo") or obj.get("descricao") or "arquivo_publicado"
            if file_id:
                files.append({"tipo": str(tipo), "file_id": str(file_id)})

    unique: dict[tuple[str, str], dict[str, str]] = {}
    for row in files:
        unique[(row["tipo"], row["file_id"])] = row

    return list(unique.values())


def normalize_period(row: dict[str, Any]) -> tuple[str | None, str | None]:
    possible_start = [
        "inicioLance",
        "dataInicioLance",
        "dataInicio",
        "dtInicio",
        "inicio",
        "data_inicio",
    ]
    possible_end = [
        "fimLance",
        "dataFimLance",
        "dataFim",
        "dtFim",
        "fim",
        "data_fim",
    ]

    start = next((row.get(k) for k in possible_start if row.get(k)), None)
    end = next((row.get(k) for k in possible_end if row.get(k)), None)

    def br_to_iso(value: Any) -> str | None:
        if value is None:
            return None
        s = str(value).strip()
        m = re.search(r"(\d{2})/(\d{2})/(\d{4})", s)
        if m:
            return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
        if m:
            return m.group(0)
        return None

    return br_to_iso(start), br_to_iso(end)



def write_file_indexes(files_df: pd.DataFrame, out_dir: Path) -> None:
    if files_df.empty:
        return

    priority = {"edital": 1, "catalogo": 2, "arquivo_publicado": 9}
    files_df = files_df.copy()
    files_df["tipo_priority"] = files_df["tipo"].map(priority).fillna(5)

    lot_file_map = files_df[
        [
            "uf", "cidade", "codigo_cidade", "data_inicio", "data_fim",
            "lote", "contrato", "tipo", "file_id", "download_ok", "path",
        ]
    ].drop_duplicates()

    unique_files = (
        files_df.sort_values(["file_id", "tipo_priority", "download_ok"], ascending=[True, True, False])
        .drop_duplicates(subset=["file_id"], keep="first")
        [["tipo", "file_id", "download_ok", "path"]]
    )

    lot_file_map.to_csv(out_dir / "lot_file_map.csv", index=False, encoding="utf-8-sig")
    unique_files.to_csv(out_dir / "unique_files.csv", index=False, encoding="utf-8-sig")

def build_history(
    out_dir: Path,
    ufs: list[str] | None = None,
    max_periods_per_city: int | None = None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    cities = fetch_all_cidades(ufs)
    cities_path = out_dir / "cities.csv"
    cities.to_csv(cities_path, index=False, encoding="utf-8-sig")

    all_lots: list[dict[str, Any]] = []
    all_periods: list[dict[str, Any]] = []
    all_files: list[dict[str, Any]] = []

    for _, city in cities.iterrows():
        codigo = int(city["codigo"])
        nome = str(city["nome"])
        uf = str(city.get("siglaUf", city.get("source_uf", "")))

        print(f"City {uf}/{nome}/{codigo}: periods")

        periods = fetch_periodos(codigo)

        for period in periods:
            period_row = dict(period)
            period_row["codigo_cidade"] = codigo
            period_row["cidade"] = nome
            period_row["uf"] = uf
            all_periods.append(period_row)

        if max_periods_per_city:
            periods = periods[:max_periods_per_city]

        for period in periods:
            start, end = normalize_period(dict(period))

            if not start:
                continue

            end = end or start
            print(f"  Fetching {start} to {end}")

            try:
                lots = fetch_vitrine(codigo, start, end)
            except Exception as exc:
                print(f"  Failed vitrine {uf}/{nome}/{codigo}/{start}: {exc}")
                continue

            period_key = f"{uf}_{codigo}_{start}"

            city_lots_path = out_dir / "vitrine" / f"{period_key}.json"
            city_lots_path.parent.mkdir(parents=True, exist_ok=True)
            city_lots_path.write_text(json.dumps(lots, ensure_ascii=False, indent=2), encoding="utf-8")

            for item in lots:
                item = dict(item)
                item["source_uf"] = uf
                item["source_cidade"] = nome
                item["source_codigo_cidade"] = codigo
                item["source_data_inicio"] = start
                item["source_data_fim"] = end
                all_lots.append(item)

                for file_row in extract_file_ids(item):
                    file_id = file_row["file_id"]
                    tipo = safe_name(file_row["tipo"])

                    pdf_path = out_dir / "pdf" / tipo / f"{file_id}.pdf"
                    ok = download_pdf(file_id, pdf_path)

                    all_files.append(
                        {
                            "uf": uf,
                            "cidade": nome,
                            "codigo_cidade": codigo,
                            "data_inicio": start,
                            "data_fim": end,
                            "lote": item.get("numeroDolote"),
                            "contrato": item.get("nuContrato"),
                            "tipo": file_row["tipo"],
                            "file_id": file_id,
                            "download_ok": ok,
                            "path": str(pdf_path),
                        }
                    )

    pd.json_normalize(all_periods).to_csv(out_dir / "periods.csv", index=False, encoding="utf-8-sig")
    pd.json_normalize(all_lots).to_csv(out_dir / "lots.csv", index=False, encoding="utf-8-sig")
    files_df = pd.DataFrame(all_files).drop_duplicates()
    files_df.to_csv(out_dir / "files.csv", index=False, encoding="utf-8-sig")
    write_file_indexes(files_df, out_dir)

    print(f"Cities:  {len(cities)}")
    print(f"Periods: {len(all_periods)}")
    print(f"Lots:    {len(all_lots)}")
    print(f"Files:   {len(all_files)}")
    print(f"Output:  {out_dir}")