from pathlib import Path

import pandas as pd

from caixa_joias.warehouse.build import _prepare_current


def test_prepare_current_falls_back_to_current_file_map(tmp_path: Path) -> None:
    processed = tmp_path / "processed"
    raw = tmp_path / "raw" / "caixa"
    processed.mkdir(parents=True)
    (raw / "current_all_active").mkdir(parents=True)

    pd.DataFrame(
        [
            {
                "lote": "CATALOG-ONLY-LOT",
                "contrato": "CATALOG-ONLY-CONTRACT",
                "descricao": "UM ANEL DE OURO, PESO LOTE: 10,00G",
                "valor_minimo": 1000,
                "peso_g": 10,
                "history_file_id": "1072026868620260417133908",
            }
        ]
    ).to_csv(processed / "current_all_active_catalog_lots.csv", index=False)

    pd.DataFrame(
        [
            {
                "lote": "DIFFERENT-LOT",
                "contrato": "DIFFERENT-CONTRACT",
                "source_uf": "SP",
                "source_cidade": "SAO PAULO",
                "source_codigo_cidade": "9859",
                "source_data_inicio": "2026-05-01",
                "source_data_fim": "2026-05-02",
            }
        ]
    ).to_csv(raw / "current_all_active" / "lots.csv", index=False)

    pd.DataFrame(
        [
            {
                "uf": "MG",
                "cidade": "BELO HORIZONTE",
                "codigo_cidade": "2803",
                "data_inicio": "2026-05-08",
                "data_fim": "2026-05-09",
                "lote": "CATALOG-ONLY-LOT",
                "contrato": "CATALOG-ONLY-CONTRACT",
                "tipo": "catalogo",
                "file_id": "1072026868620260417133908",
                "download_ok": True,
                "path": "data/raw/caixa/current_all_active/pdf/catalogo/1072026868620260417133908.pdf",
            }
        ]
    ).to_csv(raw / "current_all_active" / "lot_file_map.csv", index=False)

    current = _prepare_current(processed, raw)

    row = current.iloc[0]
    assert row["uf"] == "MG"
    assert row["cidade"] == "BELO HORIZONTE"
    assert str(row["codigo_cidade"]) == "2803"
    assert row["data_inicio_norm"] == "2026-05-08"
    assert row["data_fim_norm"] == "2026-05-09"
