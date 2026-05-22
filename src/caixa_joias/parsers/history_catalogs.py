from __future__ import annotations

from pathlib import Path

import pandas as pd

from caixa_joias.parsers.catalogo_pdf import parse_catalog_pdf


def parse_history_catalogs(
    history_dir: str | Path,
    out_csv: str | Path,
    out_summary_csv: str | Path,
) -> None:
    history_dir = Path(history_dir)
    out_csv = Path(out_csv)
    out_summary_csv = Path(out_summary_csv)

    unique_files_path = history_dir / "unique_files.csv"
    unique_files = pd.read_csv(unique_files_path)

    rows = []
    summary_rows = []

    for _, file_row in unique_files.iterrows():
        path = Path(str(file_row["path"]))

        if not path.exists():
            summary_rows.append({
                "file_id": file_row["file_id"],
                "tipo": file_row["tipo"],
                "path": str(path),
                "status": "missing",
                "rows": 0,
            })
            continue

        try:
            df = parse_catalog_pdf(path)
        except Exception as exc:
            summary_rows.append({
                "file_id": file_row["file_id"],
                "tipo": file_row["tipo"],
                "path": str(path),
                "status": f"error: {exc}",
                "rows": 0,
            })
            continue

        if df.empty:
            summary_rows.append({
                "file_id": file_row["file_id"],
                "tipo": file_row["tipo"],
                "path": str(path),
                "status": "no_catalog_rows",
                "rows": 0,
            })
            continue

        df["history_file_id"] = file_row["file_id"]
        df["history_file_type"] = file_row["tipo"]
        df["history_pdf_path"] = str(path)

        rows.append(df)

        summary_rows.append({
            "file_id": file_row["file_id"],
            "tipo": file_row["tipo"],
            "path": str(path),
            "status": "parsed",
            "rows": len(df),
        })

    final = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    summary = pd.DataFrame(summary_rows)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_summary_csv.parent.mkdir(parents=True, exist_ok=True)

    final.to_csv(out_csv, index=False, encoding="utf-8-sig")
    summary.to_csv(out_summary_csv, index=False, encoding="utf-8-sig")

    print(f"Parsed catalog rows: {len(final)}")
    print(f"Summary rows: {len(summary)}")
    print(f"Output: {out_csv}")
    print(f"Summary: {out_summary_csv}")


if __name__ == "__main__":
    parse_history_catalogs(
        "data/raw/caixa/history_sp_full",
        "data/processed/history_sp_full_catalog_lots.csv",
        "data/processed/history_sp_full_catalog_parse_summary.csv",
    )