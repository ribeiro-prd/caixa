from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from caixa_joias.scrapers.caixa.fetch_vitrine import BASE_URL, fetch_json


def save_payload(payload: Any, json_path: Path, csv_path: Path) -> pd.DataFrame:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    data = payload if isinstance(payload, list) else [payload]
    df = pd.json_normalize(data)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    return df


def fetch_ufs() -> list[dict]:
    data = fetch_json(f"{BASE_URL}/busca/ufs/leiloes")
    return data if isinstance(data, list) else []


def fetch_cidades(uf: str) -> list[dict]:
    data = fetch_json(f"{BASE_URL}/busca/cidades/{uf.upper()}")
    return data if isinstance(data, list) else []


def fetch_periodos(codigo_cidade: int) -> list[dict]:
    data = fetch_json(f"{BASE_URL}/busca/periodos/{codigo_cidade}")
    return data if isinstance(data, list) else []


def fetch_all_cidades(ufs: list[str] | None = None) -> pd.DataFrame:
    if ufs is None:
        uf_rows = fetch_ufs()
        ufs = [row.get("sigla") or row.get("siglaUf") or row.get("uf") for row in uf_rows]
        ufs = [uf for uf in ufs if uf]

    all_rows: list[dict] = []

    for uf in ufs:
        cidades = fetch_cidades(uf)
        for row in cidades:
            row = dict(row)
            row["source_uf"] = uf.upper()
            all_rows.append(row)

    return pd.DataFrame(all_rows)


def main() -> None:
    out_dir = Path("data/raw/caixa/metadata")
    out_dir.mkdir(parents=True, exist_ok=True)

    ufs = fetch_ufs()
    save_payload(ufs, out_dir / "ufs.json", out_dir / "ufs.csv")

    cidades = fetch_all_cidades(["SP"])
    cidades.to_csv(out_dir / "cidades_SP.csv", index=False, encoding="utf-8-sig")

    print("Metadata exported:")
    print(out_dir / "ufs.csv")
    print(out_dir / "cidades_SP.csv")


if __name__ == "__main__":
    main()