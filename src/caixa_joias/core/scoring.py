from __future__ import annotations
import pandas as pd

def add_basic_score(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    score = pd.Series(0, index=out.index, dtype='float64')
    score += (out['spread_objetivo_vs_spot'] >= 0.30).astype(int) * 3
    score += out['teor_detectado'].isin([0.9999, 0.999, 0.986, 0.917, 0.900]).astype(int) * 2
    score += out['tipo_lote'].isin(['moeda', 'barra']).astype(int) * 2
    for col in ['contem_massa', 'contem_enchimento', 'contem_metal_nao_nobre', 'contem_relogio']:
        if col in out:
            score -= out[col].fillna(False).astype(int) * 2
    if 'contem_perola' in out:
        score -= out['contem_perola'].fillna(False).astype(int)
    out['score_basico'] = score.clip(lower=0, upper=10)
    return out
