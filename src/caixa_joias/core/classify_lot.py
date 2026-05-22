from __future__ import annotations
import re
from typing import Any

TEOR_PATTERNS = [
    ("999.9", [r"OURO\s*999,9", r"OURO999,9"]),
    ("999", [r"OURO\s*999", r"OURO999"]),
    ("986", [r"OURO\s*,?\s*986", r"OURO986"]),
    ("917", [r"OURO\s*,?\s*917", r"OURO917"]),
    ("900", [r"OURO\s*,?\s*900", r"OURO900"]),
    ("800", [r"OURO\s*,?\s*800", r"OURO800"]),
]

KEYWORDS = {
    'contem_moeda': ['MOEDA'],
    'contem_barra': ['BARRA'],
    'contem_diamante': ['DIAMANTE', 'DIAMANTES'],
    'contem_perola': ['PÉROLA', 'PEROLA', 'PÉROLAS', 'PEROLAS'],
    'contem_massa': ['MASSA'],
    'contem_enchimento': ['ENCHIMENTO', 'ENCHIMENTO(S)'],
    'contem_metal_nao_nobre': ['METAL NÃO NOBRE', 'METAL NAO NOBRE'],
    'contem_relogio': ['RELÓGIO', 'RELOGIO'],
    'contem_prata': ['PRATA'],
    'contem_platina': ['PLATINA'],
    'contem_ouro_baixo': ['OURO BAIXO', 'OURO BRANCO BAIXO'],
}

def detect_teor(desc: str) -> float | None:
    text = desc.upper()
    for label, patterns in TEOR_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, text):
                value = float(label)
                return value / 1000 if value > 100 else value
    return None

def classify_lot(desc: str) -> dict[str, Any]:
    text = desc.upper()
    flags = {key: any(token in text for token in tokens) for key, tokens in KEYWORDS.items()}
    if flags['contem_moeda']:
        tipo = 'moeda'
    elif flags['contem_barra']:
        tipo = 'barra'
    elif flags['contem_relogio']:
        tipo = 'relogio'
    else:
        tipo = 'joia'
    return {'tipo_lote': tipo, 'teor_detectado': detect_teor(desc), **flags}
