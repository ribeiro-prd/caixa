from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from caixa_joias.scrapers.caixa.fetch_vitrine import BASE_URL, HEADERS, fetch_json


def to_result_date(value: str) -> str:
    value = value.strip()

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        y, m, d = value.split("-")
        return f"{d}-{m}-{y}"

    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", value):
        d, m, y = value.split("/")
        return f"{d}-{m}-{y}"

    if re.fullmatch(r"\d{2}-\d{2}-\d{4}", value):
        return value

    raise ValueError(f"Unsupported date format: {value}")


def fetch_resultados(
    codigo_cidade: int,
    data_inicio: str,
    data_fim: str,
    numero_lote_ou_contrato: str = "",
) -> Any:
    params = {
        "codigoDaCidade": codigo_cidade,
        "dataFimLance": to_result_date(data_fim),
        "dataInicioLance": to_result_date(data_inicio),
        "numeroDoLoteOuContrato": numero_lote_ou_contrato,
    }

    return fetch_json(f"{BASE_URL}/busca/resultados-leiloes", params=params)


def find_dicts(obj: Any) -> list[dict]:
    found: list[dict] = []

    if isinstance(obj, dict):
        found.append(obj)
        for value in obj.values():
            found.extend(find_dicts(value))

    elif isinstance(obj, list):
        for item in obj:
            found.extend(find_dicts(item))

    return found


def extract_download_files(payload: Any) -> pd.DataFrame:
    rows = []

    for obj in find_dicts(payload):
        file_id = (
            obj.get("documento")
            or obj.get("file_id")
            or obj.get("arquivo")
            or obj.get("nome")
        )

        file_name = (
            obj.get("nome")
            or obj.get("nomeArquivo")
            or obj.get("tipoArquivo")
            or obj.get("descricao")
            or obj.get("tipo")
        )

        if not file_id or not file_name:
            continue

        file_id = str(file_id)
        file_name = str(file_name)

        if not re.fullmatch(r"\d{20,}", file_id):
            continue

        rows.append(
            {
                "file_id": file_id,
                "file_name": file_name,
            }
        )

    return pd.DataFrame(rows).drop_duplicates()


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def download_result_file(file_id: str, file_name: str, out_dir: Path) -> Path | None:
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / f"{file_id}_{safe_name(file_name)}.pdf"

    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path

    response = requests.get(
        f"{BASE_URL}/cronograma/download",
        params={"documento": file_id, "nome": file_name},
        headers=HEADERS,
        timeout=90,
    )

    if response.status_code != 200:
        return None

    if not response.content.startswith(b"%PDF"):
        return None

    out_path.write_bytes(response.content)
    return out_path


def fetch_resultados_to_disk(
    codigo_cidade: int,
    data_inicio: str,
    data_fim: str,
    out_dir: str | Path,
) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = fetch_resultados(
        codigo_cidade=codigo_cidade,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )

    raw_path = out_dir / f"resultados_{codigo_cidade}_{data_inicio}_{data_fim}.json"
    raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    files = extract_download_files(payload)

    rows = []
    for _, row in files.iterrows():
        path = download_result_file(
            file_id=row["file_id"],
            file_name=row["file_name"],
            out_dir=out_dir / "pdf",
        )

        rows.append(
            {
                "file_id": row["file_id"],
                "file_name": row["file_name"],
                "download_ok": path is not None,
                "path": str(path) if path else None,
            }
        )

    files_out = pd.DataFrame(rows)
    files_out.to_csv(out_dir / "result_files.csv", index=False, encoding="utf-8-sig")

    print(f"Raw JSON -> {raw_path}")
    print(f"Files -> {out_dir / 'result_files.csv'}")
    print(files_out.to_string(index=False))


if __name__ == "__main__":
    fetch_resultados_to_disk(
        codigo_cidade=9859,
        data_inicio="2026-01-01",
        data_fim="2026-05-22",
        out_dir="data/raw/caixa/resultados_sp",
    )