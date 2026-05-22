from __future__ import annotations

from pathlib import Path

import fitz
import pandas as pd


def read_pdf_sample(path: Path, max_pages: int = 10) -> tuple[int, str]:
    doc = fitz.open(path)
    page_count = doc.page_count

    parts = []
    for i in range(min(page_count, max_pages)):
        parts.append(doc[i].get_text("text") or "")

    doc.close()
    return page_count, "\n".join(parts)


def classify_pdf_text(text: str) -> str:
    t = text.upper()

    if "RELAÇÃO DE VENCEDORES" in t or "RELACAO DE VENCEDORES" in t:
        return "resultado_vencedores"

    if "RESULTADO" in t and ("CPF" in t or "CNPJ" in t or "ARREMATA" in t):
        return "resultado_possivel"

    if "CATÁLOGO ATUALIZADO" in t or "CATALOGO ATUALIZADO" in t:
        return "catalogo_atualizado"

    if "LOTE / CONTRATO" in t and "DESCRIÇÃO" in t and "VALOR" in t:
        return "catalogo"

    if "EDITAL" in t or "LICITAÇÃO DE JÓIAS" in t or "LICITACAO DE JOIAS" in t:
        return "edital"

    return "desconhecido"


def build_pdf_inventory(history_dir: str | Path, out_csv: str | Path) -> None:
    history_dir = Path(history_dir)
    out_csv = Path(out_csv)

    unique_files = pd.read_csv(history_dir / "unique_files.csv")
    rows = []

    for _, row in unique_files.iterrows():
        path = Path(str(row["path"]))

        record = {
            "tipo_original": row.get("tipo"),
            "file_id": row.get("file_id"),
            "download_ok": row.get("download_ok"),
            "path": str(path),
            "exists": path.exists(),
            "page_count": None,
            "detected_type": None,
            "sample_text": "",
        }

        if not path.exists():
            record["detected_type"] = "missing"
            rows.append(record)
            continue

        try:
            page_count, sample_text = read_pdf_sample(path)
            record["page_count"] = page_count
            record["sample_text"] = " ".join(sample_text.split())[:3000]
            record["detected_type"] = classify_pdf_text(sample_text)
        except Exception as exc:
            record["detected_type"] = f"error: {exc}"

        rows.append(record)

    df = pd.DataFrame(rows)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")

    print(df["detected_type"].value_counts(dropna=False).to_string())
    print(f"Output -> {out_csv}")


if __name__ == "__main__":
    build_pdf_inventory(
        "data/raw/caixa/history_sp_full",
        "data/processed/history_sp_full_pdf_inventory.csv",
    )