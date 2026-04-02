# ======================================================
# IMPORTS
# ======================================================
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import streamlit as st

# ======================================================
# CONFIGURAÇÃO
# ======================================================
st.set_page_config(
    page_title="Dashboard DRE",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ======================================================
# LOGIN
# ======================================================
def check_password():
    def password_entered():
        if st.session_state["password"] == "claro2026":
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.title("🔒 Acesso Restrito")
        st.text_input(
            "Digite a senha",
            type="password",
            on_change=password_entered,
            key="password",
        )
        st.stop()
    elif not st.session_state["password_correct"]:
        st.text_input(
            "Digite a senha",
            type="password",
            on_change=password_entered,
            key="password",
        )
        st.error("Senha incorreta")
        st.stop()


check_password()

# ======================================================
# CABEÇALHO
# ======================================================
agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
st.title("📊 Dashboard DRE")
st.caption(f"Atualizado em {agora.strftime('%d/%m/%Y %H:%M')}")

# ======================================================
# FUNÇÕES AUXILIARES
# ======================================================
def fmt_mi(v):
    if pd.isna(v) or v == 0:
        return ""
    return (
        f"R$ {v/1e6:,.2f} Mi"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def fmt_pct(v):
    if pd.isna(v):
        return ""
    return f"{v:.2f}%".replace(".", ",")


# ======================================================
# DADOS
# ======================================================
ARQUIVO = "Resultado DRE.xlsx"

MAPA_MESES = {
    1: "janeiro",
    2: "fevereiro",
    3: "março",
    4: "abril",
    5: "maio",
    6: "junho",
    7: "julho",
    8: "agosto",
    9: "setembro",
    10: "outubro",
    11: "novembro",
    12: "dezembro",
}

ORDEM_MESES = list(MAPA_MESES.values())


@st.cache_data
def load_data():
    caminho = os.path.join(os.path.dirname(__file__), ARQUIVO)
    if not os.path.exists(caminho):
        st.error("Arquivo Resultado DRE.xlsx não encontrado.")
        st.stop()

    df = pd.read_excel(caminho, header=None)
    df.columns = [
        "cidade",
        "empresa",
        "categoria",
        "tipo_conta",
        "tipo",
        "data",
        "valor",
    ]

    df["tipo"] = df["tipo"].str.upper().str.strip()
    df["tipo_conta"] = df["tipo_conta"].str.upper().str.strip()
    df["empresa"] = df["empresa"].str.strip()
    df["categoria"] = df["categoria"].str.strip()

    df["data"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")

    df = df.dropna(subset=["data", "valor"])

    df["ano"] = df["data"].dt.year
    df["mes_num"] = df["data"].dt.month
    df["mes_nome"] = df["mes_num"].map(MAPA_MESES)

    return df


df = load_data()
dres = sorted(df["categoria"].dropna().unique())

# ======================================================
# SIDEBAR
# ======================================================
anos = sorted(df["ano"].unique())
ano_padrao = max(anos)
tipos = sorted(df["tipo_conta"].dropna().astype(str).unique())

with st.sidebar:
    visao = st.radio("Visão", ["Consolidado", "Filial", "Comparativo"])

    if visao != "Comparativo":
        ano = st.selectbox("Ano", anos, index=anos.index(ano_padrao))
    else:
        ano = None

    tipo_conta = st.multiselect(
        "Tipo da Conta",
        tipos,
        default=["CENTRALIZADAS"] if "CENTRALIZADAS" in tipos else [],
    )

    empresa = st.multiselect("Empresa", sorted(df["empresa"].unique()))
    dre = st.multiselect("DRE", dres)

    filial = None
    if visao == "Filial":
        filial = st.selectbox("Filial", sorted(df["cidade"].unique()))

# ======================================================
# BASE FILTRADA
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
# VISÃO COMPARATIVO
# ======================================================
if visao == "Comparativo":
    anos_comp = st.multiselect(
        "Anos para comparação",
        anos,
        default=anos[-2:] if len(anos) >= 2 else anos,
    )

    comp = (
        base[
            (base["tipo"] == "REALIZADO")
            & (base["ano"].isin(anos_comp))
        ]
        .groupby(["ano", "mes_num", "mes_nome"], as_index=False)
        .agg(valor=("valor", "sum"))
        .sort_values("mes_num")
    )

    fig = px.line(
        comp,
        x="mes_nome",
        y="valor",
        color="ano",
        category_orders={"mes_nome": ORDEM_MESES},
        markers=True,
    )
    st.plotly_chart(fig, use_container_width=True)

    tabela = (
        comp.pivot(index="ano", columns="mes_nome", values="valor")
        .reindex(columns=ORDEM_MESES)
    )

    if len(tabela.index) == 2:
        a1, a2 = sorted(tabela.index)
        tabela.loc["Variação %"] = (tabela.loc[a2] / tabela.loc[a1] - 1) * 100

    tabela_fmt = tabela.copy()
    for idx in tabela_fmt.index:
        tabela_fmt.loc[idx] = tabela_fmt.loc[idx].apply(
            fmt_pct if idx == "Variação %" else fmt_mi
        )

    st.dataframe(tabela_fmt, use_container_width=True)

# ======================================================
# CONSOLIDADO / FILIAL
# ======================================================
else:
    mensal = (
        base.groupby(["mes_num", "mes_nome", "tipo"], as_index=False)
        .agg(valor=("valor", "sum"))
    )

    fig = px.line(
        mensal,
        x="mes_nome",
        y="valor",
        color="tipo",
        category_orders={"mes_nome": ORDEM_MESES},
        markers=True,
    )
    st.plotly_chart(fig, use_container_width=True)

    tabela = (
        mensal.pivot(index="tipo", columns="mes_nome", values="valor")
        .reindex(columns=ORDEM_MESES)
    )

    if isinstance(tabela, pd.Series):
        tabela = tabela.to_frame()

    st.dataframe(tabela.applymap(fmt_mi), use_container_width=True)

    # ==================================================
    # GRÁFICO DE COLUNAS INTELIGENTE
    # ==================================================
    base_real = base[base["tipo"] == "REALIZADO"]

    if not empresa:
        st.subheader("Ranking de Gastos por Empresa – Realizado (Menor → Maior)")

        rank = (
            base_real.groupby("empresa", as_index=False)
            .agg(gasto=("valor", "sum"))
            .sort_values("gasto")
        )

        fig_rank = px.bar(
            rank,
            x="empresa",
            y="gasto",
            text=rank["gasto"].apply(fmt_mi),
            color="gasto",
            color_continuous_scale="RdYlGn",
        )
        st.plotly_chart(fig_rank, use_container_width=True)

    else:
        emp = empresa[0]
        st.subheader(f"Gastos Mensais – {emp} (Realizado)")

        mensal_emp = (
            base_real[base_real["empresa"] == emp]
            .groupby(["mes_num", "mes_nome"], as_index=False)
            .agg(valor=("valor", "sum"))
            .sort_values("mes_num")
        )

        fig_emp = px.bar(
            mensal_emp,
            x="mes_nome",
            y="valor",
            text=mensal_emp["valor"].apply(fmt_mi),
            color="valor",
            color_continuous_scale="Blues",
        )
        st.plotly_chart(fig_emp, use_container_width=True)

    # ==================================================
    # GRÁFICOS DE PIZZA
    # ==================================================
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Participação % por CD – Realizado")
        pizza_cd = (
            base_real.groupby("cidade", as_index=False)
            .agg(valor=("valor", "sum"))
        )
        fig_cd = px.pie(
            pizza_cd, names="cidade", values="valor", hole=0.4
        )
        fig_cd.update_traces(textinfo="percent+label")
        st.plotly_chart(fig_cd, use_container_width=True)

    with col2:
        st.subheader("Participação % por Empresa – Realizado")
        pizza_emp = (
            base_real.groupby("empresa", as_index=False)
            .agg(valor=("valor", "sum"))
        )
        fig_emp_pie = px.pie(
            pizza_emp, names="empresa", values="valor", hole=0.4
        )
        fig_emp_pie.update_traces(textinfo="percent+label")
        st.plotly_chart(fig_emp_pie, use_container_width=True)
