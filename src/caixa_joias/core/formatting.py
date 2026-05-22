from __future__ import annotations
import re

def br_money_to_float(value: str) -> float:
    cleaned = value.strip().replace('R$', '').replace('.', '').replace(',', '.')
    return float(cleaned)

def br_weight_to_float(value: str) -> float:
    cleaned = value.strip().replace('.', '').replace(',', '.')
    return float(cleaned)

def normalize_text(value: str) -> str:
    return re.sub(r'\s+', ' ', value or '').strip()
