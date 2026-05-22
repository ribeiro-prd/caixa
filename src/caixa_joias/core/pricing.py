from __future__ import annotations
import pandas as pd

def add_pricing_metrics(df: pd.DataFrame, spot_24k: float, fee_rate: float = 0.06, bid_markup: float = 0.05) -> pd.DataFrame:
    out = df.copy()
    out['lance_objetivo'] = out['valor_minimo'] * (1 + bid_markup)
    out['total_objetivo_com_tarifa'] = out['lance_objetivo'] * (1 + fee_rate)
    out['valor_minimo_com_tarifa'] = out['valor_minimo'] * (1 + fee_rate)
    out['peso_fino_estimado_g'] = out['peso_g'] * out['teor_detectado']
    out['spot_por_g_teor'] = spot_24k * out['teor_detectado']
    out['custo_minimo_por_g_bruto'] = out['valor_minimo_com_tarifa'] / out['peso_g']
    out['custo_objetivo_por_g_bruto'] = out['total_objetivo_com_tarifa'] / out['peso_g']
    out['custo_minimo_por_g_fino'] = out['valor_minimo_com_tarifa'] / out['peso_fino_estimado_g']
    out['custo_objetivo_por_g_fino'] = out['total_objetivo_com_tarifa'] / out['peso_fino_estimado_g']
    out['spread_objetivo_vs_spot'] = 1 - (out['total_objetivo_com_tarifa'] / (out['peso_g'] * out['spot_por_g_teor']))
    return out
