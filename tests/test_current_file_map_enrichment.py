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


def test_prepare_current_adds_caixa_detail_fields_from_active_lots(tmp_path: Path) -> None:
    processed = tmp_path / "processed"
    raw = tmp_path / "raw" / "caixa"
    processed.mkdir(parents=True)
    (raw / "current_all_active").mkdir(parents=True)

    pd.DataFrame(
        [
            {
                "lote": "0290.000045-3",
                "contrato": "0290.213.00064421-0",
                "descricao": "CINCO MOEDAS, DE: OURO, 22K, PESO LOTE: 39,67G",
                "valor_minimo": 15453,
                "peso_g": 39.67,
                "source_file": "121202629028520260428121217.pdf",
            }
        ]
    ).to_csv(processed / "current_all_active_catalog_lots.csv", index=False)

    pd.DataFrame(
        [
            {
                "id": "509f7141-d8a9-4cca-9d7a-9543f68c3a88",
                "numeroDolote": "0290.000045-3",
                "nuContrato": "0290.213.00064421-0",
                "deContrato": "CINCO MOEDAS, DE: OURO, 22K, PESO LOTE: 39,67G",
                "noCentralizadora": "BAURU, SP",
                "deLocalEndereco": "RUA Gustavo Maciel, 7-33 - Centro - Bauru/SP, BAURU, SP",
                "dataDeLance": "De 25/05/2026 à 25/05/2026",
                "dataResultado": "01/06/2026",
                "dataInicio": "25/05/2026",
                "dataFim": "25/05/2026",
                "edital": "121202629028520260427145223",
                "catalogo": "121202629028520260428121217",
                "urlImagemFrente": "/0290/0/0290213000644210/FRENTE.JPG",
                "source_uf": "SP",
                "source_cidade": "BAURU",
                "source_codigo_cidade": "9138",
            }
        ]
    ).to_csv(raw / "current_all_active" / "lots.csv", index=False)

    current = _prepare_current(processed, raw)

    row = current.iloc[0]
    assert row["uf"] == "SP"
    assert row["cidade"] == "BAURU"
    assert row["data_inicio_norm"] == "2026-05-25"
    assert row["caixa_lote_id"] == "509f7141-d8a9-4cca-9d7a-9543f68c3a88"
    assert row["caixa_centralizadora"] == "BAURU, SP"
    assert row["caixa_url_imagem_frente"] == "https://servicebus2.caixa.gov.br/vitrinearquivos/fotos/0290/0/0290213000644210/FRENTE.JPG"
    assert row["caixa_edital_url"] == "https://servicebus2.caixa.gov.br/vitrinearquivos/pdf/121202629028520260427145223.pdf"
    assert row["caixa_catalogo_url"] == "https://servicebus2.caixa.gov.br/vitrinearquivos/pdf/121202629028520260428121217.pdf"
