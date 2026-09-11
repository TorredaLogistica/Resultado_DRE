import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from zoneinfo import ZoneInfo
import os

# ======================================================
# CONFIGURAÇÃO
# ======================================================
st.set_page_config(
    page_title="Dashboard DRE",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ======================================================
# CABEÇALHO
# ======================================================
agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
st.title("📊 Dashboard DRE")
st.caption(f"Atualizado em {agora.strftime('%d/%m/%Y %H:%M')}")

# ======================================================
# CSS DOS CARDS
# ======================================================
st.markdown("""
<style>
.card {background:#fff;border:1px solid #e5e7eb;border-radius:22px;
padding:20px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.06);}
.card-title {font-size:13px;color:#6b7280;text-transform:uppercase;margin-bottom:6px;}
.card-value {font-size:26px;font-weight:700;}
.blue {color:#1F77B4;}
.green {color:#2CA02C;}
.orange {color:#F05A28;}
</style>
""", unsafe_allow_html=True)

def card(t, v, c):
    return f"<div class='card'><div class='card-title'>{t}</div><div class='card-value {c}'>{v}</div></div>"

def fmt_mi(v):
    return "" if pd.isna(v) or v == 0 else f"R$ {v/1e6:,.2f} Mi".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_pct(v):
    return "" if pd.isna(v) else f"{v:.2f}%".replace(".", ",")

# ======================================================
# DADOS
# ======================================================
ARQUIVO = "Resultado DRE.xlsx"

MAPA_MESES = {
    1:"janeiro",2:"fevereiro",3:"março",4:"abril",
    5:"maio",6:"junho",7:"julho",8:"agosto",
    9:"setembro",10:"outubro",11:"novembro",12:"dezembro"
}
ORDEM_MESES = list(MAPA_MESES.values())

@st.cache_data
def load():
    caminho = os.path.join(os.path.dirname(__file__), ARQUIVO)
    if not os.path.exists(caminho):
        st.error(f"Arquivo {ARQUIVO} não encontrado no repositório.")
        st.stop()

    df = pd.read_excel(caminho, header=None)
    df.columns = ["cidade","empresa","categoria","tipo_conta","tipo","data","valor"]
    df["tipo"] = df["tipo"].str.upper().str.strip()
    df["tipo_conta"] = df["tipo_conta"].str.upper().str.strip()
    df["empresa"] = df["empresa"].astype("string").str.strip()
    # Chave auxiliar para reconhecer E-Commerce mesmo com espaços ou hífens diferentes.
    df["empresa_chave"] = (
        df["empresa"]
        .str.upper()
        .str.replace(r"[^A-Z0-9]", "", regex=True)
    )
    df["data"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df = df.dropna(subset=["data","valor"])
    df["ano"] = df["data"].dt.year
    df["mes_num"] = df["data"].dt.month
    df["mes_nome"] = df["mes_num"].map(MAPA_MESES)
    return df

df = load()
dres = sorted(df["categoria"].dropna().unique())

# ======================================================
# SIDEBAR
# ======================================================
anos = sorted(df.ano.unique())
ano_padrao = max(anos)
tipos = sorted(df.tipo_conta.dropna().unique())

with st.sidebar:
    visao = st.radio("Visão", ["Consolidado", "Filial", "Comparativo"])

    if visao != "Comparativo":
        ano = st.selectbox("Ano", anos, index=anos.index(ano_padrao))
    else:
        ano = None

    tipo_conta = st.multiselect(
        "Tipo da Conta",
        tipos,
        default=["CENTRALIZADAS"] if "CENTRALIZADAS" in tipos else []
    )

    incluir_ecommerce = st.checkbox(
        "Incluir Empresa E-Commerce",
        value=False,
        help="Por padrão, a Empresa E-Commerce fica fora de todos os indicadores e gráficos."
    )
    empresas_disponiveis = df.loc[
        incluir_ecommerce | (df["empresa_chave"] != "ECOMMERCE"),
        "empresa"
    ].dropna().sort_values().unique()
    empresa = st.multiselect("Empresa", empresas_disponiveis)
    dre = st.multiselect("DRE", dres)

    filial = None
    if visao == "Filial":
        filial = st.selectbox("Filial", sorted(df.cidade.unique()))

# ======================================================
# FILTROS DE BASE
# ======================================================
base = df.copy()

if ano is not None:
    base = base[base["ano"] == ano]
if tipo_conta:
    base = base[base["tipo_conta"].isin(tipo_conta)]
if empresa:
    base = base[base["empresa"].isin(empresa)]
if dre:
    base = base[base["categoria"].isin(dre)]
if filial:
    base = base[base["cidade"] == filial]

# ======================================================
# LÓGICA DE VISÃO
# ======================================================
if visao == "Comparativo":
    anos_comp = st.multiselect("Anos para comparação", anos, default=anos[-2:])

    comp = (
        base[(base.tipo == "REALIZADO") & (base.ano.isin(anos_comp))]
        .groupby(["ano","mes_num","mes_nome"], as_index=False)
        .agg(valor=("valor","sum"))
        .sort_values("mes_num")
    )

    fig = px.line(
        comp,
        x="mes_nome", y="valor", color="ano",
        category_orders={"mes_nome": ORDEM_MESES},
        markers=True
    )
    st.plotly_chart(fig, use_container_width=True)

    tabela = comp.pivot(index="ano", columns="mes_nome", values="valor").reindex(columns=ORDEM_MESES)

    if len(anos_comp) == 2:
        a1, a2 = sorted(anos_comp)
        if a1 in tabela.index and a2 in tabela.index:
            tabela.loc["Variação %"] = (tabela.loc[a2] / tabela.loc[a1] - 1) * 100

    # ✅ CORREÇÃO: Converter para object ANTES de aplicar formatação de string
    tabela_fmt = tabela.astype(object).copy()
    for idx in tabela_fmt.index:
        tabela_fmt.loc[idx] = tabela_fmt.loc[idx].apply(fmt_pct if idx == "Variação %" else fmt_mi)

    st.dataframe(tabela_fmt, use_container_width=True)

else:
    # Visão Consolidado / Filial
    mensal = base.groupby(["mes_num","mes_nome","tipo"])["valor"].sum().reset_index()

    mes_real = mensal[mensal.tipo=="REALIZADO"]["mes_num"].max() or 0
    r = mensal[(mensal.tipo=="REALIZADO") & (mensal.mes_num<=mes_real)].valor.sum()
    f_rest = mensal[(mensal.tipo=="FORECAST") & (mensal.mes_num>mes_real)].valor.sum()
    o_rest = mensal[(mensal.tipo=="ORÇADO") & (mensal.mes_num>mes_real)].valor.sum()

    tf = mensal[mensal.tipo=="FORECAST"].valor.sum()
    to = mensal[mensal.tipo=="ORÇADO"].valor.sum()

    af = r + f_rest
    ao = r + o_rest

    c1,c2,c3 = st.columns(3)
    c1.markdown(card("REALIZADO x FORECAST",fmt_pct(af/tf*100 if tf else None),"blue"),True)
    c2.markdown(card("ACUMULADO FORECAST",fmt_mi(af),"blue"),True)
    c3.markdown(card("TOTAL FORECAST",fmt_mi(tf),"blue"),True)

    c4,c5,c6 = st.columns(3)
    c4.markdown(card("REALIZADO x ORÇADO",fmt_pct(ao/to*100 if to else None),"green"),True)
    c5.markdown(card("ACUMULADO ORÇAMENTO",fmt_mi(ao),"green"),True)
    c6.markdown(card("TOTAL ORÇAMENTO",fmt_mi(to),"green"),True)

    c7,c8 = st.columns(2)
    c7.markdown(card("ACUMULADO REALIZADO",fmt_mi(r),"orange"),True)
    c8.markdown(card("REALIZADO + FORECAST",fmt_mi(af),"orange"),True)

    fig = px.line(
        mensal, x="mes_nome", y="valor", color="tipo",
        category_orders={"mes_nome": ORDEM_MESES}, markers=True
    )
    st.plotly_chart(fig, use_container_width=True)

    # Oscilação mensal entre Realizado e Forecast:
    # ((Realizado / Forecast) - 1) * 100.
    oscilacao = (
        mensal[mensal["tipo"].isin(["REALIZADO", "FORECAST"])]
        .pivot_table(
            index=["mes_num", "mes_nome"],
            columns="tipo",
            values="valor",
            aggfunc="sum"
        )
        .reset_index()
    )

    if {"REALIZADO", "FORECAST"}.issubset(oscilacao.columns):
        oscilacao = oscilacao[
            oscilacao["REALIZADO"].notna()
            & oscilacao["FORECAST"].notna()
            & oscilacao["FORECAST"].ne(0)
        ].copy()
        oscilacao["variacao_pct"] = (
            oscilacao["REALIZADO"] / oscilacao["FORECAST"] - 1
        ) * 100
        oscilacao["mes_ano"] = (
            oscilacao["mes_num"].astype(int).astype(str).str.zfill(2)
            + "/"
            + str(ano)
        )
        oscilacao["cor"] = oscilacao["variacao_pct"].apply(
            lambda valor: "Positiva" if valor >= 0 else "Negativa"
        )
        oscilacao["rotulo"] = oscilacao["variacao_pct"].apply(
            lambda valor: f"{valor:+.1f}%".replace(".", ",")
        )
        oscilacao = oscilacao.sort_values("mes_num")

        if not oscilacao.empty:
            st.subheader("Oscilação mensal: Realizado x Forecast")
            fig_oscilacao = px.bar(
                oscilacao,
                x="mes_ano",
                y="variacao_pct",
                color="cor",
                text="rotulo",
                color_discrete_map={"Positiva": "#2AA79B", "Negativa": "#E30613"},
                category_orders={"mes_ano": oscilacao["mes_ano"].tolist()}
            )
            fig_oscilacao.update_traces(
                textposition="outside",
                cliponaxis=False,
                hovertemplate=(
                    "Mês: %{x}<br>Variação: %{y:+.2f}%<extra></extra>"
                )
            )
            fig_oscilacao.update_layout(
                title="Variação mensal do custo",
                xaxis_title=None,
                yaxis_title="Variação (%)",
                showlegend=False,
                bargap=0.25
            )
            fig_oscilacao.update_yaxes(
                ticksuffix="%",
                zeroline=True,
                zerolinecolor="#94A3B8",
                gridcolor="#E2E8F0"
            )
            st.plotly_chart(fig_oscilacao, use_container_width=True)
        else:
            st.info(
                "Não há meses com valores de Realizado e Forecast válidos para calcular a oscilação."
            )
    else:
        st.info(
            "Não há dados simultâneos de Realizado e Forecast para calcular a oscilação mensal."
        )

    tabela = mensal.pivot(index="tipo", columns="mes_nome", values="valor").reindex(columns=ORDEM_MESES)
    st.dataframe(tabela.style.format(fmt_mi), use_container_width=True)

# ======================================================
# SEÇÃO FINAL: GASTOS REALIZADOS (RANKING E PIZZA)
# ======================================================
base_real = base[base.tipo == "REALIZADO"]

if not empresa:
    st.subheader("Ranking de Gastos por Empresa – Realizado (Menor → Maior)")
    rank_empresa = base_real.groupby("empresa", as_index=False).agg(gasto=("valor", "sum")).sort_values("gasto")
    fig_rank_empresa = px.bar(
        rank_empresa, x="empresa", y="gasto",
        text=rank_empresa["gasto"].apply(fmt_mi),
        color="gasto", color_continuous_scale="RdYlGn"
    )
    st.plotly_chart(fig_rank_empresa, use_container_width=True)
else:
    emp = empresa[0]
    st.subheader(f"Gastos Mensais – {emp} (Realizado)")
    mensal_emp = base_real[base_real["empresa"] == emp].groupby(["mes_num", "mes_nome"], as_index=False).agg(valor=("valor", "sum")).sort_values("mes_num")
    fig_mensal = px.bar(
        mensal_emp, x="mes_nome", y="valor",
        text=mensal_emp["valor"].apply(fmt_mi),
        color="valor", color_continuous_scale="Blues"
    )
    st.plotly_chart(fig_mensal, use_container_width=True)

col_pie1, col_pie2 = st.columns(2)
with col_pie1:
    st.subheader("Participação % por CD")
    pizza_cd = base_real.groupby("cidade", as_index=False).agg(valor=("valor", "sum"))
    if not pizza_cd.empty:
        st.plotly_chart(px.pie(pizza_cd, names="cidade", values="valor", hole=0.4), use_container_width=True)

with col_pie2:
    st.subheader("Participação % por Empresa")
    pizza_emp = base_real.groupby("empresa", as_index=False).agg(valor=("valor", "sum"))
    if not pizza_emp.empty:
        st.plotly_chart(px.pie(pizza_emp, names="empresa", values="valor", hole=0.4), use_container_width=True)
