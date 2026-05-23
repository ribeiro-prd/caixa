from __future__ import annotations

from pathlib import Path
import pandas as pd
import streamlit as st

try:
    import duckdb
except ImportError as exc:
    st.error("duckdb is required. Install requirements-dashboard.txt.")
    raise exc

DB_PATH = Path("data/warehouse/caixa_joias.duckdb")
st.set_page_config(page_title="CAIXA Joias Intelligence", layout="wide")

@st.cache_resource
def get_connection(path: str):
    return duckdb.connect(path, read_only=True)

def query(sql: str, params: dict | None = None) -> pd.DataFrame:
    con = get_connection(str(DB_PATH))
    return con.execute(sql, params or {}).df()

def pct(value):
    return "" if pd.isna(value) else f"{value:.1%}"

if not DB_PATH.exists():
    st.error(f"Warehouse not found: {DB_PATH}. Run `caixa-joias build-warehouse` first.")
    st.stop()

st.title("CAIXA Joias Intelligence")
tabs = st.tabs(["Overview", "Lot Search", "Strategy Backtest", "Buyer Concentration", "Auction Results"])

with tabs[0]:
    st.subheader("Market summary")
    summary = query("SELECT * FROM v_market_summary")
    if not summary.empty:
        row = summary.iloc[0]
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Winning rows", f"{int(row['winning_rows']):,}")
        c2.metric("Buyers", f"{int(row['buyer_count']):,}")
        c3.metric("Auctions", f"{int(row['auction_count']):,}")
        c4.metric("Median premium", pct(row["median_premium"]))
        c5.metric("Median total/g", f"R$ {row['median_total_per_g']:,.2f}")
    st.dataframe(query("SELECT * FROM v_premium_bands"), use_container_width=True)

with tabs[1]:
    st.subheader("Lot search")
    col1, col2, col3, col4 = st.columns(4)
    contains = col1.text_input("Contains", value="OURO")
    not_contains = col2.text_input("Does not contain", value="RELÓGIO, METAL NÃO NOBRE")
    max_premium = col3.number_input("Max premium", value=0.20, step=0.05)
    max_total_g = col4.number_input("Max total per gram", value=600.0, step=25.0)

    conditions = ["1=1"]
    params = {"max_premium": max_premium, "max_total_g": max_total_g}
    if contains.strip():
        conditions.append("UPPER(COALESCE(descricao, '')) LIKE '%' || UPPER($contains) || '%'")
        params["contains"] = contains.strip()
    for i, token in enumerate([x.strip() for x in not_contains.split(",") if x.strip()]):
        key = f"not_contains_{i}"
        conditions.append(f"UPPER(COALESCE(descricao, '')) NOT LIKE '%' || UPPER(${key}) || '%'")
        params[key] = token
    conditions.append("premium_vs_minimo <= $max_premium")
    conditions.append("(total_por_g <= $max_total_g OR total_por_g IS NULL)")
    sql = f"""
        SELECT auction_key, lote, contrato, descricao, valor_minimo, lance, total, peso_g, premium_vs_minimo, total_por_g, cpf_cnpj_mascarado
        FROM lances
        WHERE {' AND '.join(conditions)}
        ORDER BY total_por_g NULLS LAST, premium_vs_minimo
        LIMIT 1000
    """
    st.dataframe(query(sql, params), use_container_width=True)

with tabs[2]:
    st.subheader("Minimum + X% backtest")
    st.dataframe(query("SELECT * FROM v_strategy_backtest ORDER BY bid_markup"), use_container_width=True)
    st.subheader("Actual cheap-clearing candidates")
    st.dataframe(query("SELECT * FROM v_opportunity_candidates LIMIT 1000"), use_container_width=True)

with tabs[3]:
    st.subheader("Buyer concentration")
    st.dataframe(query("SELECT * FROM v_buyer_concentration"), use_container_width=True)

with tabs[4]:
    st.subheader("Auction result rows")
    col1, col2 = st.columns(2)
    buyer = col1.text_input("Buyer mask contains", value="")
    lote = col2.text_input("Lote contains", value="")
    conditions = ["1=1"]
    params = {}
    if buyer.strip():
        conditions.append("cpf_cnpj_mascarado LIKE '%' || $buyer || '%'")
        params["buyer"] = buyer.strip()
    if lote.strip():
        conditions.append("lote LIKE '%' || $lote || '%'")
        params["lote"] = lote.strip()
    sql = f"""
        SELECT auction_key, cpf_cnpj_mascarado, lote, contrato, lance, tarifa, total, valor_minimo, premium_vs_minimo, peso_g, total_por_g, descricao
        FROM lances
        WHERE {' AND '.join(conditions)}
        ORDER BY auction_key, lote
        LIMIT 2000
    """
    st.dataframe(query(sql, params), use_container_width=True)
