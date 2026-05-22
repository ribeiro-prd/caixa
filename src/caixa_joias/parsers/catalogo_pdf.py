from __future__ import annotations
import re
from pathlib import Path
import pandas as pd
import pdfplumber
from caixa_joias.core.classify_lot import classify_lot
from caixa_joias.core.formatting import br_money_to_float, br_weight_to_float, normalize_text

LOT_RE = re.compile(r"(?P<lote>\d{4}\.\d{6}-\d)\s+(?P<contrato>\d{4}\.\d{3}\.\d{8}-\d)\s+(?P<descricao>.*?)R\$\s*(?P<valor>[\d\.\,]+)", re.S)
PESO_RE = re.compile(r"PESO\s+LOTE:\s*(?P<peso>[\d\.,]+)\s*G", re.I)

def extract_pdf_text(pdf_path: str | Path) -> str:
    parts = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or '')
    return '\n'.join(parts)

def parse_catalog_pdf(pdf_path: str | Path) -> pd.DataFrame:
    text = extract_pdf_text(pdf_path)
    rows = []
    for match in LOT_RE.finditer(text):
        desc = normalize_text(match.group('descricao'))
        peso_match = PESO_RE.search(desc)
        row = {
            'source_file': Path(pdf_path).name,
            'lote': match.group('lote'),
            'contrato': match.group('contrato'),
            'descricao': desc,
            'valor_minimo': br_money_to_float(match.group('valor')),
            'peso_g': br_weight_to_float(peso_match.group('peso')) if peso_match else None,
            'raw_text': normalize_text(match.group(0)),
        }
        row.update(classify_lot(desc))
        rows.append(row)
    return pd.DataFrame(rows)
