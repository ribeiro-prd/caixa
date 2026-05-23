from __future__ import annotations

from pathlib import Path
import pandas as pd

try:
    import duckdb
except ImportError as exc:
    raise RuntimeError("duckdb is required. Install requirements-dashboard.txt.") from exc


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _register(con, name: str, df: pd.DataFrame) -> None:
    con.register(f"{name}_df", df)
    con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM {name}_df")
    con.unregister(f"{name}_df")


def build_warehouse(
    processed_dir: str | Path = "data/processed",
    raw_dir: str | Path = "data/raw/caixa",
    out_db: str | Path = "data/warehouse/caixa_joias.duckdb",
    out_exports_dir: str | Path = "data/exports/warehouse",
) -> None:
    processed_dir = Path(processed_dir)
    raw_dir = Path(raw_dir)
    out_db = Path(out_db)
    out_exports_dir = Path(out_exports_dir)
    out_db.parent.mkdir(parents=True, exist_ok=True)
    out_exports_dir.mkdir(parents=True, exist_ok=True)

    lances_path = _first_existing([
        processed_dir / "resultados_sp_analysis_cli" / "resultados_lances_merged_catalog_keyed.csv",
        processed_dir / "resultados_sp_lances_merged_catalog_keyed.csv",
    ])
    buyers_path = _first_existing([
        processed_dir / "resultados_sp_analysis_cli" / "resultados_buyers_summary.csv",
        processed_dir / "resultados_sp_buyers_summary.csv",
    ])
    catalog_path = _first_existing([
        processed_dir / "history_sp_full_catalogo_only_clean.csv",
        processed_dir / "resultados_sp_analysis_cli" / "resultados_catalog_lots.csv",
        processed_dir / "resultados_sp_catalog_lots.csv",
    ])

    lances = _read_csv(lances_path) if lances_path else pd.DataFrame()
    buyers = _read_csv(buyers_path) if buyers_path else pd.DataFrame()
    catalog_lots = _read_csv(catalog_path) if catalog_path else pd.DataFrame()

    history_dir = raw_dir / "history_sp_full"
    history_lots = _read_csv(history_dir / "lots.csv")
    history_periods = _read_csv(history_dir / "periods.csv")
    history_files = _read_csv(history_dir / "unique_files.csv")
    result_files = _read_csv(raw_dir / "resultados_sp" / "result_files.csv")

    if not lances.empty:
        if "total_com_tarifa" not in lances.columns and {"lance", "tarifa"}.issubset(lances.columns):
            lances["total_com_tarifa"] = lances["lance"] + lances["tarifa"]
        if "premium_vs_minimo" not in lances.columns and {"lance", "valor_minimo"}.issubset(lances.columns):
            lances["premium_vs_minimo"] = lances["lance"] / lances["valor_minimo"] - 1
        if "lance_por_g" not in lances.columns and {"lance", "peso_g"}.issubset(lances.columns):
            lances["lance_por_g"] = lances["lance"] / lances["peso_g"]
        if "total_por_g" not in lances.columns and {"total", "peso_g"}.issubset(lances.columns):
            lances["total_por_g"] = lances["total"] / lances["peso_g"]

    if not buyers.empty and "share" not in buyers.columns and "lance_total" in buyers.columns:
        total = buyers["lance_total"].sum()
        buyers["share"] = buyers["lance_total"] / total if total else 0

    con = duckdb.connect(str(out_db))
    _register(con, "lances", lances)
    _register(con, "buyers", buyers)
    _register(con, "catalog_lots", catalog_lots)
    _register(con, "history_lots", history_lots)
    _register(con, "history_periods", history_periods)
    _register(con, "history_files", history_files)
    _register(con, "result_files", result_files)

    con.execute("""
        CREATE OR REPLACE VIEW v_market_summary AS
        SELECT COUNT(*) AS winning_rows,
               COUNT(DISTINCT cpf_cnpj_mascarado) AS buyer_count,
               COUNT(DISTINCT auction_key) AS auction_count,
               SUM(lance) AS lance_total,
               SUM(total) AS total_with_fee,
               AVG(premium_vs_minimo) AS avg_premium,
               MEDIAN(premium_vs_minimo) AS median_premium,
               MEDIAN(total_por_g) AS median_total_per_g
        FROM lances
    """)
    con.execute("""
        CREATE OR REPLACE VIEW v_buyer_concentration AS
        SELECT cpf_cnpj_mascarado, lotes, lance_total, total_com_tarifa, lance_medio, share,
               SUM(share) OVER (ORDER BY lance_total DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cumulative_share
        FROM buyers
        ORDER BY lance_total DESC
    """)
    con.execute("""
        CREATE OR REPLACE VIEW v_premium_bands AS
        SELECT CASE
                 WHEN premium_vs_minimo <= 0.05 THEN '00 <= 5%'
                 WHEN premium_vs_minimo <= 0.10 THEN '01 <= 10%'
                 WHEN premium_vs_minimo <= 0.20 THEN '02 <= 20%'
                 WHEN premium_vs_minimo <= 0.50 THEN '03 <= 50%'
                 WHEN premium_vs_minimo <= 1.00 THEN '04 <= 100%'
                 ELSE '05 > 100%'
               END AS premium_band,
               COUNT(*) AS lots,
               SUM(lance) AS lance_total,
               MEDIAN(total_por_g) AS median_total_per_g
        FROM lances
        WHERE premium_vs_minimo IS NOT NULL
        GROUP BY 1
        ORDER BY 1
    """)
    con.execute("""
        CREATE OR REPLACE VIEW v_strategy_backtest AS
        SELECT 0.05 AS bid_markup, COUNT(*) FILTER (WHERE premium_vs_minimo <= 0.05) AS lots_that_would_win, COUNT(*) AS total_result_lots, COUNT(*) FILTER (WHERE premium_vs_minimo <= 0.05)::DOUBLE / COUNT(*) AS win_rate FROM lances
        UNION ALL SELECT 0.10, COUNT(*) FILTER (WHERE premium_vs_minimo <= 0.10), COUNT(*), COUNT(*) FILTER (WHERE premium_vs_minimo <= 0.10)::DOUBLE / COUNT(*) FROM lances
        UNION ALL SELECT 0.20, COUNT(*) FILTER (WHERE premium_vs_minimo <= 0.20), COUNT(*), COUNT(*) FILTER (WHERE premium_vs_minimo <= 0.20)::DOUBLE / COUNT(*) FROM lances
        UNION ALL SELECT 0.50, COUNT(*) FILTER (WHERE premium_vs_minimo <= 0.50), COUNT(*), COUNT(*) FILTER (WHERE premium_vs_minimo <= 0.50)::DOUBLE / COUNT(*) FROM lances
        UNION ALL SELECT 1.00, COUNT(*) FILTER (WHERE premium_vs_minimo <= 1.00), COUNT(*), COUNT(*) FILTER (WHERE premium_vs_minimo <= 1.00)::DOUBLE / COUNT(*) FROM lances
    """)
    con.execute("""
        CREATE OR REPLACE VIEW v_opportunity_candidates AS
        SELECT *
        FROM lances
        WHERE COALESCE(UPPER(descricao), '') LIKE '%OURO%'
          AND COALESCE(UPPER(descricao), '') NOT LIKE '%RELÓGIO%'
          AND COALESCE(UPPER(descricao), '') NOT LIKE '%RELOGIO%'
          AND COALESCE(UPPER(descricao), '') NOT LIKE '%METAL NÃO NOBRE%'
          AND COALESCE(UPPER(descricao), '') NOT LIKE '%METAL NAO NOBRE%'
          AND premium_vs_minimo <= 0.20
        ORDER BY total_por_g NULLS LAST, premium_vs_minimo
    """)

    views = ["v_market_summary", "v_buyer_concentration", "v_premium_bands", "v_strategy_backtest", "v_opportunity_candidates"]
    exported = {}
    for view in views:
        data = con.execute(f"SELECT * FROM {view}").df()
        data.to_csv(out_exports_dir / f"{view}.csv", index=False, encoding="utf-8-sig")
        exported[view] = data

    with pd.ExcelWriter(out_exports_dir / "warehouse_summary.xlsx", engine="openpyxl") as writer:
        for view, data in exported.items():
            data.to_excel(writer, sheet_name=view.replace("v_", "")[:31], index=False)

    con.close()
    print(f"DuckDB -> {out_db}")
    print(f"Exports -> {out_exports_dir}")
