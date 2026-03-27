import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from zoneinfo import ZoneInfo
import os

# ======================================================
# CONFIGURAÇÃO (PRIMEIRA LINHA SEMPRE)
# ======================================================
st.set_page_config(
    page_title="Dashboard DRE",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ======================================================
# 🔐 LOGIN
# ======================================================
def check_password():
    def password_entered():
        if st.session_state["password"] == "claro2026":
            st.session_state["authenticated"] = True
            del st.session_state["password"]
        else:
            st.session_state["authenticated"] = False

    if "authenticated" not in st.session_state:
        st.text_input(
            "Digite a senha de acesso",
            type="password",
            on_change=password_entered,
            key="password"
        )
        st.stop()

    if not st.session_state["authenticated"]:
        st.text_input(
            "Digite a senha de acesso",
            type="password",
            on_change=password_entered,
            key="password"
        )
        st.error("Senha incorreta")
        st.stop()

check_password()

# ======================================================
# TÍTULO E HORÁRIO (GMT‑3)
# ======================================================
agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
st.title("📊 Dashboard DRE")
st.caption(f"Atualizado em {agora.strftime('%d/%m/%Y %H:%M')}")

# ======================================================
# CSS GLOBAL DOS CARDS (IGUAL AO PRINT)
# ======================================================
st.markdown("""
<style>
.card {
    background-color: #ffffff;
    border: 1px solid #E5E7EB;
    border-radius: 22px;
    padding: 20px;
    text-align: center;
    box-shadow: 0px 1px 3px rgba(0,0,0,0.06);
    margin-bottom: 12px;
}
.card-title {
    font-size: 13px;
    font-weight: 500;
    color: #6B7280;
    margin-bottom: 8px;
    text-transform: uppercase;
}
.card-value {
    font-size: 26px;
    font-weight: 700;
}
.card-blue   { color: #1F77B4; }
.card-green  { color: #2CA02C; }
.card-orange { color: #F05A28; }
</style>
""", unsafe_allow_html=True)

# ======================================================
# CONSTANTES
# ======================================================
ARQUIVO_DRE = "Resultado DRE.xlsx"

MAPA_MESES = {
    1:"janeiro",2:"fevereiro",3:"março",4:"abril",
    5:"maio",6:"junho",7:"julho",8:"agosto",
    9:"setembro",10:"outubro",11:"novembro",12:"dezembro"
}
ORDEM_MESES = list(MAPA_MESES.values())

CORES = {
    "FORECAST": "#1F77B4",
    "ORÇADO": "#2CA02C",
    "REALIZADO": "#F05A28"
}

# ======================================================
# FORMATADORES
# ======================================================
def fmt_mi(v):
    if v is None or pd.isna(v) or v == 0:
        return ""
    return f"R$ {v/1e6:,.2f} Mi".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_pct(v):
    if v is None or pd.isna(v):
        return ""
    return f"{v:.2f}%".replace(".", ",")

def render_card(titulo, valor, cor_css):
    return f"""
    <div class="card">
        <div class="card-title">{titulo}</div>
        <div class="card-value {cor_css}">{valor}</div>
    </div>
    """

# ======================================================
# LEITURA DO EXCEL DO REPOSITÓRIO
# ======================================================
@st.cache_data
def carregar():
    if not os.path.exists(ARQUIVO_DRE):
        st.error(f"Arquivo '{ARQUIVO_DRE}' não encontrado no repositório.")
        st.stop()

    df = pd.read_excel(ARQUIVO_DRE, header=None, engine="openpyxl")
    df.columns = ["cidade","empresa","categoria","tipo_conta","tipo","data","valor"]

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

df = carregar()

# ======================================================
# SIDEBAR – FILTROS COM VALORES INICIAIS
# ======================================================
anos_disponiveis = sorted(df["ano"].unique())
ano_default = 2026 if 2026 in anos_disponiveis else anos_disponiveis[-1]

with st.sidebar:
    visao = st.radio("Visão", ["Consolidado", "Filial", "Comparativo"])
    ano = st.selectbox("Ano", anos_disponiveis, index=anos_disponiveis.index(ano_default))
    tipo_conta = st.multiselect(
        "Tipo da Conta",
        sorted(df["tipo_conta"].unique()),
        default=["Centralizadas"] if "Centralizadas" in df["tipo_conta"].unique() else None
    )
    empresa = st.multiselect("Empresa", sorted(df["empresa"].unique()))

base = df[df["ano"] == ano].copy()
if tipo_conta:
    base = base[base["tipo_conta"].isin(tipo_conta)]
if empresa:
    base = base[base["empresa"].isin(empresa)]

# ======================================================
# CONSOLIDADO / FILIAL (CARDS)
# ======================================================
mensal = (
    base.groupby(["mes_num","mes_nome","tipo"], as_index=False)
    .agg(valor=("valor","sum"))
    .sort_values("mes_num")
)

mes_real = mensal[mensal["tipo"]=="REALIZADO"]["mes_num"].max() or 0
realizado = mensal[(mensal["tipo"]=="REALIZADO") & (mensal["mes_num"]<=mes_real)]["valor"].sum()
forecast_rest = mensal[(mensal["tipo"]=="FORECAST") & (mensal["mes_num"]>mes_real)]["valor"].sum()
orcado_rest = mensal[(mensal["tipo"]=="ORÇADO") & (mensal["mes_num"]>mes_real)]["valor"].sum()

total_forecast = mensal[mensal["tipo"]=="FORECAST"]["valor"].sum()
total_orcado = mensal[mensal["tipo"]=="ORÇADO"]["valor"].sum()

acum_forecast = realizado + forecast_rest
acum_orcado = realizado + orcado_rest

pct_forecast = (acum_forecast/total_forecast*100) if total_forecast else None
pct_orcado = (acum_orcado/total_orcado*100) if total_orcado else None

c1,c2,c3=st.columns(3)
c1.markdown(render_card("REALIZADO X FORECAST",fmt_pct(pct_forecast),"card-blue"),True)
c2.markdown(render_card("ACUMULADO FORECAST",fmt_mi(acum_forecast),"card-blue"),True)
c3.markdown(render_card("TOTAL FORECAST",fmt_mi(total_forecast),"card-blue"),True)

c4,c5,c6=st.columns(3)
c4.markdown(render_card("REALIZADO X ORÇADO",fmt_pct(pct_orcado),"card-green"),True)
c5.markdown(render_card("ACUMULADO ORÇAMENTO",fmt_mi(acum_orcado),"card-green"),True)
c6.markdown(render_card("TOTAL ORÇAMENTO",fmt_mi(total_orcado),"card-green"),True)

c7,c8=st.columns(2)
c7.markdown(render_card("ACUMULADO REALIZADO",fmt_mi(realizado),"card-orange"),True)
c8.markdown(render_card("REALIZADO + FORECAST",fmt_mi(acum_forecast),"card-orange"),True)
