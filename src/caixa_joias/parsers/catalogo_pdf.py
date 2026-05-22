from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pdfplumber

from caixa_joias.core.classify_lot import classify_lot
from caixa_joias.core.formatting import br_money_to_float, br_weight_to_float, normalize_text

LOT_ID_RE = re.compile(r"\b\d{4}\.\d{6}-\d\b")
CONTRACT_RE = re.compile(r"\b\d{4}\.\d{3}\.\d{8}-\d\b")
VALOR_RE = re.compile(r"R\$\s*(?P<valor>[\d\.\,]+)")
PESO_RE = re.compile(r"PESO\s*(?:[^:]{0,50})?\s*LOTE\s*:\s*(?P<peso>[\d\.,]+)\s*G", re.I)

CATALOG_COLUMNS = [
    "source_file",
    "lote",
    "contrato",
    "descricao",
    "valor_minimo",
    "peso_g",
    "raw_text",
    "tipo_lote",
    "teor_detectado",
    "contem_moeda",
    "contem_barra",
    "contem_diamante",
    "contem_perola",
    "contem_massa",
    "contem_enchimento",
    "contem_metal_nao_nobre",
    "contem_relogio",
    "contem_prata",
    "contem_platina",
    "contem_ouro_baixo",
]


def extract_pdf_text(pdf_path: str | Path) -> str:
    parts: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


def _parse_lot_block(block: str, source_file: str) -> dict | None:
    raw = normalize_text(block)

    lote_match = LOT_ID_RE.search(raw)
    contract_match = CONTRACT_RE.search(raw)
    valor_match = VALOR_RE.search(raw)

    if not lote_match or not contract_match or not valor_match:
        return None

    desc = raw
    desc = LOT_ID_RE.sub(" ", desc, count=1)
    desc = CONTRACT_RE.sub(" ", desc, count=1)
    desc = VALOR_RE.sub(" ", desc, count=1)
    desc = normalize_text(desc)

    peso_match = PESO_RE.search(desc)

    row = {
        "source_file": source_file,
        "lote": lote_match.group(0),
        "contrato": contract_match.group(0),
        "descricao": desc,
        "valor_minimo": br_money_to_float(valor_match.group("valor")),
        "peso_g": br_weight_to_float(peso_match.group("peso")) if peso_match else None,
        "raw_text": raw,
    }
    row.update(classify_lot(desc))
    return row

def parse_catalog_pdf(pdf_path: str | Path) -> pd.DataFrame:
    pdf_path = Path(pdf_path)
    text = extract_pdf_text(pdf_path)

    starts = [m.start() for m in LOT_ID_RE.finditer(text)]
    rows: list[dict] = []

    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        block = text[start:end]
        row = _parse_lot_block(block, pdf_path.name)
        if row:
            rows.append(row)

    return pd.DataFrame(rows, columns=CATALOG_COLUMNS)