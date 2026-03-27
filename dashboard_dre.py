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
# CABEÇALHO (HORÁRIO BRASÍLIA)
# ======================================================
agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
st.title("📊 Dashboard DRE")
st.caption(f"Atualizado em {agora.strftime('%d/%m/%Y %H:%M')}")

# ======================================================
# CONSTANTES
# ======================================================
ARQUIVO_XLSX = "Resultado DRE.xlsx"

MAPA_MESES = {
    1:"janeiro",2:"fevereiro",3:"março",4:"abril",
    5:"maio",6:"junho",7:"julho",8:"agosto",
    9:"setembro",10:"outubro",11:"novembro",12:"dezembro"
}
ORDEM_MESES = list(MAPA_MESES.values())

# ======================================================
# FORMATADORES (INALTERADOS)
# ======================================================
def fmt_mi(v):
    if v is None or pd.isna(v) or v == 0:
        return ""
    return f"R$ {v/1e6:,.2f} Mi".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_pct(v):
    if v is None or pd.isna(v):
        return ""
    return f"{v:.2f}%".replace(".", ",")

# ======================================================
# LEITURA DO EXCEL (AJUSTE ÚNICO AQUI)
# ======================================================
@st.cache_data
def load_data():
    # Caminho absoluto do arquivo no repositório GitHub
    caminho = os.path.join(os.path.dirname(__file__), ARQUIVO_XLSX)

    if not os.path.exists(caminho):
        st.error(
            "❌ Arquivo 'Resultado DRE.xlsx' não encontrado.\n\n"
            "Verifique se:\n"
            "- O arquivo está na raiz do repositório GitHub\n"
            "- O nome está exatamente: Resultado DRE.xlsx\n"
            "- Inclui espaço e maiúsculas"
        )
        st.stop()

    df = pd.read_excel(caminho, header=None, engine="openpyxl")
    df.columns = [
        "cidade","empresa","categoria",
        "tipo_conta","tipo","data","valor"
    ]

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

df = load_data()

# ======================================================
# SIDEBAR (INALTERADO)
# ======================================================
anos = sorted(df["ano"].unique())
ano_padrao = max(anos)

tipos_conta = sorted(
    df["tipo_conta"].dropna().astype(str).unique()
)

with st.sidebar:
    visao = st.radio("Visão", ["Consolidado", "Filial", "Comparativo"])
    ano = st.selectbox("Ano", anos, index=anos.index(ano_padrao))

    tipo_conta = st.multiselect(
        "Tipo da Conta",
        tipos_conta,
        default=["Centralizadas"] if "Centralizadas" in tipos_conta else []
    )

    empresa = st.multiselect(
        "Empresa",
        sorted(df["empresa"].dropna().astype(str).unique())
    )

    filial = None
    if visao == "Filial":
        filial = st.selectbox(
            "Filial",
            sorted(df["cidade"].dropna().astype(str).unique())
        )

# ======================================================
# BASE FILTRADA (INALTERADA)
# ======================================================
base = df[df["ano"] == ano].copy()

if tipo_conta:
    base = base[base["tipo_conta"].isin(tipo_conta)]
if empresa:
    base = base[base["empresa"].isin(empresa)]
if filial:
    base = base[base["cidade"] == filial]

# ======================================================
# VISÃO COMPARATIVO (INALTERADA)
# ======================================================
if visao == "Comparativo":

    anos_comp = st.multiselect(
        "Anos para comparação",
        anos,
        default=anos[-2:] if len(anos) >= 2 else anos
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

    tabela = (
        comp.pivot(index="ano", columns="mes_nome", values="valor")
        .reindex(columns=ORDEM_MESES)
    )

    if len(anos_comp) == 2:
        a1, a2 = sorted(anos_comp)
        tabela.loc["Variação %"] = (tabela.loc[a2] / tabela.loc[a1] - 1) * 100

    tabela_fmt = tabela.copy()
    for idx in tabela_fmt.index:
        if idx == "Variação %":
            tabela_fmt.loc[idx] = tabela_fmt.loc[idx].apply(fmt_pct)
        else:
            tabela_fmt.loc[idx] = tabela_fmt.loc[idx].apply(fmt_mi)

    st.dataframe(tabela_fmt, use_container_width=True)

# ======================================================
# CONSOLIDADO / FILIAL (INALTERADO)
# ======================================================
else:

    mensal = (
        base.groupby(["mes_num","mes_nome","tipo"], as_index=False)
        .agg(valor=("valor","sum"))
        .sort_values("mes_num")
    )

    fig = px.line(
        mensal,
        x="mes_nome",
        y="valor",
        color="tipo",
        markers=True,
        category_orders={"mes_nome": ORDEM_MESES}
    )
    fig.update_layout(xaxis_title="Mês", yaxis_title="R$")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader(f"Ano {ano}")
    tabela = (
        mensal.pivot(index="tipo", columns="mes_nome", values="valor")
        .reindex(columns=ORDEM_MESES)
    )
    st.dataframe(tabela.applymap(fmt_mi), use_container_width=True)
