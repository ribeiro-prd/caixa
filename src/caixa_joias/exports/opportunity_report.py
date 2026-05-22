from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from caixa_joias.core.formatting import br_money_to_float
from caixa_joias.core.pricing import add_pricing_metrics
from caixa_joias.core.scoring import add_basic_score
from caixa_joias.exports.excel import write_analysis_excel


def _text_mask_contains(series: pd.Series, terms: list[str], mode: str) -> pd.Series:
    if not terms:
        return pd.Series(True, index=series.index)

    text = series.fillna("").astype(str)

    masks = [
        text.str.contains(term, case=False, na=False, regex=False)
        for term in terms
    ]

    if mode == "all":
        out = masks[0]
        for m in masks[1:]:
            out = out & m
        return out

    out = masks[0]
    for m in masks[1:]:
        out = out | m
    return out


def _text_mask_not_contains(series: pd.Series, terms: list[str]) -> pd.Series:
    if not terms:
        return pd.Series(True, index=series.index)

    text = series.fillna("").astype(str)

    out = pd.Series(True, index=series.index)
    for term in terms:
        out = out & ~text.str.contains(term, case=False, na=False, regex=False)
    return out


def _parse_money_column(series: pd.Series) -> pd.Series:
    return series.astype(str).apply(
        lambda x: br_money_to_float(x) if x.startswith("R$") else pd.NA
    )


def build_report(
    catalog_csv: str | Path,
    vitrine_csv: str | Path | None,
    out_xlsx: str | Path,
    spot_24k: float,
    fee_rate: float,
    bid_markup: float,
    contains: list[str],
    contains_mode: str,
    not_contains: list[str],
    uf: list[str],
    centralizadora: list[str],
    location_contains: list[str],
    min_value: float | None,
    max_value: float | None,
    min_weight: float | None,
    max_weight: float | None,
    tipo: list[str],
    teor: list[float],
    visibility: str,
    lote: list[str],
    contrato: list[str],
    min_score: float | None,
    min_spread: float | None,
    max_cost_fino: float | None,
    sort_by: str,
    limit: int | None,
) -> None:
    catalog = pd.read_csv(catalog_csv)

    priced = add_pricing_metrics(
        catalog,
        spot_24k=spot_24k,
        fee_rate=fee_rate,
        bid_markup=bid_markup,
    )
    scored = add_basic_score(priced)

    if vitrine_csv:
        vitrine = pd.read_csv(vitrine_csv)

        vitrine_small = vitrine[
            [
                "numeroDolote",
                "nuContrato",
                "valor",
                "deContrato",
                "deLocalEndereco",
                "noCentralizadora",
                "sgUf",
                "coLeilao",
                "dataInicio",
                "dataFim",
                "dataResultado",
                "catalogo",
                "edital",
                "urlImagemCapa",
                "urlImagemFrente",
                "urlImagemVerso",
            ]
        ].copy()

        vitrine_small["valor_vitrine_num"] = _parse_money_column(vitrine_small["valor"])

        merged = scored.merge(
            vitrine_small,
            left_on="lote",
            right_on="numeroDolote",
            how="left",
        )
        merged["visivel_na_vitrine"] = merged["numeroDolote"].notna()
    else:
        merged = scored.copy()
        merged["visivel_na_vitrine"] = False
        merged["sgUf"] = pd.NA
        merged["noCentralizadora"] = pd.NA
        merged["deLocalEndereco"] = pd.NA

    filtered = merged.copy()

    search_text = (
        filtered["descricao"].fillna("").astype(str)
        + " "
        + filtered.get("deContrato", pd.Series("", index=filtered.index)).fillna("").astype(str)
        + " "
        + filtered.get("deLocalEndereco", pd.Series("", index=filtered.index)).fillna("").astype(str)
        + " "
        + filtered.get("noCentralizadora", pd.Series("", index=filtered.index)).fillna("").astype(str)
    )

    include_mask = _text_mask_contains(search_text, contains, contains_mode)
    exclude_mask = _text_mask_not_contains(search_text, not_contains)
    filtered = filtered[include_mask & exclude_mask]

    if uf:
        filtered = filtered[filtered["sgUf"].fillna("").astype(str).str.upper().isin([x.upper() for x in uf])]

    if centralizadora:
        filtered = filtered[
            _text_mask_contains(
                filtered["noCentralizadora"].fillna("").astype(str),
                centralizadora,
                "any",
            )
        ]

    if location_contains:
        filtered = filtered[
            _text_mask_contains(
                filtered["deLocalEndereco"].fillna("").astype(str),
                location_contains,
                "any",
            )
        ]

    if min_value is not None:
        filtered = filtered[filtered["valor_minimo"] >= min_value]

    if max_value is not None:
        filtered = filtered[filtered["valor_minimo"] <= max_value]

    if min_weight is not None:
        filtered = filtered[filtered["peso_g"] >= min_weight]

    if max_weight is not None:
        filtered = filtered[filtered["peso_g"] <= max_weight]

    if tipo:
        filtered = filtered[filtered["tipo_lote"].isin(tipo)]

    if teor:
        filtered = filtered[
            filtered["teor_detectado"].apply(
                lambda x: any(abs(float(x) - t) < 0.0001 for t in teor) if pd.notna(x) else False
            )
        ]

    if visibility == "visible":
        filtered = filtered[filtered["visivel_na_vitrine"]]
    elif visibility == "catalog-only":
        filtered = filtered[~filtered["visivel_na_vitrine"]]

    if lote:
        filtered = filtered[filtered["lote"].isin(lote)]

    if contrato:
        filtered = filtered[filtered["contrato"].isin(contrato)]

    if min_score is not None:
        filtered = filtered[filtered["score_basico"] >= min_score]

    if min_spread is not None:
        filtered = filtered[filtered["spread_objetivo_vs_spot"] >= min_spread]

    if max_cost_fino is not None:
        filtered = filtered[filtered["custo_objetivo_por_g_fino"] <= max_cost_fino]

    sortable = {
        "score": ["score_basico", "spread_objetivo_vs_spot", "custo_objetivo_por_g_fino"],
        "spread": ["spread_objetivo_vs_spot", "score_basico", "custo_objetivo_por_g_fino"],
        "cost-fino": ["custo_objetivo_por_g_fino", "score_basico"],
        "value": ["valor_minimo"],
        "weight": ["peso_g"],
        "lot": ["lote"],
    }

    sort_cols = sortable.get(sort_by, sortable["score"])
    ascending = [False] * len(sort_cols)

    if sort_by == "cost-fino":
        ascending = [True, False]
    elif sort_by == "value":
        ascending = [True]
    elif sort_by == "lot":
        ascending = [True]

    filtered = filtered.sort_values(sort_cols, ascending=ascending)
    merged = merged.sort_values(["score_basico", "spread_objetivo_vs_spot"], ascending=[False, False])

    if limit is not None:
        filtered = filtered.head(limit)

    display_cols = [
        "lote",
        "contrato",
        "sgUf",
        "noCentralizadora",
        "deLocalEndereco",
        "valor_minimo",
        "lance_objetivo",
        "total_objetivo_com_tarifa",
        "peso_g",
        "teor_detectado",
        "tipo_lote",
        "peso_fino_estimado_g",
        "custo_objetivo_por_g_bruto",
        "custo_objetivo_por_g_fino",
        "spread_objetivo_vs_spot",
        "score_basico",
        "visivel_na_vitrine",
        "contem_moeda",
        "contem_barra",
        "contem_diamante",
        "contem_perola",
        "contem_massa",
        "contem_enchimento",
        "contem_metal_nao_nobre",
        "contem_relogio",
        "contem_ouro_baixo",
        "descricao",
        "urlImagemCapa",
        "urlImagemFrente",
        "urlImagemVerso",
    ]

    display_cols = [c for c in display_cols if c in filtered.columns]

    summary = pd.DataFrame(
        [
            {
                "catalog_rows": len(catalog),
                "vitrine_visible_rows": int(merged["visivel_na_vitrine"].sum()),
                "catalog_only_rows": int((~merged["visivel_na_vitrine"]).sum()),
                "filtered_rows": len(filtered),
                "spot_24k": spot_24k,
                "fee_rate": fee_rate,
                "bid_markup": bid_markup,
                "contains": " | ".join(contains),
                "contains_mode": contains_mode,
                "not_contains": " | ".join(not_contains),
                "uf": " | ".join(uf),
                "centralizadora": " | ".join(centralizadora),
                "location_contains": " | ".join(location_contains),
                "min_value": min_value,
                "max_value": max_value,
                "min_weight": min_weight,
                "max_weight": max_weight,
                "tipo": " | ".join(tipo),
                "teor": " | ".join(str(x) for x in teor),
                "visibility": visibility,
                "sort_by": sort_by,
                "limit": limit,
            }
        ]
    )

    write_analysis_excel(
        out_xlsx,
        {
            "summary": summary,
            "filtered": filtered[display_cols],
            "all_ranked": merged,
        },
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build configurable CAIXA jewelry opportunity report.")

    parser.add_argument("--catalog", default="data/processed/catalogo.csv")
    parser.add_argument("--vitrine", default="data/raw/caixa/api/vitrine_9859_2026-05-22.csv")
    parser.add_argument("--out", default="data/exports/opportunities.xlsx")

    parser.add_argument("--spot-24k", type=float, default=729.0)
    parser.add_argument("--fee-rate", type=float, default=0.06)
    parser.add_argument("--bid-markup", type=float, default=0.05)

    parser.add_argument("--contains", action="append", default=[])
    parser.add_argument("--contains-mode", choices=["any", "all"], default="any")
    parser.add_argument("--not-contains", action="append", default=[])

    parser.add_argument("--uf", action="append", default=[])
    parser.add_argument("--centralizadora", action="append", default=[])
    parser.add_argument("--location-contains", action="append", default=[])

    parser.add_argument("--min-value", type=float)
    parser.add_argument("--max-value", type=float)
    parser.add_argument("--min-weight", type=float)
    parser.add_argument("--max-weight", type=float)

    parser.add_argument("--tipo", action="append", default=[])
    parser.add_argument("--teor", action="append", type=float, default=[])

    parser.add_argument("--visibility", choices=["all", "visible", "catalog-only"], default="all")

    parser.add_argument("--lote", action="append", default=[])
    parser.add_argument("--contrato", action="append", default=[])

    parser.add_argument("--min-score", type=float)
    parser.add_argument("--min-spread", type=float)
    parser.add_argument("--max-cost-fino", type=float)

    parser.add_argument("--sort-by", choices=["score", "spread", "cost-fino", "value", "weight", "lot"], default="score")
    parser.add_argument("--limit", type=int)

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    build_report(
        catalog_csv=args.catalog,
        vitrine_csv=args.vitrine,
        out_xlsx=args.out,
        spot_24k=args.spot_24k,
        fee_rate=args.fee_rate,
        bid_markup=args.bid_markup,
        contains=args.contains,
        contains_mode=args.contains_mode,
        not_contains=args.not_contains,
        uf=args.uf,
        centralizadora=args.centralizadora,
        location_contains=args.location_contains,
        min_value=args.min_value,
        max_value=args.max_value,
        min_weight=args.min_weight,
        max_weight=args.max_weight,
        tipo=args.tipo,
        teor=args.teor,
        visibility=args.visibility,
        lote=args.lote,
        contrato=args.contrato,
        min_score=args.min_score,
        min_spread=args.min_spread,
        max_cost_fino=args.max_cost_fino,
        sort_by=args.sort_by,
        limit=args.limit,
    )

    print(f"Report exported -> {args.out}")


if __name__ == "__main__":
    main()