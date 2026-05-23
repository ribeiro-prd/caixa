from __future__ import annotations

import re
import json
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
    return pd.read_csv(path, dtype=str, low_memory=False)


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





def _normalize_file_id(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None

    text = str(value).strip()
    match = re.search(r"(\d{20,})", text)

    if match:
        return match.group(1)

    return None



def _auction_key(file_id: object) -> str | None:
    file_id = _normalize_file_id(file_id)
    if not file_id:
        return None

    for match in re.finditer(r"20\d{6}", file_id):
        date_part = match.group(0)
        month = int(date_part[4:6])
        day = int(date_part[6:8])

        if 1 <= month <= 12 and 1 <= day <= 31:
            return file_id[: match.start()]

    return None

def _valid_yyyymmdd(value: str) -> bool:
    if not re.fullmatch(r"20\d{6}", value):
        return False

    month = int(value[4:6])
    day = int(value[6:8])

    return 1 <= month <= 12 and 1 <= day <= 31



def _valid_yyyymmdd(value: str) -> bool:
    if not re.fullmatch(r"20\d{6}", value):
        return False

    month = int(value[4:6])
    day = int(value[6:8])

    return 1 <= month <= 12 and 1 <= day <= 31


def _file_ts(file_id: object) -> str | None:
    file_id = _normalize_file_id(file_id)
    if not file_id:
        return None

    candidates = []

    for match in re.finditer(r"(20\d{6})(\d{6})?", file_id):
        date_part = match.group(1)
        time_part = match.group(2) or "000000"

        if _valid_yyyymmdd(date_part):
            candidates.append(date_part + time_part)

    if not candidates:
        return None

    return candidates[-1]


def _file_date(file_id: object) -> str | None:
    ts = _file_ts(file_id)

    if not ts or len(ts) < 8:
        return None

    return f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"


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


def _resultados_json_file_map(raw: Path) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    raw_json_dir = raw / "resultados_all_2025" / "raw_json"

    if not raw_json_dir.exists():
        raw_json_dir = raw / "resultados_sp" / "raw_json"

    if not raw_json_dir.exists():
        return pd.DataFrame()

    for path in sorted(raw_json_dir.glob("*.json")):
        match = re.match(r"resultados_([A-Z]{2})_(\d+)_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.json$", path.name)
        source_uf = match.group(1) if match else None
        source_codigo = match.group(2) if match else None

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        auctions = payload if isinstance(payload, list) else [payload]

        for auction in auctions:
            if not isinstance(auction, dict):
                continue

            files = auction.get("arquivosPublicados") or []
            if isinstance(files, str):
                try:
                    files = json.loads(files.replace("'", '"'))
                except Exception:
                    files = []

            if not isinstance(files, list):
                continue

            for file_info in files:
                if not isinstance(file_info, dict):
                    continue

                file_id = _normalize_file_id(file_info.get("nome") or file_info.get("documento") or file_info.get("arquivo"))
                if not file_id:
                    continue

                rows.append(
                    {
                        "file_id": file_id,
                        "tipo_arquivo": file_info.get("tipoArquivo") or file_info.get("tipo") or file_info.get("descricao"),
                        "co_leilao": auction.get("coLeilao") or auction.get("co_leilao"),
                        "dt_inicio": _normalize_date(auction.get("dtInicio") or auction.get("dataInicio") or auction.get("inicioLance")),
                        "dt_fim": _normalize_date(auction.get("dtFim") or auction.get("dataFim") or auction.get("fimLance")),
                        "codigo_centralizadora": auction.get("codigoCentralizadora"),
                        "no_unidade": auction.get("noUnidade"),
                        "uf": source_uf,
                        "codigo_cidade": source_codigo,
                        "resultados_json_path": str(path),
                    }
                )

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows).drop_duplicates("file_id")


def _resultados_file_map(raw: Path) -> pd.DataFrame:
    batch = _read_csv(raw / "resultados_all_2025" / "batch_result_files.csv")
    if batch.empty:
        batch = _read_csv(raw / "resultados_sp" / "result_files.csv")

    json_map = _resultados_json_file_map(raw)

    if batch.empty:
        return json_map
    if json_map.empty:
        return batch

    batch = batch.copy()
    json_map = json_map.copy()
    batch["_join_file_id"] = batch["file_id"].apply(_normalize_file_id) if "file_id" in batch.columns else None
    json_map["_join_file_id"] = json_map["file_id"].apply(_normalize_file_id)
    out = batch.merge(json_map.drop(columns=["file_id"]), on="_join_file_id", how="outer", suffixes=("", "_json"))

    if "file_id" not in out.columns:
        out["file_id"] = out["_join_file_id"]

    for col in ["uf", "cidade", "codigo_cidade"]:
        alt = f"{col}_json"
        if alt in out.columns:
            if col in out.columns:
                out[col] = out[col].fillna(out[alt])
            else:
                out[col] = out[alt]

    return out.drop(columns=[c for c in ["_join_file_id"] if c in out.columns])


def _auction_key_from_metadata(df: pd.DataFrame) -> pd.Series:
    def build(row: pd.Series) -> str | None:
        co = row.get("co_leilao")
        start = row.get("dt_inicio")
        central = row.get("codigo_centralizadora")
        if pd.notna(co) and str(co).strip() and pd.notna(start) and str(start).strip():
            parts = [str(central).strip() if pd.notna(central) and str(central).strip() else "", str(co).strip(), str(start).strip()]
            return "|".join(parts)
        return None

    return df.apply(build, axis=1)


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



def _enrich_file_map(df: pd.DataFrame, file_map: pd.DataFrame, file_id_col: str) -> pd.DataFrame:
    if df.empty or file_map.empty or file_id_col not in df.columns or "file_id" not in file_map.columns:
        return df

    left = df.copy()
    fmap = file_map.copy()

    left["_join_file_id"] = left[file_id_col].apply(_normalize_file_id)
    fmap["_join_file_id"] = fmap["file_id"].apply(_normalize_file_id)

    cols = ["_join_file_id"]

    for c in [
        "uf", "cidade", "codigo_cidade", "data_inicio", "data_fim", "file_name", "path",
        "tipo_arquivo", "co_leilao", "dt_inicio", "dt_fim", "codigo_centralizadora",
        "no_unidade", "resultados_json_path",
    ]:
        if c in fmap.columns:
            cols.append(c)

    fmap = fmap[cols].dropna(subset=["_join_file_id"]).drop_duplicates("_join_file_id")
    out = left.merge(fmap, on="_join_file_id", how="left", suffixes=("", "_filemap"))

    for c in [
        "uf", "cidade", "codigo_cidade", "data_inicio", "data_fim", "tipo_arquivo",
        "co_leilao", "dt_inicio", "dt_fim", "codigo_centralizadora", "no_unidade",
        "resultados_json_path",
    ]:
        alt = f"{c}_filemap"

        if alt in out.columns:
            if c in out.columns:
                out[c] = out[c].fillna(out[alt])
            else:
                out[c] = out[alt]

    return out.drop(columns=[c for c in ["_join_file_id"] if c in out.columns])


def _norm_join_key(value: object) -> str:
    if value is None or pd.isna(value):
        return ""

    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def _first_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col

    return None



def _ensure_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    df = df.copy()

    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df



def _add_features(df: pd.DataFrame) -> pd.DataFrame:
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
    file_map = _resultados_file_map(raw)
    df = _enrich_file_map(df, file_map, "result_file_id")
    metadata_key = _auction_key_from_metadata(df)
    if "auction_key" in df.columns:
        df["auction_key"] = metadata_key.fillna(df["auction_key"])
    else:
        df["auction_key"] = metadata_key.fillna(df["result_file_id"].apply(_auction_key))
    df["auction_date"] = df["dt_inicio"].fillna(df["result_file_id"].apply(_file_date)) if "dt_inicio" in df.columns else df["result_file_id"].apply(_file_date)

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
    file_map = _resultados_file_map(raw)
    df = _enrich_file_map(df, file_map, "catalog_file_id")
    metadata_key = _auction_key_from_metadata(df)
    df["auction_key"] = metadata_key.fillna(df["catalog_file_id"].apply(_auction_key))
    df["catalog_date"] = df["dt_inicio"].fillna(df["catalog_file_id"].apply(_file_date)) if "dt_inicio" in df.columns else df["catalog_file_id"].apply(_file_date)
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
    return df



def _first_list_of_dicts(value: object) -> list[dict]:
    if isinstance(value, list) and all(isinstance(x, dict) for x in value):
        return value

    if isinstance(value, dict):
        for preferred in ["lotes", "itens", "items", "data", "results"]:
            found = _first_list_of_dicts(value.get(preferred))
            if found:
                return found

        for child in value.values():
            found = _first_list_of_dicts(child)
            if found:
                return found

    return []


def _best_overlap_col(source: pd.DataFrame, target: pd.Series) -> str | None:
    target_keys = set(target.dropna().map(_norm_join_key))
    target_keys.discard("")

    if not target_keys:
        return None

    best_col = None
    best_score = 0

    for col in source.columns:
        sample = source[col].dropna()
        if sample.empty:
            continue

        keys = set(sample.astype(str).map(_norm_join_key))
        keys.discard("")
        score = len(target_keys.intersection(keys))

        if score > best_score:
            best_col = col
            best_score = score

    return best_col if best_score > 0 else None


def _current_active_metadata(raw: Path) -> pd.DataFrame:
    frames = []

    cities = _read_csv(raw / "metadata" / "cidades_ALL.csv")
    city_lookup = {}
    if not cities.empty and "codigo" in cities.columns:
        for _, row in cities.iterrows():
            city_lookup[str(row.get("codigo"))] = {
                "source_cidade": row.get("nome"),
                "source_uf": row.get("siglaUf") or row.get("source_uf"),
            }

    csv_path = raw / "current_all_active" / "lots.csv"
    csv_df = _read_csv(csv_path)
    if not csv_df.empty:
        frames.append(csv_df)

    vitrine_dir = raw / "current_all_active" / "vitrine"
    if vitrine_dir.exists():
        for path in sorted(vitrine_dir.glob("*.json")):
            match = re.match(r"([A-Z]{2})_(\d+)_(\d{4}-\d{2}-\d{2})\.json$", path.name)
            uf = match.group(1) if match else None
            codigo = match.group(2) if match else None
            data_ref = match.group(3) if match else None

            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue

            records = _first_list_of_dicts(payload)
            if not records:
                continue

            df = pd.json_normalize(records)
            df["source_uf"] = uf
            df["source_codigo_cidade"] = codigo
            df["source_data_inicio"] = data_ref
            df["source_data_fim"] = data_ref
            df["source_json_path"] = str(path)

            if codigo and codigo in city_lookup:
                if not city_lookup[codigo].get("source_uf"):
                    city_lookup[codigo]["source_uf"] = uf

                df["source_cidade"] = city_lookup[codigo].get("source_cidade")
                df["source_uf"] = df["source_uf"].fillna(city_lookup[codigo].get("source_uf"))

            frames.append(df)

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True, sort=False)


def _fill_from_candidates(df: pd.DataFrame, target: str, candidates: list[str]) -> pd.DataFrame:
    if target not in df.columns:
        df[target] = None

    for src in candidates:
        if src in df.columns:
            df[target] = df[target].fillna(df[src])

    return df



def _prepare_current(processed: Path, raw: Path) -> pd.DataFrame:
    path = _first_existing([
        processed / "current_all_active_catalog_lots.csv",
        processed / "history_sp_full_catalogo_only_clean.csv",
    ])

    df = _read_csv(path) if path else pd.DataFrame()
    if df.empty:
        return df

    df = _ensure_numeric(df, ["valor_minimo", "peso_g"])

    if "history_file_id" in df.columns:
        df["current_file_id"] = df["history_file_id"].astype(str)
    elif "pdf_path" in df.columns:
        df["current_file_id"] = df["pdf_path"].apply(_extract_file_id)
    else:
        df["current_file_id"] = None

    active_meta = _current_active_metadata(raw)

    if not active_meta.empty and "lote" in df.columns:
        meta = active_meta.copy()

        lot_col = _best_overlap_col(meta, df["lote"])
        contract_col = _best_overlap_col(meta, df["contrato"]) if "contrato" in df.columns else None

        if lot_col:
            df["_lot_key"] = df["lote"].apply(_norm_join_key)
            meta["_lot_key"] = meta[lot_col].apply(_norm_join_key)

            join_cols = ["_lot_key"]

            if contract_col and "contrato" in df.columns:
                df["_contract_key"] = df["contrato"].apply(_norm_join_key)
                meta["_contract_key"] = meta[contract_col].apply(_norm_join_key)
                join_cols.append("_contract_key")

            wanted = join_cols.copy()
            for c in [
                "uf", "siglaUf", "source_uf",
                "cidade", "nome_cidade", "nomeCidade", "nome", "source_cidade",
                "codigo_cidade", "codigoCidade", "codigo", "source_codigo_cidade",
                "data_inicio", "dataInicio", "dataInicioLance", "inicioLance", "source_data_inicio",
                "data_fim", "dataFim", "dataFimLance", "fimLance", "source_data_fim",
                "source_json_path",
            ]:
                if c in meta.columns:
                    wanted.append(c)

            meta = meta[wanted].drop_duplicates(join_cols)
            df = df.merge(meta, on=join_cols, how="left", suffixes=("", "_active"))

            df = _fill_from_candidates(df, "uf", ["uf_active", "siglaUf", "source_uf"])
            df = _fill_from_candidates(df, "cidade", ["cidade_active", "nome_cidade", "nomeCidade", "nome", "source_cidade"])
            df = _fill_from_candidates(df, "codigo_cidade", ["codigo_cidade_active", "codigoCidade", "codigo", "source_codigo_cidade"])
            df = _fill_from_candidates(df, "data_inicio", ["data_inicio_active", "dataInicio", "dataInicioLance", "inicioLance", "source_data_inicio"])
            df = _fill_from_candidates(df, "data_fim", ["data_fim_active", "dataFim", "dataFimLance", "fimLance", "source_data_fim"])

            df = df.drop(columns=[c for c in ["_lot_key", "_contract_key"] if c in df.columns])

    df = _enrich_file_map(df, _read_csv(raw / "current_all_active" / "lot_file_map.csv"), "current_file_id")

    if "data_inicio" in df.columns:
        df["data_inicio_norm"] = df["data_inicio"].apply(_normalize_date)
    else:
        df["data_inicio_norm"] = None

    if "data_fim" in df.columns:
        df["data_fim_norm"] = df["data_fim"].apply(_normalize_date)
    else:
        df["data_fim_norm"] = None

    for col in ["lote", "contrato"]:
        if col in df.columns:
            df[col] = df[col].astype("string").fillna("")

    df = _add_features(df)
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
    _register(con, "result_files", _resultados_file_map(raw))

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
        WITH catalog AS (
            SELECT
                price_band,
                COUNT(*) AS catalog_lots
            FROM historical_lots
            GROUP BY price_band
        ),
        sold AS (
            SELECT
                price_band,
                COUNT(*) AS sold_lots,
                AVG(ratio) AS avg_ratio,
                MEDIAN(total_por_g) AS median_total_per_g
            FROM lances
            GROUP BY price_band
        )
        SELECT
            c.price_band,
            c.catalog_lots,
            COALESCE(s.sold_lots, 0) AS sold_lots,
            COALESCE(s.sold_lots, 0)::DOUBLE / NULLIF(c.catalog_lots, 0) AS sale_rate,
            s.avg_ratio,
            s.median_total_per_g
        FROM catalog c
        LEFT JOIN sold s USING (price_band)
        ORDER BY CASE c.price_band
            WHEN 'R$0-500' THEN 1
            WHEN 'R$500-1k' THEN 2
            WHEN 'R$1k-2k' THEN 3
            WHEN 'R$2k-5k' THEN 4
            WHEN 'R$5k-10k' THEN 5
            WHEN 'R$10k-20k' THEN 6
            WHEN 'R$20k+' THEN 7
            ELSE 99
        END
    """)

    con.execute("""
        CREATE OR REPLACE VIEW v_weight_sweet_spot AS
        WITH catalog AS (
            SELECT
                weight_band,
                COUNT(*) AS catalog_lots
            FROM historical_lots
            GROUP BY weight_band
        ),
        sold AS (
            SELECT
                weight_band,
                COUNT(*) AS sold_lots,
                AVG(ratio) AS avg_ratio,
                MEDIAN(total_por_g) AS median_total_per_g
            FROM lances
            GROUP BY weight_band
        )
        SELECT
            c.weight_band,
            c.catalog_lots,
            COALESCE(s.sold_lots, 0) AS sold_lots,
            COALESCE(s.sold_lots, 0)::DOUBLE / NULLIF(c.catalog_lots, 0) AS sale_rate,
            s.avg_ratio,
            s.median_total_per_g
        FROM catalog c
        LEFT JOIN sold s USING (weight_band)
        ORDER BY CASE c.weight_band
            WHEN '0-3g' THEN 1
            WHEN '3-5g' THEN 2
            WHEN '5-10g' THEN 3
            WHEN '10-20g' THEN 4
            WHEN '20-50g' THEN 5
            WHEN '50-100g' THEN 6
            WHEN '100g+' THEN 7
            ELSE 99
        END
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
            'https://vitrinedejoias.caixa.gov.br/Paginas/Busca.aspx' AS caixa_search_url,
            COALESCE(c.uf, '') || ' ' || COALESCE(c.cidade, '') || ' lote ' || COALESCE(c.lote, '') || ' contrato ' || COALESCE(c.contrato, '') AS caixa_lookup_text,
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
