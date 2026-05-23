from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Iterable

import pandas as pd

try:
    import duckdb
except ImportError as exc:
    raise RuntimeError("duckdb is required. Install requirements-dashboard.txt.") from exc


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, low_memory=False)


def _first_existing(paths: Iterable[Path]) -> Path | None:
    for p in paths:
        if p.exists():
            return p
    return None


def _strip_accents(value: object) -> str:
    text = "" if pd.isna(value) else str(value)
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).upper()


def _extract_file_id(value: object) -> str | None:
    m = re.search(r"(\d{20,})", str(value))
    return m.group(1) if m else None


def _file_ts(file_id: object) -> str | None:
    if not isinstance(file_id, str):
        return None
    m = re.search(r"(20\d{6})(\d{6})?", file_id)
    if not m:
        return None
    return m.group(1) + (m.group(2) or "000000")


def _file_date(file_id: object) -> str | None:
    ts = _file_ts(file_id)
    if not ts:
        return None
    return f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"


def _auction_key(file_id: object) -> str | None:
    if not isinstance(file_id, str):
        return None
    m = re.search(r"20\d{6}", file_id)
    return file_id[:m.start()] if m else None


def _normalize_date(value: object) -> str | None:
    if pd.isna(value):
        return None
    s = str(value).strip()
    if not s:
        return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", s)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return None


def _classify_material(desc: object) -> str:
    t = _strip_accents(desc)
    if "METAL NAO NOBRE" in t:
        return "metal nao nobre"
    if "OURO BRANCO" in t:
        return "ouro branco"
    if "OURO RODINADO" in t or "RODINADO" in t:
        return "ouro rodinado"
    if "OURO BAIXO" in t:
        return "ouro baixo"
    if "OURO AMARELO" in t:
        return "ouro amarelo"
    if "OURO" in t:
        return "ouro"
    if "PRATA" in t:
        return "prata"
    if "PLATINA" in t:
        return "platina"
    if "PALADIO" in t:
        return "paladio"
    if "ACO" in t:
        return "aco"
    if "COBRE" in t:
        return "cobre"
    if "FOLHEADO" in t:
        return "folheado"
    return "outro"


def _classify_gold_purity(desc: object) -> str:
    t = _strip_accents(desc)
    has_gold = "OURO" in t or re.search(r"\b(24K|22K|21K|18K|14K|10K)\b", t)
    if not has_gold:
        return "sem ouro"

    patterns = [
        ("999 / 24k", [r"\b999\b", r"\b999[,.]?\d*/1000\b", r"\b24K\b"]),
        ("995", [r"\b995\b"]),
        ("990", [r"\b990\b"]),
        ("986", [r"\b986\b"]),
        ("916 / 22k", [r"\b916\b", r"\b22K\b"]),
        ("900", [r"\b900\b"]),
        ("875 / 21k", [r"\b875\b", r"\b21K\b"]),
        ("850", [r"\b850\b"]),
        ("800", [r"\b800\b"]),
        ("750 / 18k", [r"\b750\b", r"\b18K\b"]),
        ("585 / 14k", [r"\b585\b", r"\b14K\b"]),
        ("416 / 10k", [r"\b416\b", r"\b10K\b"]),
    ]
    for label, pats in patterns:
        if any(re.search(p, t) for p in pats):
            return label
    if "OURO BAIXO" in t:
        return "ouro baixo sem teor"
    return "ouro sem teor"


def _classify_type(desc: object) -> str:
    t = _strip_accents(desc)
    checks = [
        ("relogio", ["RELOGIO"]), ("tornozeleira", ["TORNOZELEIRA"]),
        ("alianca", ["ALIANCA"]), ("anel", ["ANEL"]), ("argola", ["ARGOLA"]),
        ("brinco", ["BRINCO"]), ("broche", ["BROCHE"]), ("colar", ["COLAR"]),
        ("corrente", ["CORRENTE"]), ("medalha", ["MEDALHA"]), ("par", ["PAR "]),
        ("pendente", ["PENDENTE", "PINGENTE"]), ("pulseira", ["PULSEIRA"]),
        ("lingote", ["LINGOTE"]), ("moeda", ["MOEDA"]),
    ]
    found = [label for label, tokens in checks if any(token in t for token in tokens)]
    if not found:
        return "outro"
    priority = ["moeda", "lingote", "anel", "brinco", "colar", "corrente", "pulseira", "pendente", "alianca", "relogio"]
    ordered = [x for x in priority if x in found] + [x for x in found if x not in priority]
    return ", ".join(ordered[:3])


def _classify_gems(desc: object) -> str:
    t = _strip_accents(desc)
    gems = []
    for label, tokens in [
        ("diamante", ["DIAMANTE", "BRILHANTE"]),
        ("perola", ["PEROLA"]),
        ("esmeralda", ["ESMERALDA"]),
        ("coral", ["CORAL"]),
        ("hematita", ["HEMATITA"]),
        ("pedra", ["PEDRA"]),
    ]:
        if any(tok in t for tok in tokens):
            gems.append(label)
    return ", ".join(dict.fromkeys(gems)) if gems else "sem gemas"


def _defect_status(desc: object) -> str:
    t = _strip_accents(desc)
    return "com defeito" if any(x in t for x in ["DEFEITO", "AMASSAD", "AVARI"]) else "sem defeito"


def _price_band(value: object) -> str:
    try:
        v = float(value)
    except Exception:
        return "sem preco"
    if v < 500:
        return "R$0-500"
    if v < 1000:
        return "R$500-1k"
    if v < 2000:
        return "R$1k-2k"
    if v < 5000:
        return "R$2k-5k"
    if v < 10000:
        return "R$5k-10k"
    if v < 20000:
        return "R$10k-20k"
    return "R$20k+"


def _weight_band(value: object) -> str:
    try:
        v = float(value)
    except Exception:
        return "sem peso"
    if v < 3:
        return "0-3g"
    if v < 5:
        return "3-5g"
    if v < 10:
        return "5-10g"
    if v < 20:
        return "10-20g"
    if v < 50:
        return "20-50g"
    if v < 100:
        return "50-100g"
    return "100g+"


def _num(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _str_keys(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = df[c].astype("string").fillna("")
    return df


def _features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "descricao" not in df.columns:
        df["descricao"] = ""
    df["material"] = df["descricao"].apply(_classify_material)
    df["gold_purity"] = df["descricao"].apply(_classify_gold_purity)
    df["item_type"] = df["descricao"].apply(_classify_type)
    df["gem_group"] = df["descricao"].apply(_classify_gems)
    df["defect_status"] = df["descricao"].apply(_defect_status)
    df["price_band"] = df["valor_minimo"].apply(_price_band) if "valor_minimo" in df.columns else "sem preco"
    df["weight_band"] = df["peso_g"].apply(_weight_band) if "peso_g" in df.columns else "sem peso"
    return df


def _lance_file_id(df: pd.DataFrame) -> pd.Series:
    for c in ["result_file_id", "source_file_resultado", "source_file", "pdf_path_resultado", "pdf_path"]:
        if c in df.columns:
            return df[c].astype(str) if c == "result_file_id" else df[c].apply(_extract_file_id)
    return pd.Series([None] * len(df), index=df.index)


def _enrich_file_map(df: pd.DataFrame, file_map: pd.DataFrame, key: str) -> pd.DataFrame:
    if df.empty or file_map.empty or key not in df.columns or "file_id" not in file_map.columns:
        return df
    cols = ["file_id"] + [c for c in ["uf", "cidade", "codigo_cidade", "data_inicio", "data_fim", "file_name", "path"] if c in file_map.columns]
    fmap = file_map[cols].drop_duplicates("file_id")
    out = df.merge(fmap, left_on=key, right_on="file_id", how="left", suffixes=("", "_filemap"))
    for c in ["uf", "cidade", "codigo_cidade", "data_inicio", "data_fim"]:
        alt = f"{c}_filemap"
        if alt in out.columns:
            out[c] = out[c].fillna(out[alt]) if c in out.columns else out[alt]
    return out


def _prepare_lances(processed: Path, raw: Path) -> pd.DataFrame:
    path = _first_existing([
        processed / "resultados_all_2025_analysis" / "resultados_lances_merged_catalog_keyed.csv",
        processed / "resultados_sp_analysis_cli" / "resultados_lances_merged_catalog_keyed.csv",
        processed / "resultados_sp_lances_merged_catalog_keyed.csv",
    ])
    df = _read_csv(path) if path else pd.DataFrame()
    if df.empty:
        return df

    df = _num(df, ["valor_minimo", "lance", "tarifa", "total", "peso_g", "premium_vs_minimo", "lance_por_g", "total_por_g"])
    df["result_file_id"] = _lance_file_id(df)
    df["auction_key"] = df["auction_key"] if "auction_key" in df.columns else df["result_file_id"].apply(_auction_key)
    df["auction_date"] = df["result_file_id"].apply(_file_date)
    file_map = _read_csv(raw / "resultados_all_2025" / "batch_result_files.csv")
    if file_map.empty:
        file_map = _read_csv(raw / "resultados_sp" / "result_files.csv")
    df = _enrich_file_map(df, file_map, "result_file_id")

    if "total" not in df.columns and {"lance", "tarifa"}.issubset(df.columns):
        df["total"] = df["lance"] + df["tarifa"]
    if "premium_vs_minimo" not in df.columns and {"lance", "valor_minimo"}.issubset(df.columns):
        df["premium_vs_minimo"] = df["lance"] / df["valor_minimo"] - 1
    if "lance_por_g" not in df.columns and {"lance", "peso_g"}.issubset(df.columns):
        df["lance_por_g"] = df["lance"] / df["peso_g"]
    if "total_por_g" not in df.columns and {"total", "peso_g"}.issubset(df.columns):
        df["total_por_g"] = df["total"] / df["peso_g"]
    df["ratio"] = 1 + df["premium_vs_minimo"]
    df = _str_keys(df, ["auction_key", "lote", "contrato"])
    return _features(df)


def _prepare_historical(processed: Path, raw: Path, lances: pd.DataFrame) -> pd.DataFrame:
    path = _first_existing([
        processed / "resultados_all_2025_analysis" / "resultados_catalog_lots.csv",
        processed / "resultados_sp_analysis_cli" / "resultados_catalog_lots.csv",
        processed / "resultados_sp_catalog_lots.csv",
    ])
    df = _read_csv(path) if path else pd.DataFrame()
    if df.empty:
        return df
    df = _num(df, ["valor_minimo", "peso_g"])
    if "pdf_path" in df.columns:
        df["catalog_file_id"] = df["pdf_path"].apply(_extract_file_id)
    elif "history_file_id" in df.columns:
        df["catalog_file_id"] = df["history_file_id"].astype(str)
    else:
        df["catalog_file_id"] = None
    df["auction_key"] = df["catalog_file_id"].apply(_auction_key)
    df["catalog_date"] = df["catalog_file_id"].apply(_file_date)
    df["catalog_ts"] = df["catalog_file_id"].apply(_file_ts)
    df = _str_keys(df, ["auction_key", "lote", "contrato"])
    df = _features(df)
    df = df.sort_values(["auction_key", "lote", "catalog_ts"]).drop_duplicates(["auction_key", "lote"], keep="last")
    if not lances.empty:
        sold = lances[["auction_key", "lote", "lance", "total", "premium_vs_minimo", "total_por_g", "cpf_cnpj_mascarado", "auction_date"]].copy()
        sold = _str_keys(sold, ["auction_key", "lote"])
        sold["sold"] = True
        df = df.merge(sold, on=["auction_key", "lote"], how="left", suffixes=("", "_result"))
        df["sold"] = df["sold"].fillna(False)
    else:
        df["sold"] = False
    df = _enrich_file_map(df, _read_csv(raw / "resultados_all_2025" / "batch_result_files.csv"), "catalog_file_id")
    return df


def _prepare_current(processed: Path, raw: Path) -> pd.DataFrame:
    path = _first_existing([
        processed / "current_all_active_catalog_lots.csv",
        processed / "history_sp_full_catalogo_only_clean.csv",
    ])
    df = _read_csv(path) if path else pd.DataFrame()
    if df.empty:
        return df
    df = _num(df, ["valor_minimo", "peso_g"])
    if "history_file_id" in df.columns:
        df["current_file_id"] = df["history_file_id"].astype(str)
    elif "pdf_path" in df.columns:
        df["current_file_id"] = df["pdf_path"].apply(_extract_file_id)
    else:
        df["current_file_id"] = None

    fmap = _read_csv(raw / "current_all_active" / "lot_file_map.csv")
    if not fmap.empty and "file_id" in fmap.columns:
        cols = [c for c in ["file_id", "lote", "contrato", "uf", "cidade", "codigo_cidade", "data_inicio", "data_fim", "tipo", "path"] if c in fmap.columns]
        fmap = fmap[cols].drop_duplicates()
        if {"lote", "contrato"}.issubset(df.columns) and {"lote", "contrato"}.issubset(fmap.columns):
            df = _str_keys(df, ["lote", "contrato"])
            fmap = _str_keys(fmap, ["lote", "contrato"])
            df = df.merge(fmap, left_on=["current_file_id", "lote", "contrato"], right_on=["file_id", "lote", "contrato"], how="left", suffixes=("", "_filemap"))
        else:
            df = df.merge(fmap.drop_duplicates("file_id"), left_on="current_file_id", right_on="file_id", how="left", suffixes=("", "_filemap"))
        for c in ["uf", "cidade", "codigo_cidade", "data_inicio", "data_fim"]:
            alt = f"{c}_filemap"
            if alt in df.columns:
                df[c] = df[c].fillna(df[alt]) if c in df.columns else df[alt]
    df["data_inicio_norm"] = df["data_inicio"].apply(_normalize_date) if "data_inicio" in df.columns else None
    df["data_fim_norm"] = df["data_fim"].apply(_normalize_date) if "data_fim" in df.columns else None
    df = _str_keys(df, ["lote", "contrato"])
    df = _features(df)
    df["minimo_por_g"] = df["valor_minimo"] / df["peso_g"]
    return df


def _prepare_buyers(lances: pd.DataFrame) -> pd.DataFrame:
    if lances.empty or "cpf_cnpj_mascarado" not in lances.columns:
        return pd.DataFrame()
    agg = (
        lances.groupby("cpf_cnpj_mascarado", dropna=False)
        .agg(
            lotes=("lote", "count"),
            lance_total=("lance", "sum"),
            total_com_tarifa=("total", "sum"),
            lance_medio=("lance", "mean"),
            premium_medio=("premium_vs_minimo", "mean"),
            ratio_medio=("ratio", "mean"),
            total_por_g_mediano=("total_por_g", "median"),
            estados=("uf", lambda x: ", ".join(sorted(set(str(v) for v in x.dropna() if str(v) != "nan")))[:100]),
            tipos=("item_type", lambda x: ", ".join(x.value_counts().head(3).index.astype(str))),
            materiais=("material", lambda x: ", ".join(x.value_counts().head(3).index.astype(str))),
            teores=("gold_purity", lambda x: ", ".join(x.value_counts().head(3).index.astype(str))),
            primeira_data=("auction_date", "min"),
            ultima_data=("auction_date", "max"),
        )
        .reset_index()
    )
    total = agg["lance_total"].sum()
    agg["share"] = agg["lance_total"] / total if total else 0
    return agg.sort_values(["lance_total", "lotes"], ascending=[False, False])


def _register(con: duckdb.DuckDBPyConnection, name: str, df: pd.DataFrame) -> None:
    con.register(f"{name}_df", df)
    con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM {name}_df")
    con.unregister(f"{name}_df")


def build_warehouse(
    processed_dir: str | Path = "data/processed",
    raw_dir: str | Path = "data/raw/caixa",
    out_db: str | Path = "data/warehouse/caixa_joias.duckdb",
    out_exports_dir: str | Path = "data/exports/warehouse",
) -> None:
    processed = Path(processed_dir)
    raw = Path(raw_dir)
    out_db = Path(out_db)
    out_exports = Path(out_exports_dir)
    out_db.parent.mkdir(parents=True, exist_ok=True)
    out_exports.mkdir(parents=True, exist_ok=True)

    lances = _prepare_lances(processed, raw)
    historical = _prepare_historical(processed, raw, lances)
    current = _prepare_current(processed, raw)
    buyers = _prepare_buyers(lances)

    con = duckdb.connect(str(out_db))
    _register(con, "lances", lances)
    _register(con, "historical_lots", historical)
    _register(con, "current_lots", current)
    _register(con, "buyers", buyers)
    _register(con, "history_periods", _read_csv(raw / "current_all_active" / "periods.csv"))
    _register(con, "history_files", _read_csv(raw / "current_all_active" / "unique_files.csv"))
    _register(con, "result_files", _read_csv(raw / "resultados_all_2025" / "batch_result_files.csv"))

    con.execute("""
        CREATE OR REPLACE VIEW v_market_summary AS
        SELECT
            (SELECT COUNT(*) FROM current_lots) AS lots_in_vitrine,
            (SELECT COUNT(*) FROM lances) AS winning_rows,
            (SELECT COUNT(DISTINCT cpf_cnpj_mascarado) FROM lances) AS buyer_count,
            (SELECT COUNT(DISTINCT auction_key) FROM lances) AS auction_count,
            (SELECT COALESCE(SUM(valor_minimo),0) FROM current_lots) AS current_offer_value,
            (SELECT COALESCE(SUM(lance),0) FROM lances) AS lance_total,
            (SELECT MEDIAN(minimo_por_g) FROM current_lots) AS current_median_min_per_g,
            (SELECT MEDIAN(premium_vs_minimo) FROM lances) AS median_premium,
            (SELECT AVG(ratio) FROM lances) AS avg_ratio,
            (SELECT MEDIAN(total_por_g) FROM lances) AS median_total_per_g,
            (SELECT COUNT(DISTINCT uf) FROM current_lots) AS active_states,
            (SELECT COUNT(DISTINCT cidade) FROM current_lots) AS active_cities,
            (SELECT SUM(peso_g)/1000 FROM current_lots) AS current_weight_kg,
            (SELECT MIN(COALESCE(auction_date,catalog_date)) FROM historical_lots) AS min_history_date,
            (SELECT MAX(COALESCE(auction_date,catalog_date)) FROM historical_lots) AS max_history_date,
            (SELECT MIN(data_inicio_norm) FROM current_lots) AS min_current_date,
            (SELECT MAX(data_fim_norm) FROM current_lots) AS max_current_date
    """)

    con.execute("""
        CREATE OR REPLACE VIEW v_buyer_concentration AS
        SELECT *, SUM(share) OVER (ORDER BY lance_total DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cumulative_share
        FROM buyers
        ORDER BY lance_total DESC
    """)

    con.execute("""
        CREATE OR REPLACE VIEW v_premium_bands AS
        SELECT CASE
            WHEN premium_vs_minimo <= .05 THEN '00 <= 5%'
            WHEN premium_vs_minimo <= .10 THEN '01 <= 10%'
            WHEN premium_vs_minimo <= .20 THEN '02 <= 20%'
            WHEN premium_vs_minimo <= .50 THEN '03 <= 50%'
            WHEN premium_vs_minimo <= 1.0 THEN '04 <= 100%'
            ELSE '05 > 100%' END AS premium_band,
            COUNT(*) AS lots, SUM(lance) AS lance_total, MEDIAN(total_por_g) AS median_total_per_g
        FROM lances
        GROUP BY 1 ORDER BY 1
    """)

    con.execute("""
        CREATE OR REPLACE VIEW v_strategy_backtest AS
        SELECT markup AS bid_markup,
               COUNT(*) FILTER (WHERE premium_vs_minimo <= markup) AS lots_that_would_win,
               COUNT(*) AS total_result_lots,
               COUNT(*) FILTER (WHERE premium_vs_minimo <= markup)::DOUBLE / NULLIF(COUNT(*),0) AS win_rate
        FROM lances
        CROSS JOIN (VALUES (.05),(.10),(.20),(.50),(1.00)) AS m(markup)
        GROUP BY markup ORDER BY markup
    """)

    for view_name, group_col in [
        ("v_premium_by_material", "material"),
        ("v_premium_by_type", "item_type"),
        ("v_premium_by_purity", "gold_purity"),
    ]:
        con.execute(f"""
            CREATE OR REPLACE VIEW {view_name} AS
            SELECT {group_col}, COUNT(*) AS lots, AVG(ratio) AS avg_ratio, MEDIAN(ratio) AS median_ratio,
                   AVG(premium_vs_minimo) AS avg_premium, MEDIAN(total_por_g) AS median_total_per_g
            FROM lances
            GROUP BY {group_col}
            HAVING COUNT(*) >= 5
            ORDER BY avg_ratio DESC
        """)

    con.execute("""
        CREATE OR REPLACE VIEW v_price_sweet_spot AS
        SELECT price_band, COUNT(*) AS catalog_lots, COUNT(*) FILTER (WHERE sold) AS sold_lots,
               COUNT(*) FILTER (WHERE sold)::DOUBLE / NULLIF(COUNT(*),0) AS sale_rate,
               AVG(1 + premium_vs_minimo) AS avg_ratio, MEDIAN(total_por_g) AS median_total_per_g
        FROM historical_lots
        GROUP BY price_band
        ORDER BY CASE price_band
            WHEN 'R$0-500' THEN 1 WHEN 'R$500-1k' THEN 2 WHEN 'R$1k-2k' THEN 3
            WHEN 'R$2k-5k' THEN 4 WHEN 'R$5k-10k' THEN 5 WHEN 'R$10k-20k' THEN 6
            WHEN 'R$20k+' THEN 7 ELSE 99 END
    """)

    con.execute("""
        CREATE OR REPLACE VIEW v_weight_sweet_spot AS
        SELECT weight_band, COUNT(*) AS catalog_lots, COUNT(*) FILTER (WHERE sold) AS sold_lots,
               COUNT(*) FILTER (WHERE sold)::DOUBLE / NULLIF(COUNT(*),0) AS sale_rate,
               AVG(1 + premium_vs_minimo) AS avg_ratio, MEDIAN(total_por_g) AS median_total_per_g
        FROM historical_lots
        GROUP BY weight_band
        ORDER BY CASE weight_band
            WHEN '0-3g' THEN 1 WHEN '3-5g' THEN 2 WHEN '5-10g' THEN 3
            WHEN '10-20g' THEN 4 WHEN '20-50g' THEN 5 WHEN '50-100g' THEN 6
            WHEN '100g+' THEN 7 ELSE 99 END
    """)

    con.execute("""
        CREATE OR REPLACE VIEW v_gem_value AS
        SELECT CASE WHEN gem_group = 'sem gemas' THEN 'sem gemas' ELSE 'com gemas' END AS gem_bucket,
               COUNT(*) AS lots,
               MEDIAN(valor_minimo / NULLIF(peso_g,0)) AS median_min_per_g,
               MEDIAN(total_por_g) AS median_total_per_g,
               AVG(ratio) AS avg_ratio
        FROM lances GROUP BY 1
    """)

    con.execute("""
        CREATE OR REPLACE VIEW v_geography AS
        SELECT COALESCE(uf,'NA') AS uf, COUNT(DISTINCT auction_key || '|' || lote) AS lots,
               SUM(lance) AS lance_total, MEDIAN(total_por_g) AS median_total_per_g,
               AVG(ratio) AS avg_ratio, COUNT(DISTINCT cpf_cnpj_mascarado) AS buyers
        FROM lances GROUP BY 1 ORDER BY lots DESC
    """)

    for view_name, group_col in [
        ("v_current_value_by_material", "material"),
        ("v_current_value_by_type", "item_type"),
        ("v_current_value_by_purity", "gold_purity"),
    ]:
        con.execute(f"""
            CREATE OR REPLACE VIEW {view_name} AS
            SELECT {group_col}, COUNT(*) AS lots, SUM(valor_minimo) AS offer_value,
                   MEDIAN(minimo_por_g) AS median_min_per_g, SUM(peso_g)/1000 AS weight_kg
            FROM current_lots
            GROUP BY {group_col}
            ORDER BY offer_value DESC
        """)

    con.execute("""
        CREATE OR REPLACE VIEW v_current_opportunities AS
        WITH material_ratio AS (SELECT material, MEDIAN(ratio) AS expected_material_ratio FROM lances GROUP BY material),
             type_ratio AS (SELECT item_type, MEDIAN(ratio) AS expected_type_ratio FROM lances GROUP BY item_type),
             purity_ratio AS (SELECT gold_purity, MEDIAN(ratio) AS expected_purity_ratio FROM lances GROUP BY gold_purity)
        SELECT c.*,
               COALESCE(m.expected_material_ratio,1.50) AS expected_material_ratio,
               COALESCE(t.expected_type_ratio,1.50) AS expected_type_ratio,
               COALESCE(p.expected_purity_ratio,1.50) AS expected_purity_ratio,
               (COALESCE(m.expected_material_ratio,1.50)+COALESCE(t.expected_type_ratio,1.50)+COALESCE(p.expected_purity_ratio,1.50))/3 AS expected_ratio,
               c.valor_minimo*((COALESCE(m.expected_material_ratio,1.50)+COALESCE(t.expected_type_ratio,1.50)+COALESCE(p.expected_purity_ratio,1.50))/3) AS expected_bid,
               c.minimo_por_g AS current_min_per_g,
               CASE WHEN UPPER(COALESCE(c.descricao,'')) LIKE '%OURO%'
                         AND UPPER(COALESCE(c.descricao,'')) NOT LIKE '%RELÓGIO%'
                         AND UPPER(COALESCE(c.descricao,'')) NOT LIKE '%RELOGIO%'
                         AND UPPER(COALESCE(c.descricao,'')) NOT LIKE '%METAL NÃO NOBRE%'
                         AND UPPER(COALESCE(c.descricao,'')) NOT LIKE '%METAL NAO NOBRE%'
                    THEN 1 ELSE 0 END AS clean_gold_flag,
               CASE WHEN c.minimo_por_g IS NULL THEN 0
                    WHEN c.minimo_por_g <= 350 THEN 100
                    WHEN c.minimo_por_g <= 450 THEN 80
                    WHEN c.minimo_por_g <= 550 THEN 60
                    WHEN c.minimo_por_g <= 650 THEN 40
                    ELSE 20 END
               + CASE WHEN c.gold_purity IN ('999 / 24k','995','990','986','916 / 22k','900') THEN 25 ELSE 0 END
               + CASE WHEN c.gem_group <> 'sem gemas' THEN 10 ELSE 0 END
               - CASE WHEN c.defect_status = 'com defeito' THEN 10 ELSE 0 END AS opportunity_score
        FROM current_lots c
        LEFT JOIN material_ratio m USING(material)
        LEFT JOIN type_ratio t USING(item_type)
        LEFT JOIN purity_ratio p USING(gold_purity)
    """)

    con.execute("""
        CREATE OR REPLACE VIEW v_universe AS
        SELECT (SELECT COUNT(*) FROM historical_lots) AS historical_catalog_lots,
               (SELECT COUNT(*) FROM current_lots) AS current_lots,
               (SELECT COUNT(*) FROM lances) AS arrematacoes,
               (SELECT COUNT(DISTINCT cpf_cnpj_mascarado) FROM lances) AS compradores,
               (SELECT COUNT(DISTINCT auction_key) FROM lances) AS leiloes,
               (SELECT COUNT(DISTINCT uf) FROM lances) AS historical_states,
               (SELECT COUNT(DISTINCT cidade) FROM lances) AS historical_cities,
               (SELECT SUM(lance) FROM lances) AS historical_lance_total,
               (SELECT SUM(valor_minimo) FROM current_lots) AS current_offer_value,
               (SELECT SUM(peso_g)/1000 FROM current_lots) AS current_weight_kg,
               (SELECT MEDIAN(minimo_por_g) FROM current_lots) AS current_median_min_per_g,
               (SELECT MIN(COALESCE(auction_date,catalog_date)) FROM historical_lots) AS min_history_date,
               (SELECT MAX(COALESCE(auction_date,catalog_date)) FROM historical_lots) AS max_history_date,
               (SELECT MIN(data_inicio_norm) FROM current_lots) AS min_current_date,
               (SELECT MAX(data_fim_norm) FROM current_lots) AS max_current_date
    """)

    export_names = [
        "v_market_summary", "v_buyer_concentration", "v_premium_bands", "v_strategy_backtest",
        "v_premium_by_material", "v_premium_by_type", "v_premium_by_purity", "v_price_sweet_spot",
        "v_weight_sweet_spot", "v_gem_value", "v_geography", "v_current_value_by_material",
        "v_current_value_by_type", "v_current_value_by_purity", "v_current_opportunities", "v_universe",
    ]

    with pd.ExcelWriter(out_exports / "warehouse_summary.xlsx", engine="openpyxl") as writer:
        for name in export_names:
            df = con.execute(f"SELECT * FROM {name}").df()
            df.to_csv(out_exports / f"{name}.csv", index=False, encoding="utf-8-sig")
            df.to_excel(writer, sheet_name=name.replace("v_", "")[:31], index=False)

    con.close()

    print(f"DuckDB -> {out_db}")
    print(f"Exports -> {out_exports}")
    print(f"Lances rows -> {len(lances)}")
    print(f"Current rows -> {len(current)}")
    print(f"Historical catalog rows -> {len(historical)}")
    print(f"Buyers -> {len(buyers)}")
