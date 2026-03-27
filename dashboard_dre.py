import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from zoneinfo import ZoneInfo
import os

# ======================================================
# CONFIG
# ======================================================
st.set_page_config(
    page_title="Dashboard DRE",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ======================================================
# LOGIN
# ======================================================
def check_password():
    def authenticate():
        st.session_state.auth = st.session_state.pwd == "claro2026"
        if st.session_state.auth:
            del st.session_state.pwd

    if "auth" not in st.session_state:
        st.text_input("Senha de acesso", type="password",
                      key="pwd", on_change=authenticate)
        st.stop()

    if not st.session_state.auth:
        st.text_input("Senha de acesso", type="password",
                      key="pwd", on_change=authenticate)
        st.error("Senha incorreta")
        st.stop()

check_password()

# ======================================================
# HEADER
# ======================================================
agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
st.title("📊 Dashboard DRE")
st.caption(f"Atualizado em {agora.strftime('%d/%m/%Y %H:%M')}")

# ======================================================
# CONSTANTES
# ======================================================
ARQUIVO = "Resultado DRE.xlsx"

MAPA_MESES = {
    1:"janeiro",2:"fevereiro",3:"março",4:"abril",
    5:"maio",6:"junho",7:"julho",8:"agosto",
    9:"setembro",10:"outubro",11:"novembro",12:"dezembro"
}
ORDEM_MESES = list(MAPA_MESES.values())

# ======================================================
# FORMATADORES
# ======================================================
def fmt_mi(v):
    if v is None or pd.isna(v) or v == 0:
        return ""
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_pct(v):
    if v is None or pd.isna(v):
        return ""
    return f"{v:.2f}%".replace(".", ",")

# ======================================================
# LEITURA DO XLSX
# ======================================================
@st.cache_data
def load():
    caminho = os.path.join(os.getcwd(), ARQUIVO)
    if not os.path.exists(caminho):
        st.error("Arquivo Resultado_dre.xlsx não encontrado no repositório.")
        st.stop()

    df = pd.read_excel(caminho, header=None)
    df.columns = ["cidade","empresa","categoria",
                  "tipo_conta","tipo","data","valor"]

    df["tipo"] = df["tipo"].astype(str).str.upper().str.strip()
    df["tipo_conta"] = df["tipo_conta"].astype(str).str.strip()
    df["empresa"] = df["empresa"].astype(str).str.strip()

    df["data"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df = df.dropna(subset=["data","valor"])

    df["ano"] = df["data"].dt.year
    df["mes_num"] = df["data"].dt.month
    df["mes_nome"] = df["mes_num"].map(MAPA_MESES)

    return df

df = load()

# ======================================================
# SIDEBAR
# ======================================================
anos = sorted(df["ano"].unique())
ano_default = max(anos)

tipos = sorted(df["tipo_conta"].dropna().unique())

with st.sidebar:
    visao = st.radio("Visão", ["Consolidado","Filial","Comparativo"])
    ano = st.selectbox("Ano", anos, index=anos.index(ano_default))
    tipo_conta = st.multiselect(
        "Tipo da Conta",
        tipos,
        default=["Centralizadas"] if "Centralizadas" in tipos else []
    )
    empresa = st.multiselect("Empresa", sorted(df["empresa"].unique()))

    filial = None
    if visao == "Filial":
        filial = st.selectbox("Filial", sorted(df["cidade"].unique()))

# ======================================================
# BASE FILTRADA (USADA EM TODAS AS VISÕES)
# ======================================================
base = df[df["ano"] == ano].copy()
if tipo_conta:
    base = base[base["tipo_conta"].isin(tipo_conta)]
if empresa:
    base = base[base["empresa"].isin(empresa)]
if filial:
    base = base[base["cidade"] == filial]

# ======================================================
# VISÃO COMPARATIVO (AJUSTADA)
# ======================================================
if visao == "Comparativo":

    anos_comp = st.multiselect(
        "Anos para comparação",
        anos,
        default=anos[-2:]
    )

    comp = (
        base[
            (base["tipo"] == "REALIZADO") &
            (base["ano"].isin(anos_comp))
        ]
        .groupby(["ano","mes_num","mes_nome"], as_index=False)
        .agg(valor=("valor","sum"))
        .sort_values("mes_num")
    )

    # GRÁFICO
    fig = px.line(
        comp,
        x="mes_nome",
        y="valor",
        color="ano",
        markers=True,
        category_orders={"mes_nome": ORDEM_MESES}
    )
    fig.update_layout(xaxis_title="Mês", yaxis_title="R$")
    st.plotly_chart(fig, use_container_width=True)

    # TABELA
    tabela = (
        comp.pivot(index="ano", columns="mes_nome", values="valor")
        .reindex(columns=ORDEM_MESES)
    )

    # VARIAÇÃO %
    if len(anos_comp) == 2:
        a1, a2 = sorted(anos_comp)
        tabela.loc["Variação %"] = (tabela.loc[a2] / tabela.loc[a1] - 1) * 100

    # FORMATAÇÃO FINAL
    tabela_fmt = tabela.copy()
    for idx in tabela_fmt.index:
        if idx == "Variação %":
            tabela_fmt.loc[idx] = tabela_fmt.loc[idx].apply(fmt_pct)
        else:
            tabela_fmt.loc[idx] = tabela_fmt.loc[idx].apply(fmt_mi)

    st.dataframe(tabela_fmt, use_container_width=True)
