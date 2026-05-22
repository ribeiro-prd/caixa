from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import requests

BASE_URL = "https://servicebus2.caixa.gov.br/vitrinedejoias/api"

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://vitrinedejoias.caixa.gov.br/Paginas/Busca.aspx",
}


def fetch_json(url: str, params: dict | None = None) -> Any:
    response = requests.get(url, params=params, headers=HEADERS, timeout=60)
    response.raise_for_status()
    return response.json()


def find_candidate_lists(obj: Any, path: str = "$") -> list[tuple[str, list]]:
    found: list[tuple[str, list]] = []

    if isinstance(obj, list):
        found.append((path, obj))
        for i, item in enumerate(obj[:5]):
            found.extend(find_candidate_lists(item, f"{path}[{i}]"))

    elif isinstance(obj, dict):
        for key, value in obj.items():
            found.extend(find_candidate_lists(value, f"{path}.{key}"))

    return found


def pick_items(data: Any) -> list[dict]:
    candidates = find_candidate_lists(data)

    dict_lists = [
        (path, items)
        for path, items in candidates
        if items and isinstance(items[0], dict)
    ]

    if not dict_lists:
        return []

    dict_lists.sort(key=lambda x: len(x[1]), reverse=True)
    path, items = dict_lists[0]
    print(f"Using list path: {path} ({len(items)} items)")
    return items


def fetch_vitrine(
    codigo_cidade: int,
    data_inicio: str,
    data_fim: str,
    quantidade: int = 81,
    max_pages: int = 200,
) -> list[dict]:
    out_dir = Path("data/raw/caixa/api/pages")
    out_dir.mkdir(parents=True, exist_ok=True)

    all_items: list[dict] = []

    for page in range(1, max_pages + 1):
        params = {
            "campoDeOrdenacao": "valor_minimo",
            "codigoDaCidade": codigo_cidade,
            "dataFimLance": data_fim,
            "dataInicioLance": data_inicio,
            "numeroDoLoteOuContrato": "",
            "ordenacao": "decrescente",
            "pagina": page,
            "quantidadeDeItens": quantidade,
            "valorMaximoVenda": 0,
            "valorMinimoVenda": 0,
        }

        data = fetch_json(f"{BASE_URL}/busca/vitrine", params=params)

        page_path = out_dir / f"vitrine_page_{page}.json"
        page_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        if page == 1:
            if isinstance(data, dict):
                print("Top-level keys:", list(data.keys()))
            else:
                print("Top-level type:", type(data).__name__)

        items = pick_items(data)

        if not items:
            print(f"No items found on page {page}. Raw saved to {page_path}")
            break

        all_items.extend(items)

        if len(items) < quantidade:
            break

    return all_items


def main() -> None:
    out_dir = Path("data/raw/caixa/api")
    out_dir.mkdir(parents=True, exist_ok=True)

    codigo_cidade = 9859
    data_inicio = "2026-05-22"
    data_fim = "2026-05-22"

    items = fetch_vitrine(codigo_cidade, data_inicio, data_fim)

    raw_path = out_dir / f"vitrine_{codigo_cidade}_{data_inicio}.json"
    csv_path = out_dir / f"vitrine_{codigo_cidade}_{data_inicio}.csv"

    raw_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    df = pd.json_normalize(items)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    print(f"Fetched {len(items)} items")
    print(f"JSON: {raw_path}")
    print(f"CSV:  {csv_path}")
    print("Columns:", df.columns.tolist())


if __name__ == "__main__":
    main()