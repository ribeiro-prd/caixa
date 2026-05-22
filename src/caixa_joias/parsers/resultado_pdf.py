from __future__ import annotations
import re
from pathlib import Path
import pandas as pd
import pdfplumber
from caixa_joias.core.formatting import br_money_to_float

CPF_RE = re.compile(r"CPF/CNPJ:\s*(?P<doc>[0-9Xx\.\-/]+)")
RESULT_RE = re.compile(r"(?P<lote>\d{4}\.\d{6}-\d)\s+(?P<lance>[\d\.\,]+)\s+(?P<tarifa>[\d\.\,]+)\s+(?P<total>[\d\.\,]+)")

def parse_results_pdf(pdf_path: str | Path) -> pd.DataFrame:
    rows = []
    current_doc = None
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ''
            for line in text.splitlines():
                cpf_match = CPF_RE.search(line)
                if cpf_match:
                    current_doc = cpf_match.group('doc')
                result_match = RESULT_RE.search(line)
                if result_match and current_doc:
                    rows.append({
                        'source_file': Path(pdf_path).name,
                        'page': page_num,
                        'cpf_cnpj_mascarado': current_doc,
                        'lote': result_match.group('lote'),
                        'lance': br_money_to_float(result_match.group('lance')),
                        'tarifa': br_money_to_float(result_match.group('tarifa')),
                        'total': br_money_to_float(result_match.group('total')),
                    })
    return pd.DataFrame(rows)
