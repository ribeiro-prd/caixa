from pathlib import Path

import pandas as pd

from caixa_joias.warehouse.build import _prepare_historical, _prepare_lances, _resultados_file_map


def test_resultados_json_file_map_recovers_auction_dates(tmp_path: Path) -> None:
    raw = tmp_path / "raw" / "caixa"
    raw_json = raw / "resultados_all_2025" / "raw_json"
    raw_json.mkdir(parents=True)

    (raw_json / "resultados_MG_2803_2025-01-01_2026-05-22.json").write_text(
        """
        [
          {
            "coLeilao": "001/2026",
            "codigoCentralizadora": "0012",
            "dtInicio": "23/01/2026",
            "dtFim": "23/01/2026",
            "noUnidade": "BELO HORIZONTE",
            "arquivosPublicados": [
              {"nome": "0012026121220260123105426", "tipoArquivo": "Ata"},
              {"nome": "0012026121220260109135818", "tipoArquivo": "Catalogo"}
            ]
          },
          {
            "coLeilao": "002/2026",
            "codigoCentralizadora": "0012",
            "dtInicio": "30/01/2026",
            "dtFim": "30/01/2026",
            "noUnidade": "BELO HORIZONTE",
            "arquivosPublicados": [
              {"nome": "0012026121220260130105426", "tipoArquivo": "Ata"},
              {"nome": "0012026121220260129135818", "tipoArquivo": "Catalogo"}
            ]
          }
        ]
        """,
        encoding="utf-8",
    )

    file_map = _resultados_file_map(raw)

    assert set(file_map["dt_inicio"]) == {"2026-01-23", "2026-01-30"}
    assert set(file_map["co_leilao"]) == {"001/2026", "002/2026"}


def test_prepare_historical_and_lances_prefer_resultados_json_dates(tmp_path: Path) -> None:
    processed = tmp_path / "processed"
    raw = tmp_path / "raw" / "caixa"
    analysis = processed / "resultados_all_2025_analysis"
    raw_json = raw / "resultados_all_2025" / "raw_json"
    analysis.mkdir(parents=True)
    raw_json.mkdir(parents=True)

    (raw_json / "resultados_MG_2803_2025-01-01_2026-05-22.json").write_text(
        """
        [
          {
            "coLeilao": "001/2026",
            "codigoCentralizadora": "0012",
            "dtInicio": "23/01/2026",
            "dtFim": "23/01/2026",
            "noUnidade": "BELO HORIZONTE",
            "arquivosPublicados": [
              {"nome": "0012026121220260123105426", "tipoArquivo": "Ata"},
              {"nome": "0012026121220260109135818", "tipoArquivo": "Catalogo"}
            ]
          },
          {
            "coLeilao": "002/2026",
            "codigoCentralizadora": "0012",
            "dtInicio": "30/01/2026",
            "dtFim": "30/01/2026",
            "noUnidade": "BELO HORIZONTE",
            "arquivosPublicados": [
              {"nome": "0012026121220260130105426", "tipoArquivo": "Ata"},
              {"nome": "0012026121220260129135818", "tipoArquivo": "Catalogo"}
            ]
          }
        ]
        """,
        encoding="utf-8",
    )

    pd.DataFrame(
        [
            {
                "source_file_resultado": "0012026121220260123105426.pdf",
                "lote": "0012.000001-6",
                "contrato": "A",
                "descricao": "UM ANEL DE OURO, PESO LOTE: 10,00G",
                "valor_minimo": 1000,
                "lance": 1200,
                "tarifa": 72,
                "total": 1272,
                "peso_g": 10,
                "premium_vs_minimo": 0.2,
                "cpf_cnpj_mascarado": "111.XXX.XXX-11",
            },
            {
                "source_file_resultado": "0012026121220260130105426.pdf",
                "lote": "0012.000002-4",
                "contrato": "B",
                "descricao": "UM COLAR DE OURO, PESO LOTE: 20,00G",
                "valor_minimo": 2000,
                "lance": 2200,
                "tarifa": 132,
                "total": 2332,
                "peso_g": 20,
                "premium_vs_minimo": 0.1,
                "cpf_cnpj_mascarado": "222.XXX.XXX-22",
            },
        ]
    ).to_csv(analysis / "resultados_lances_merged_catalog_keyed.csv", index=False)

    pd.DataFrame(
        [
            {
                "pdf_path": "data/raw/caixa/resultados_all_2025/pdf/0012026121220260109135818.pdf",
                "lote": "0012.000001-6",
                "contrato": "A",
                "descricao": "UM ANEL DE OURO, PESO LOTE: 10,00G",
                "valor_minimo": 1000,
                "peso_g": 10,
            },
            {
                "pdf_path": "data/raw/caixa/resultados_all_2025/pdf/0012026121220260129135818.pdf",
                "lote": "0012.000002-4",
                "contrato": "B",
                "descricao": "UM COLAR DE OURO, PESO LOTE: 20,00G",
                "valor_minimo": 2000,
                "peso_g": 20,
            },
        ]
    ).to_csv(analysis / "resultados_catalog_lots.csv", index=False)

    lances = _prepare_lances(processed, raw)
    historical = _prepare_historical(processed, raw, lances)

    assert set(lances["auction_date"]) == {"2026-01-23", "2026-01-30"}
    assert set(historical["catalog_date"]) == {"2026-01-23", "2026-01-30"}
    assert set(lances["auction_key"]) == {"0012|001/2026|2026-01-23", "0012|002/2026|2026-01-30"}
