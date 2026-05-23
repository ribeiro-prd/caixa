from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

DB_PATH = Path("data/warehouse/caixa_joias.duckdb")

st.set_page_config(page_title="CAIXA Joias Intelligence", layout="wide", initial_sidebar_state="collapsed")

CSS = """
<style>
:root {
  --accent: #b65a08;
  --accent2: #d98a1f;
  --green: #16814a;
  --red: #c43d3d;
  --ink: #171717;
  --muted: #727272;
  --line: #ece7df;
  --card: #ffffff;
  --bg: #fbfaf8;
}
.stApp { background: var(--bg); color: var(--ink); }
.block-container { max-width: 1180px; padding-top: 1.8rem; }
h1, h2, h3 { letter-spacing: -0.03em; }
.metric-card {
  border: 1px solid var(--line);
  background: var(--card);
  border-radius: 18px;
  padding: 18px 20px;
  min-height: 116px;
  box-shadow: 0 1px 2px rgba(0,0,0,.025);
}
.metric-label {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: .08em;
  color: var(--muted);
  font-weight: 700;
}
.metric-value {
  font-size: 30px;
  line-height: 1.15;
  font-weight: 800;
  margin-top: 8px;
}
.metric-note {
  color: var(--muted);
  margin-top: 4px;
  font-size: 14px;
}
.card {
  border: 1px solid var(--line);
  background: var(--card);
  border-radius: 18px;
  padding: 22px;
  margin-bottom: 18px;
}
.insight {
  border: 1px solid var(--line);
  background: #fffdf9;
  border-radius: 16px;
  padding: 18px 20px;
  margin: 14px 0 24px 0;
}
.accent { color: var(--accent); font-weight: 800; }
.green { color: var(--green); font-weight: 800; }
.red { color: var(--red); font-weight: 800; }
.lot-card {
  border: 1px solid var(--line);
  border-radius: 18px;
  background: white;
  padding: 16px 18px;
  margin-bottom: 12px;
}
.lot-title { font-size: 18px; font-weight: 800; margin-bottom: 4px; }
.lot-sub { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; color: #333; }
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid #e5d6c5;
  margin-right: 6px;
  font-size: 12px;
  color: #9a4a06;
  background: #fff8ef;
}
.topbar {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: #333;
  font-size: 13px;
  margin-bottom: 18px;
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_resource
def conn():
    return duckdb.connect(str(DB_PATH), read_only=True)


def q(sql: str, params: dict | None = None) -> pd.DataFrame:
    return conn().execute(sql, params or {}).df()


def brl(value: float | int | None) -> str:
    if pd.isna(value):
        return "-"
    return "R$ " + f"{float(value):,.0f}".replace(",", ".")


def brl2(value: float | int | None) -> str:
    if pd.isna(value):
        return "-"
    return "R$ " + f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(value: float | int | None) -> str:
    if pd.isna(value):
        return "-"
    return f"{float(value):.1%}"


def ratio(value: float | int | None) -> str:
    if pd.isna(value):
        return "-"
    return f"{float(value):.2f}x"


def title(text: str, subtitle: str | None = None):
    st.markdown(f"# {text}")
    if subtitle:
        st.markdown(f"<div style='font-size:18px;color:#444;margin-top:-10px;margin-bottom:22px'>{subtitle}</div>", unsafe_allow_html=True)


def metric_card(label: str, value: str, note: str = ""):
    st.markdown(
        f"""
        <div class="metric-card">
          <div class="metric-label">{label}</div>
          <div class="metric-value">{value}</div>
          <div class="metric-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def chart_bar(df: pd.DataFrame, x: str, y: str, title_text: str, orientation: str = "v", color: str | None = None):
    if df.empty:
        st.info("No data.")
        return
    if orientation == "h":
        fig = px.bar(df, x=x, y=y, orientation="h", title=title_text)
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
    else:
        fig = px.bar(df, x=x, y=y, title=title_text)
    if color:
        fig.update_traces(marker_color=color)
    fig.update_layout(
        height=420,
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=10, r=10, t=50, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)


def sql_in(column: str, values: list[str]) -> str:
    escaped = [v.replace("'", "''") for v in values]
    return f"{column} IN ({','.join(repr(v) for v in escaped)})"


if not DB_PATH.exists():
    st.error(f"Warehouse not found: {DB_PATH}. Run `caixa-joias build-warehouse` first.")
    st.stop()

top = q("SELECT * FROM v_market_summary").iloc[0]
st.markdown(
    f"""
    <div class="topbar">
      LIVE&nbsp;&nbsp;|&nbsp;&nbsp;OURO 24K manual&nbsp;&nbsp;|&nbsp;&nbsp;
      Histórico: {int(top['winning_rows']):,} arrematações&nbsp;&nbsp;|&nbsp;&nbsp;
      Vitrine: {int(top['lots_in_vitrine']):,} lotes&nbsp;&nbsp;|&nbsp;&nbsp;
      Compradores: {int(top['buyer_count']):,}
    </div>
    """,
    unsafe_allow_html=True,
)

tabs = st.tabs(["Início", "Vitrine", "Histórico", "Lances", "Compradores", "Universo"])


with tabs[0]:
    title("Visão Geral", "Resumo do mercado de leilões de joias da Caixa Econômica Federal")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Lotes na vitrine", f"{int(top['lots_in_vitrine']):,}".replace(",", "."), f"Mediana {brl2(top['current_median_min_per_g'])}/g")
    with c2:
        metric_card("Arrematações", f"{int(top['winning_rows']):,}".replace(",", "."), f"Prêmio mediano {pct(top['median_premium'])}")
    with c3:
        metric_card("Compradores", f"{int(top['buyer_count']):,}".replace(",", "."), f"{int(top['active_states'])} estados ativos")
    with c4:
        metric_card("Valor em oferta", brl(top["current_offer_value"]), f"{float(top['current_weight_kg'] or 0):,.1f} kg na vitrine".replace(",", "."))

    buyers = q("SELECT * FROM v_buyer_concentration LIMIT 10")
    if not buyers.empty:
        top6_share = buyers.head(6)["share"].sum()
        largest = buyers.iloc[0]
        st.markdown(
            f"""
            <div class="card">
              <h3>O mercado é dominado por poucos</h3>
              <p><span class="accent">{min(6, len(buyers))} compradores</span> respondem por
              <span class="accent">{pct(top6_share)}</span> do valor arrematado. O maior comprador adquiriu
              <span class="accent">{int(largest['lotes']):,}</span> lotes.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    col1, col2 = st.columns(2)
    with col1:
        data = q("SELECT item_type, lots, avg_ratio FROM v_premium_by_type ORDER BY avg_ratio DESC LIMIT 12")
        chart_bar(data, "avg_ratio", "item_type", "Prêmio médio por tipo de joia", orientation="h", color="#b65a08")
    with col2:
        data = q("SELECT material, lots, avg_ratio FROM v_premium_by_material ORDER BY avg_ratio DESC LIMIT 12")
        chart_bar(data, "avg_ratio", "material", "Prêmio médio por material", orientation="h", color="#d98a1f")

    st.markdown('<div class="card"><h3>Peso define a economia</h3>', unsafe_allow_html=True)
    st.dataframe(q("SELECT * FROM v_weight_sweet_spot"), use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="card"><h3>Geografia importa</h3>', unsafe_allow_html=True)
    st.dataframe(q("SELECT * FROM v_geography ORDER BY lots DESC"), use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)


with tabs[1]:
    title("Vitrine -- Lotes Disponíveis", "Lotes abertos para lance agora. Use filtros para encontrar oportunidades reais.")

    materials = sorted(q("SELECT DISTINCT material FROM current_lots ORDER BY material")["material"].dropna().astype(str).tolist())
    types = sorted(q("SELECT DISTINCT item_type FROM current_lots ORDER BY item_type")["item_type"].dropna().astype(str).tolist())
    ufs = sorted(q("SELECT DISTINCT uf FROM current_lots WHERE uf IS NOT NULL ORDER BY uf")["uf"].dropna().astype(str).tolist())

    with st.expander("Filtros", expanded=True):
        col1, col2, col3 = st.columns(3)
        sel_uf = col1.multiselect("Estado (UF)", ufs)
        sel_type = col2.multiselect("Tipo de joia", types)
        sel_material = col3.multiselect("Material", materials, default=["ouro"] if "ouro" in materials else [])
        col4, col5, col6 = st.columns(3)
        contains = col4.text_input("Texto contém", "")
        not_contains = col5.text_input("Texto não contém", "RELÓGIO, METAL NÃO NOBRE")
        max_min_per_g = col6.number_input("Máx. R$/g mínimo", value=700.0, step=25.0)

    conditions = ["1=1"]
    params = {"max_min_per_g": max_min_per_g}
    if sel_uf:
        conditions.append(sql_in("uf", sel_uf))
    if sel_type:
        conditions.append(sql_in("item_type", sel_type))
    if sel_material:
        conditions.append(sql_in("material", sel_material))
    if contains.strip():
        conditions.append("UPPER(COALESCE(descricao, '')) LIKE '%' || UPPER($contains) || '%'")
        params["contains"] = contains.strip()
    for i, token in enumerate([x.strip() for x in not_contains.split(",") if x.strip()]):
        key = f"not_{i}"
        conditions.append(f"UPPER(COALESCE(descricao, '')) NOT LIKE '%' || UPPER(${key}) || '%'")
        params[key] = token
    conditions.append("(current_min_per_g <= $max_min_per_g OR current_min_per_g IS NULL)")

    lots = q(
        f"""
        SELECT *
        FROM v_current_opportunities
        WHERE {' AND '.join(conditions)}
        ORDER BY clean_gold_flag DESC, current_min_per_g NULLS LAST, valor_minimo DESC
        LIMIT 500
        """,
        params,
    )

    st.markdown(f"**{len(lots):,} lotes encontrados**".replace(",", "."))

    for _, row in lots.head(30).iterrows():
        st.markdown(
            f"""
            <div class="lot-card">
              <div class="lot-title">{str(row.get('item_type', 'lote')).title()} <span style="float:right">{brl(row.get('valor_minimo'))}</span></div>
              <div class="lot-sub">{row.get('lote', '')} • {row.get('contrato', '')} • {row.get('cidade', '')}, {row.get('uf', '')}</div>
              <div style="margin-top:8px">
                <span class="badge">{row.get('material', '')}</span>
                <span class="badge">{row.get('gem_group', '')}</span>
                <span class="badge">{row.get('defect_status', '')}</span>
                <span class="badge">{float(row.get('peso_g') or 0):.1f}g</span>
                <span class="badge">{brl2(row.get('current_min_per_g'))}/g</span>
                <span class="badge">ratio esperado {ratio(row.get('expected_ratio'))}</span>
              </div>
              <div style="margin-top:8px;color:#555">{str(row.get('descricao', ''))[:280]}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.download_button("Baixar CSV filtrado", lots.to_csv(index=False).encode("utf-8-sig"), "vitrine_filtrada.csv", "text/csv")


with tabs[2]:
    title("Histórico -- Lotes de Leilões Passados", "Resultados já realizados. Compare preço mínimo, venda e prêmio real.")

    with st.expander("Filtros", expanded=True):
        col1, col2, col3 = st.columns(3)
        sold_status = col1.selectbox("Status", ["Todos", "Vendidos", "Não vendidos"])
        max_premium = col2.number_input("Prêmio máximo", value=2.0, step=0.10)
        text_filter = col3.text_input("Texto", "")

    conditions = ["1=1"]
    params = {"max_premium": max_premium}
    if sold_status == "Vendidos":
        conditions.append("sold = true")
    elif sold_status == "Não vendidos":
        conditions.append("sold = false")
    conditions.append("(premium_vs_minimo <= $max_premium OR premium_vs_minimo IS NULL)")
    if text_filter.strip():
        conditions.append("UPPER(COALESCE(descricao, '')) LIKE '%' || UPPER($text_filter) || '%'")
        params["text_filter"] = text_filter.strip()

    hist = q(
        f"""
        SELECT
            uf, cidade, auction_key, lote, contrato, item_type, material, gem_group,
            valor_minimo, lance, total, peso_g, premium_vs_minimo, total_por_g, sold, descricao
        FROM historical_lots
        WHERE {' AND '.join(conditions)}
        ORDER BY sold DESC, premium_vs_minimo NULLS LAST, valor_minimo DESC
        LIMIT 2000
        """,
        params,
    )
    st.dataframe(hist, use_container_width=True, hide_index=True)


with tabs[3]:
    title("Inteligência de Lances", "Onde está o prêmio, onde há competição e quais faixas ainda têm oportunidade.")

    col1, col2 = st.columns(2)
    with col1:
        chart_bar(q("SELECT * FROM v_premium_by_material LIMIT 15"), "avg_ratio", "material", "Onde está o prêmio por material", "h", "#b65a08")
    with col2:
        chart_bar(q("SELECT * FROM v_premium_by_type LIMIT 15"), "avg_ratio", "item_type", "Onde está o prêmio por tipo", "h", "#b65a08")

    st.markdown('<div class="card"><h3>Sweet spot de preço</h3>', unsafe_allow_html=True)
    st.dataframe(q("SELECT * FROM v_price_sweet_spot"), use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="card"><h3>Sweet spot de peso</h3>', unsafe_allow_html=True)
    st.dataframe(q("SELECT * FROM v_weight_sweet_spot"), use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

    col3, col4 = st.columns(2)
    with col3:
        chart_bar(q("SELECT * FROM v_gem_value"), "gem_bucket", "median_min_per_g", "Gemas e preço mínimo", "v", "#3b82f6")
    with col4:
        chart_bar(q("SELECT * FROM v_geography ORDER BY avg_ratio DESC LIMIT 15"), "avg_ratio", "uf", "Ratio por UF", "h", "#d98a1f")

    st.markdown('<div class="card"><h3>Backtest: mínimo + X%</h3>', unsafe_allow_html=True)
    st.dataframe(q("SELECT * FROM v_strategy_backtest"), use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)


with tabs[4]:
    title("Compradores", "Quem compra, quanto gasta, onde atua e o que prefere.")

    sort_by = st.selectbox("Ordenar por", ["lance_total", "lotes", "premium_medio", "share"])
    buyers = q(f"SELECT * FROM v_buyer_concentration ORDER BY {sort_by} DESC")
    st.dataframe(buyers, use_container_width=True, hide_index=True)

    if not buyers.empty:
        selected = st.selectbox("Selecionar comprador", buyers["cpf_cnpj_mascarado"].astype(str).tolist())
        detail = q(
            """
            SELECT uf, cidade, auction_key, lote, contrato, item_type, material, lance, total, premium_vs_minimo, total_por_g, descricao
            FROM lances
            WHERE cpf_cnpj_mascarado = $buyer
            ORDER BY lance DESC
            LIMIT 1000
            """,
            {"buyer": selected},
        )
        st.dataframe(detail, use_container_width=True, hide_index=True)


with tabs[5]:
    title("Universo de Dados", "Tamanho do universo coletado e analisado pela plataforma local.")

    uni = q("SELECT * FROM v_universe").iloc[0]
    cols = st.columns(2)
    with cols[0]:
        metric_card("Lotes analisados", f"{int(uni['historical_catalog_lots']):,}".replace(",", "."), "catálogos históricos")
        metric_card("Arrematações", f"{int(uni['arrematacoes']):,}".replace(",", "."), "lances confirmados")
        metric_card("Valor em oferta", brl(uni["current_offer_value"]), "vitrine atual")
        metric_card("Cidades históricas", f"{int(uni['historical_cities'] or 0)}", "com resultados")
    with cols[1]:
        metric_card("Vitrine atual", f"{int(uni['current_lots']):,}".replace(",", "."), "disponíveis para lance")
        metric_card("Compradores", f"{int(uni['compradores']):,}".replace(",", "."), "CPFs/CNPJs mascarados")
        metric_card("Ouro total vitrine", f"{float(uni['current_weight_kg'] or 0):,.1f} kg".replace(",", "."), "peso combinado")
        metric_card("R$/g médio", brl2(uni["current_median_min_per_g"]), "valor mínimo / peso")
