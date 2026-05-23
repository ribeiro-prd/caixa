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
  --accent:#b65a08; --accent2:#d97b00; --green:#16814a; --red:#c43d3d;
  --ink:#171717; --muted:#6f6f6f; --line:#ece7df; --card:#fff; --bg:#fbfaf8;
}
.stApp { background:var(--bg); color:var(--ink); }
.block-container { max-width: 960px; padding-top: 1.1rem; }
h1 { font-size: 40px !important; letter-spacing:-.04em; margin-bottom:.1rem !important; }
h2,h3 { letter-spacing:-.03em; }
div[data-testid="stTabs"] button p { font-size: 14px; }
div[data-baseweb="select"] > div { background:white; border-color:#ddd; color:#111; }
input, textarea { background:white !important; color:#111 !important; }
.metric-card,.card,.lot-card,.filter-card {
  border:1px solid var(--line); background:var(--card); border-radius:18px;
  box-shadow:0 1px 2px rgba(0,0,0,.025);
}
.metric-card { padding:18px 20px; min-height:112px; margin-bottom:14px; }
.metric-label { font-size:12px; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); font-weight:800; }
.metric-value { font-size:30px; line-height:1.15; font-weight:850; margin-top:8px; }
.metric-note { color:var(--muted); margin-top:4px; font-size:14px; }
.card { padding:22px; margin:18px 0; }
.filter-card { padding:18px; margin:15px 0 20px 0; }
.topbar {
  display:flex; gap:24px; align-items:center; border-bottom:1px solid #eee;
  margin-bottom:20px; padding-bottom:12px; font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
  font-size:13px; color:#333; white-space:nowrap; overflow:hidden;
}
.live { color:#e0a400; font-weight:900; letter-spacing:.18em; }
.accent { color:var(--accent); font-weight:850; }
.green { color:var(--green); font-weight:850; }
.red { color:var(--red); font-weight:850; }
.lot-card { padding:16px 18px; margin-bottom:12px; border-left:4px solid transparent; }
.lot-card.good { border-left-color:var(--green); }
.lot-title { font-size:18px; font-weight:850; margin-bottom:5px; }
.lot-sub { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12px; color:#333; }
.badge {
  display:inline-block; padding:3px 9px; border-radius:999px; border:1px solid #ead8c5;
  margin:5px 5px 0 0; font-size:12px; color:#994a06; background:#fff8ef;
}
.badge.blue { color:#234b9a; border-color:#d8e3ff; background:#f4f7ff; }
.badge.red { color:#b42318; border-color:#ffd6d3; background:#fff5f5; }
.badge.green { color:#157347; border-color:#c8ead8; background:#f1fff7; }
.small-note { color:var(--muted); font-size:14px; }
hr { border:none; border-top:1px solid #eee; margin:20px 0; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_resource
def conn():
    return duckdb.connect(str(DB_PATH), read_only=True)


def q(sql: str, params: dict | None = None) -> pd.DataFrame:
    return conn().execute(sql, params or {}).df()


def brl(value) -> str:
    if value is None or pd.isna(value):
        return "-"
    return "R$ " + f"{float(value):,.0f}".replace(",", ".")


def brl2(value) -> str:
    if value is None or pd.isna(value):
        return "-"
    return "R$ " + f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(value) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):.1%}"


def ratio(value) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):.2f}x"


def nfmt(value) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{int(value):,}".replace(",", ".")


def parse_date(value):
    if value is None or pd.isna(value) or str(value) == "":
        return None
    return pd.to_datetime(value).date()


def title(text: str, subtitle: str = ""):
    st.markdown(f"# {text}")
    if subtitle:
        st.markdown(f"<div style='font-size:17px;color:#444;margin-top:-6px;margin-bottom:22px'>{subtitle}</div>", unsafe_allow_html=True)


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


def plot_bar(df: pd.DataFrame, x: str, y: str, title_text: str, orientation="v", color="#b65a08"):
    if df.empty:
        st.info("Sem dados.")
        return
    fig = px.bar(df, x=x, y=y, orientation=orientation)
    fig.update_traces(marker_color=color)
    fig.update_layout(
        title=title_text, height=410, plot_bgcolor="white", paper_bgcolor="white",
        margin=dict(l=10, r=10, t=55, b=10), font=dict(color="#222")
    )
    if orientation == "h":
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, use_container_width=True)


def get_options(table: str, col: str) -> list[str]:
    try:
        return q(f"SELECT DISTINCT {col} FROM {table} WHERE {col} IS NOT NULL AND {col} <> '' ORDER BY {col}")[col].astype(str).tolist()
    except Exception:
        return []


def date_range_input(label: str, min_value, max_value):
    min_d = parse_date(min_value)
    max_d = parse_date(max_value)
    if not min_d or not max_d:
        return None
    return st.date_input(label, value=(min_d, max_d), min_value=min_d, max_value=max_d)


def sql_in(col: str, values: list[str]) -> str | None:
    if not values:
        return None
    vals = ", ".join("'" + v.replace("'", "''") + "'" for v in values)
    return f"{col} IN ({vals})"


def lot_card(row):
    cls = "good" if row.get("clean_gold_flag") == 1 else ""
    st.markdown(
        f"""
        <div class="lot-card {cls}">
          <div class="lot-title">{str(row.get('item_type','lote')).title()} <span style="float:right">{brl(row.get('valor_minimo'))}</span></div>
          <div class="lot-sub">{row.get('lote','')} • {row.get('contrato','')} • {row.get('cidade','')}, {row.get('uf','')} • {row.get('data_inicio_norm','')} a {row.get('data_fim_norm','')}</div>
          <div>
            <span class="badge">{row.get('material','')}</span>
            <span class="badge">{row.get('gold_purity','')}</span>
            <span class="badge blue">{row.get('gem_group','')}</span>
            <span class="badge red">{row.get('defect_status','')}</span>
            <span class="badge">{float(row.get('peso_g') or 0):.1f}g</span>
            <span class="badge">{brl2(row.get('current_min_per_g'))}/g</span>
            <span class="badge green">score {int(row.get('opportunity_score') or 0)}</span>
            <span class="badge">esperado {ratio(row.get('expected_ratio'))}</span>
          </div>
          <div style="margin-top:9px;color:#555">{str(row.get('descricao',''))[:360]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


if not DB_PATH.exists():
    st.error(f"Warehouse not found: {DB_PATH}. Run `caixa-joias build-warehouse` first.")
    st.stop()

top = q("SELECT * FROM v_market_summary").iloc[0]
st.markdown(
    f"""
    <div class="topbar">
      <span class="live">LIVE</span>
      <span>OURO 24K manual</span>
      <span>OURO 18K manual</span>
      <span>Histórico {nfmt(top['winning_rows'])} arrematações</span>
      <span>Vitrine {nfmt(top['lots_in_vitrine'])} lotes</span>
    </div>
    """,
    unsafe_allow_html=True,
)

tabs = st.tabs(["Início", "Vitrine", "Histórico", "Lances", "Explorar", "Compradores", "Universo"])


with tabs[0]:
    title("Visão Geral", "Resumo do mercado de leilões de joias da Caixa Econômica Federal")

    with st.expander("Como funciona? clique para expandir", expanded=False):
        st.write(
            "A plataforma cruza catálogos, vitrine atual e resultados de arrematação. "
            "O objetivo é mostrar preço por grama, competição, compradores dominantes, "
            "prêmio acima do mínimo e oportunidades atuais por material, teor, peso, UF e tipo de joia."
        )

    c1, c2 = st.columns(2)
    with c1:
        metric_card("Lotes na vitrine", nfmt(top["lots_in_vitrine"]), f"Mediana {brl2(top['current_median_min_per_g'])}/g")
        metric_card("Compradores", nfmt(top["buyer_count"]), f"{nfmt(top['active_states'])} estados ativos")
    with c2:
        metric_card("Arrematações", nfmt(top["winning_rows"]), f"Ratio médio {ratio(top['avg_ratio'])}")
        metric_card("Valor em oferta", brl(top["current_offer_value"]), f"{float(top['current_weight_kg'] or 0):,.1f} kg".replace(",", "."))

    buyers = q("SELECT * FROM v_buyer_concentration LIMIT 10")
    if not buyers.empty and len(buyers) >= 3:
        top6 = buyers.head(6)
        st.markdown(
            f"""
            <div class="card">
              <h3>O mercado é dominado por poucos</h3>
              <p><span class="accent">{len(top6)} compradores</span> respondem por
              <span class="accent">{pct(top6['share'].sum())}</span> do valor arrematado.
              O maior comprador adquiriu <span class="accent">{nfmt(top6.iloc[0]['lotes'])} lotes</span>.
              A concentração indica mercado de especialistas, não varejo.</p>
              <table style="width:100%; margin-top:14px">
                <tr><td>Comprador #1</td><td style="text-align:right">{nfmt(top6.iloc[0]['lotes'])} lotes</td></tr>
                <tr><td>Comprador #2</td><td style="text-align:right">{nfmt(top6.iloc[1]['lotes'])} lotes</td></tr>
                <tr><td>Comprador #3</td><td style="text-align:right">{nfmt(top6.iloc[2]['lotes'])} lotes</td></tr>
              </table>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="card"><h3>Peso define a economia</h3>', unsafe_allow_html=True)
    st.dataframe(q("SELECT * FROM v_weight_sweet_spot"), use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="card"><h3>Gemas: valor oculto ou competição?</h3>', unsafe_allow_html=True)
    st.dataframe(q("SELECT * FROM v_gem_value"), use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="card"><h3>Geografia importa</h3>', unsafe_allow_html=True)
    st.dataframe(q("SELECT * FROM v_geography ORDER BY lots DESC"), use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)


with tabs[1]:
    title("Vitrine -- Lotes Disponíveis", "Lotes abertos para lance agora. Filtre por data, UF, teor, material, preço e peso.")

    ufs = get_options("current_lots", "uf")
    cities = get_options("current_lots", "cidade")
    types = get_options("current_lots", "item_type")
    materials = get_options("current_lots", "material")
    purities = get_options("current_lots", "gold_purity")
    gems = get_options("current_lots", "gem_group")
    summary = q("SELECT MIN(data_inicio_norm) min_d, MAX(data_fim_norm) max_d FROM current_lots").iloc[0]

    st.markdown('<div class="filter-card"><h3>Filtros</h3>', unsafe_allow_html=True)
    dr = date_range_input("Período do leilão", summary["min_d"], summary["max_d"])
    col1, col2, col3, col4 = st.columns(4)
    sel_uf = col1.multiselect("Estado (UF)", ufs)
    sel_city = col2.multiselect("Cidade", cities)
    sel_type = col3.multiselect("Tipo de joia", types)
    sel_material = col4.multiselect("Material", materials, default=["ouro"] if "ouro" in materials else [])
    col5, col6, col7, col8 = st.columns(4)
    sel_purity = col5.multiselect("Teor do ouro", purities, default=[x for x in ["999 / 24k", "986", "900", "750 / 18k"] if x in purities])
    sel_gems = col6.multiselect("Gemas", gems)
    defect = col7.selectbox("Defeitos", ["Todos", "Sem defeito", "Com defeito"])
    sort_order = col8.selectbox("Ordenar por", ["Score", "R$/g menor", "Preço maior", "Peso maior", "Data mais próxima"])
    col9, col10, col11, col12 = st.columns(4)
    min_price = col9.number_input("Preço mínimo R$", value=0.0, step=100.0)
    max_price = col10.number_input("Preço máximo R$", value=999999.0, step=1000.0)
    min_weight = col11.number_input("Peso mínimo g", value=0.0, step=1.0)
    max_min_per_g = col12.number_input("Máx. R$/g mínimo", value=700.0, step=25.0)
    contains = st.text_input("Texto contém", "")
    not_contains = st.text_input("Texto não contém", "RELÓGIO, METAL NÃO NOBRE")
    st.markdown("</div>", unsafe_allow_html=True)

    cond = ["1=1"]
    params = {"min_price": min_price, "max_price": max_price, "min_weight": min_weight, "max_min_per_g": max_min_per_g}
    if dr and len(dr) == 2:
        cond += ["TRY_CAST(data_inicio_norm AS DATE) >= $start_date", "TRY_CAST(data_fim_norm AS DATE) <= $end_date"]
        params["start_date"] = str(dr[0])
        params["end_date"] = str(dr[1])
    for expr in [sql_in("uf", sel_uf), sql_in("cidade", sel_city), sql_in("item_type", sel_type), sql_in("material", sel_material), sql_in("gold_purity", sel_purity), sql_in("gem_group", sel_gems)]:
        if expr:
            cond.append(expr)
    if defect == "Sem defeito":
        cond.append("defect_status = 'sem defeito'")
    elif defect == "Com defeito":
        cond.append("defect_status = 'com defeito'")
    if contains.strip():
        cond.append("UPPER(COALESCE(descricao,'')) LIKE '%' || UPPER($contains) || '%'")
        params["contains"] = contains.strip()
    for i, token in enumerate([x.strip() for x in not_contains.split(",") if x.strip()]):
        key = f"not_{i}"
        cond.append(f"UPPER(COALESCE(descricao,'')) NOT LIKE '%' || UPPER(${key}) || '%'")
        params[key] = token
    cond += ["valor_minimo BETWEEN $min_price AND $max_price", "(peso_g >= $min_weight OR peso_g IS NULL)", "(current_min_per_g <= $max_min_per_g OR current_min_per_g IS NULL)"]
    order = {
        "Score": "opportunity_score DESC, current_min_per_g ASC NULLS LAST",
        "R$/g menor": "current_min_per_g ASC NULLS LAST",
        "Preço maior": "valor_minimo DESC",
        "Peso maior": "peso_g DESC NULLS LAST",
        "Data mais próxima": "data_inicio_norm ASC NULLS LAST",
    }[sort_order]

    lots = q(f"SELECT * FROM v_current_opportunities WHERE {' AND '.join(cond)} ORDER BY {order} LIMIT 800", params)
    st.markdown(f"**{nfmt(len(lots))} lotes encontrados**")
    for _, row in lots.head(60).iterrows():
        lot_card(row)
    st.download_button("Baixar vitrine filtrada", lots.to_csv(index=False).encode("utf-8-sig"), "vitrine_filtrada.csv", "text/csv")


with tabs[2]:
    title("Histórico -- Lotes de Leilões Passados", "Resultados realizados. Compare mínimo, arrematação e prêmio real.")

    ufs = get_options("historical_lots", "uf")
    types = get_options("historical_lots", "item_type")
    materials = get_options("historical_lots", "material")
    purities = get_options("historical_lots", "gold_purity")
    summary = q("SELECT MIN(COALESCE(auction_date,catalog_date)) min_d, MAX(COALESCE(auction_date,catalog_date)) max_d FROM historical_lots").iloc[0]

    st.markdown('<div class="filter-card"><h3>Filtros</h3>', unsafe_allow_html=True)
    dr = date_range_input("Data do leilão / publicação", summary["min_d"], summary["max_d"])
    col1, col2, col3, col4 = st.columns(4)
    sel_uf = col1.multiselect("Estado (UF)", ufs, key="hist_uf")
    sel_type = col2.multiselect("Tipo de joia", types, key="hist_type")
    sel_material = col3.multiselect("Material", materials, key="hist_mat")
    sel_purity = col4.multiselect("Teor do ouro", purities, key="hist_purity")
    col5, col6, col7, col8 = st.columns(4)
    status = col5.selectbox("Status", ["Todos", "Vendidos", "Disponíveis/sem venda"])
    max_premium = col6.number_input("Prêmio máximo", value=5.0, step=0.25)
    min_weight = col7.number_input("Peso mínimo", value=0.0, step=1.0, key="hist_weight")
    sort_hist = col8.selectbox("Ordenar por", ["Preço maior", "Prêmio menor", "R$/g menor", "Data recente"])
    text_filter = st.text_input("Texto histórico contém", "")
    st.markdown("</div>", unsafe_allow_html=True)

    cond = ["1=1"]
    params = {"max_premium": max_premium, "min_weight": min_weight}
    if dr and len(dr) == 2:
        cond.append("TRY_CAST(COALESCE(auction_date,catalog_date) AS DATE) BETWEEN $start_date AND $end_date")
        params["start_date"] = str(dr[0])
        params["end_date"] = str(dr[1])
    for expr in [sql_in("uf", sel_uf), sql_in("item_type", sel_type), sql_in("material", sel_material), sql_in("gold_purity", sel_purity)]:
        if expr:
            cond.append(expr)
    if status == "Vendidos":
        cond.append("sold = true")
    elif status == "Disponíveis/sem venda":
        cond.append("sold = false")
    cond += ["(premium_vs_minimo <= $max_premium OR premium_vs_minimo IS NULL)", "(peso_g >= $min_weight OR peso_g IS NULL)"]
    if text_filter.strip():
        cond.append("UPPER(COALESCE(descricao,'')) LIKE '%' || UPPER($text_filter) || '%'")
        params["text_filter"] = text_filter.strip()
    order = {
        "Preço maior": "valor_minimo DESC",
        "Prêmio menor": "premium_vs_minimo ASC NULLS LAST",
        "R$/g menor": "total_por_g ASC NULLS LAST",
        "Data recente": "COALESCE(auction_date,catalog_date) DESC NULLS LAST",
    }[sort_hist]

    hist = q(f"""
        SELECT uf,cidade,COALESCE(auction_date,catalog_date) AS data,lote,contrato,item_type,material,gold_purity,gem_group,
               valor_minimo,lance,total,peso_g,premium_vs_minimo,total_por_g,sold,descricao
        FROM historical_lots
        WHERE {' AND '.join(cond)}
        ORDER BY {order}
        LIMIT 3000
    """, params)
    st.dataframe(hist, use_container_width=True, hide_index=True)


with tabs[3]:
    title("Inteligência de Lances", "Padrões ocultos: o que vende mais, por quanto, e onde há oportunidade.")

    st.markdown('<div class="card"><h3>Para que serve esta página?</h3><p>Aqui você descobre padrões nos leilões passados: materiais com prêmio, faixas de preço com maior venda, pesos mais disputados e filtros para decidir onde dar lance.</p></div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        plot_bar(q("SELECT * FROM v_premium_by_material LIMIT 15"), "avg_ratio", "material", "Onde está o prêmio — por material", "h")
    with col2:
        plot_bar(q("SELECT * FROM v_premium_by_type LIMIT 15"), "avg_ratio", "item_type", "Onde está o prêmio — por tipo", "h")

    st.markdown('<div class="card"><h3>Prêmio por teor do ouro</h3>', unsafe_allow_html=True)
    st.dataframe(q("SELECT * FROM v_premium_by_purity"), use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="card"><h3>Sweet spot de preço</h3>', unsafe_allow_html=True)
    st.dataframe(q("SELECT * FROM v_price_sweet_spot"), use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="card"><h3>Sweet spot de peso</h3>', unsafe_allow_html=True)
    st.dataframe(q("SELECT * FROM v_weight_sweet_spot"), use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

    col3, col4 = st.columns(2)
    with col3:
        plot_bar(q("SELECT * FROM v_geography ORDER BY avg_ratio DESC LIMIT 15"), "avg_ratio", "uf", "Geografia: ratio por UF", "h", "#d97b00")
    with col4:
        plot_bar(q("SELECT * FROM v_gem_value"), "gem_bucket", "median_min_per_g", "Gemas no preço mínimo", "v", "#4f7deb")

    st.markdown('<div class="card"><h3>Backtest: mínimo + X%</h3>', unsafe_allow_html=True)
    st.dataframe(q("SELECT * FROM v_strategy_backtest"), use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)


with tabs[4]:
    title("Explorar Joias", "Análise visual dos lotes disponíveis na vitrine.")

    col1, col2 = st.columns(2)
    with col1:
        mat = q("SELECT * FROM v_current_value_by_material")
        if not mat.empty:
            fig = px.pie(mat, values="lots", names="material", hole=.48, title="Materiais")
            fig.update_layout(height=420, paper_bgcolor="white", plot_bgcolor="white")
            st.plotly_chart(fig, use_container_width=True)
    with col2:
        plot_bar(q("SELECT * FROM v_current_value_by_type LIMIT 12"), "lots", "item_type", "Tipos de joia", "h")

    st.markdown('<div class="card"><h3>Quanto custam?</h3>', unsafe_allow_html=True)
    col3, col4 = st.columns(2)
    with col3:
        plot_bar(q("SELECT price_band, COUNT(*) AS lots FROM current_lots GROUP BY price_band ORDER BY lots DESC"), "price_band", "lots", "Preço mínimo")
    with col4:
        plot_bar(q("SELECT weight_band, COUNT(*) AS lots FROM current_lots GROUP BY weight_band ORDER BY lots DESC"), "weight_band", "lots", "Peso")
    st.markdown("</div>", unsafe_allow_html=True)


with tabs[5]:
    title("Compradores", "Quem compra nos leilões da Caixa e como se comporta.")

    sort_by = st.selectbox("Ordenar por", ["lance_total", "lotes", "premium_medio", "ratio_medio", "share"])
    buyers = q(f"SELECT * FROM v_buyer_concentration ORDER BY {sort_by} DESC")
    for _, r in buyers.head(15).iterrows():
        st.markdown(
            f"""
            <div class="lot-card">
              <div class="lot-title">{r['cpf_cnpj_mascarado']} <span style="float:right">{'CNPJ' if '/' in str(r['cpf_cnpj_mascarado']) else 'CPF'}</span></div>
              <div><span class="accent">{nfmt(r['lotes'])} lotes</span> &nbsp; <span class="accent">{brl(r['lance_total'])}</span> &nbsp; {ratio(r['ratio_medio'])}</div>
              <div class="small-note">{r.get('tipos','')}<br>{r.get('materiais','')} | {r.get('teores','')} | {r.get('estados','')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if not buyers.empty:
        selected = st.selectbox("Detalhar comprador", buyers["cpf_cnpj_mascarado"].astype(str).tolist())
        detail = q("""
            SELECT uf,cidade,auction_date,lote,contrato,item_type,material,gold_purity,lance,total,premium_vs_minimo,total_por_g,descricao
            FROM lances
            WHERE cpf_cnpj_mascarado = $buyer
            ORDER BY lance DESC
            LIMIT 1000
        """, {"buyer": selected})
        st.dataframe(detail, use_container_width=True, hide_index=True)


with tabs[6]:
    title("Universo de Dados", "Tamanho do universo coletado e analisado pela plataforma local.")

    u = q("SELECT * FROM v_universe").iloc[0]
    c1, c2 = st.columns(2)
    with c1:
        metric_card("Lotes analisados", nfmt(u["historical_catalog_lots"]), "catálogos históricos deduplicados")
        metric_card("Arrematações", nfmt(u["arrematacoes"]), "lances confirmados")
        metric_card("Valor em oferta", brl(u["current_offer_value"]), "vitrine atual")
        metric_card("Período histórico", f"{u['min_history_date']} - {u['max_history_date']}", "cobertura temporal")
    with c2:
        metric_card("Vitrine atual", nfmt(u["current_lots"]), "disponíveis para lance")
        metric_card("Compradores", nfmt(u["compradores"]), "CPFs/CNPJs mascarados")
        metric_card("Ouro / peso total vitrine", f"{float(u['current_weight_kg'] or 0):,.1f} kg".replace(",", "."), "peso combinado")
        metric_card("R$/g médio", brl2(u["current_median_min_per_g"]), "valor mínimo / peso")
