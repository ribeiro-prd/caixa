from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from caixa_joias.parsers.catalogo_pdf import parse_catalog_pdf
from caixa_joias.parsers.resultado_pdf import parse_results_pdf


def extract_file_id(value: object) -> str | None:
    match = re.search(r"(\d{20,})", str(value))
    return match.group(1) if match else None


def auction_key(file_id: object) -> str | None:
    if not isinstance(file_id, str):
        return None

    match = re.search(r"20\d{6}", file_id)
    if not match:
        return None

    return file_id[: match.start()]


def file_ts(file_id: object) -> str | None:
    if not isinstance(file_id, str):
        return None

    match = re.search(r"(20\d{6})(\d{6})?", file_id)
    if not match:
        return None

    date = match.group(1)
    time = match.group(2) or "000000"
    return date + time


def parse_result_folder(pdf_dir: str | Path, out_dir: str | Path, out_xlsx: str | Path) -> None:
    pdf_dir = Path(pdf_dir)
    out_dir = Path(out_dir)
    out_xlsx = Path(out_xlsx)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_xlsx.parent.mkdir(parents=True, exist_ok=True)

    catalog_rows = []
    catalog_summary = []
    result_rows = []
    result_summary = []

    for path in sorted(pdf_dir.glob("*.pdf")):
        try:
            catalog = parse_catalog_pdf(path)
            catalog_summary.append({"path": str(path), "catalog_rows": len(catalog)})
            if not catalog.empty:
                catalog["pdf_path"] = str(path)
                catalog_rows.append(catalog)
        except Exception as exc:
            catalog_summary.append({"path": str(path), "catalog_rows": 0, "error": str(exc)})

        try:
            result = parse_results_pdf(path)
            result_summary.append({"path": str(path), "result_rows": len(result)})
            if not result.empty:
                result["pdf_path"] = str(path)
                result_rows.append(result)
        except Exception as exc:
            result_summary.append({"path": str(path), "result_rows": 0, "error": str(exc)})

    catalog_df = pd.concat(catalog_rows, ignore_index=True) if catalog_rows else pd.DataFrame()
    result_df = pd.concat(result_rows, ignore_index=True) if result_rows else pd.DataFrame()

    catalog_df.to_csv(out_dir / "resultados_catalog_lots.csv", index=False, encoding="utf-8-sig")
    result_df.to_csv(out_dir / "resultados_lances.csv", index=False, encoding="utf-8-sig")

    pd.DataFrame(catalog_summary).to_csv(out_dir / "resultados_catalog_parse_summary.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(result_summary).to_csv(out_dir / "resultados_result_parse_summary.csv", index=False, encoding="utf-8-sig")

    if catalog_df.empty or result_df.empty:
        raise RuntimeError("No catalog or result rows parsed.")

    catalog_df["catalog_file_id"] = catalog_df["pdf_path"].apply(extract_file_id)
    catalog_df["auction_key"] = catalog_df["catalog_file_id"].apply(auction_key)
    catalog_df["catalog_file_ts"] = catalog_df["catalog_file_id"].apply(file_ts)

    result_df["result_file_id"] = result_df["pdf_path"].apply(extract_file_id)
    result_df["auction_key"] = result_df["result_file_id"].apply(auction_key)
    result_df["result_file_ts"] = result_df["result_file_id"].apply(file_ts)

    catalog_dedup = (
        catalog_df.sort_values(["auction_key", "lote", "catalog_file_ts"])
        .drop_duplicates(subset=["auction_key", "lote"], keep="last")
    )

    merged = result_df.merge(
        catalog_dedup,
        on=["auction_key", "lote"],
        how="left",
        suffixes=("_resultado", "_catalogo"),
    )

    merged["premium_vs_minimo"] = merged["lance"] / merged["valor_minimo"] - 1
    merged["lance_por_g"] = merged["lance"] / merged["peso_g"]
    merged["total_por_g"] = merged["total"] / merged["peso_g"]

    buyers = (
        merged.groupby("cpf_cnpj_mascarado", dropna=False)
        .agg(
            lotes=("lote", "count"),
            lance_total=("lance", "sum"),
            total_com_tarifa=("total", "sum"),
            lance_medio=("lance", "mean"),
        )
        .reset_index()
        .sort_values(["lance_total", "lotes"], ascending=[False, False])
    )

    buyers["share"] = buyers["lance_total"] / buyers["lance_total"].sum()

    merged.to_csv(out_dir / "resultados_lances_merged_catalog_keyed.csv", index=False, encoding="utf-8-sig")
    buyers.to_csv(out_dir / "resultados_buyers_summary.csv", index=False, encoding="utf-8-sig")

    with pd.ExcelWriter(out_xlsx, engine="openpyxl") as writer:
        merged.to_excel(writer, sheet_name="lances_merged_keyed", index=False)
        buyers.to_excel(writer, sheet_name="buyers_summary", index=False)
        pd.DataFrame(catalog_summary).to_excel(writer, sheet_name="catalog_parse_summary", index=False)
        pd.DataFrame(result_summary).to_excel(writer, sheet_name="result_parse_summary", index=False)

    print(f"catalog rows: {len(catalog_df)}")
    print(f"result rows: {len(result_df)}")
    print(f"merged rows: {len(merged)}")
    print(f"matched catalog: {merged['valor_minimo'].notna().sum()}")
    print(f"buyers: {len(buyers)}")
    print(f"Excel -> {out_xlsx}")
