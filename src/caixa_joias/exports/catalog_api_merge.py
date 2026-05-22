from __future__ import annotations

from pathlib import Path

import pandas as pd

from caixa_joias.exports.excel import write_analysis_excel


def merge_catalog_with_vitrine(
    catalog_csv: str | Path,
    vitrine_csv: str | Path,
    out_xlsx: str | Path,
) -> None:
    catalog = pd.read_csv(catalog_csv)
    vitrine = pd.read_csv(vitrine_csv)

    vitrine_small = vitrine[
        [
            "numeroDolote",
            "nuContrato",
            "valor",
            "deContrato",
            "catalogo",
            "edital",
            "urlImagemCapa",
            "urlImagemFrente",
            "urlImagemVerso",
        ]
    ].copy()

    merged = catalog.merge(
        vitrine_small,
        left_on="lote",
        right_on="numeroDolote",
        how="left",
    )

    merged["visivel_na_vitrine"] = merged["numeroDolote"].notna()

    only_catalog = merged[~merged["visivel_na_vitrine"]].copy()
    visible = merged[merged["visivel_na_vitrine"]].copy()

    write_analysis_excel(
        out_xlsx,
        {
            "merged_all": merged,
            "visible_in_vitrine": visible,
            "catalog_only": only_catalog,
        },
    )


if __name__ == "__main__":
    merge_catalog_with_vitrine(
        "data/processed/catalogo.csv",
        "data/raw/caixa/api/vitrine_9859_2026-05-22.csv",
        "data/exports/catalogo_vitrine_merged.xlsx",
    )