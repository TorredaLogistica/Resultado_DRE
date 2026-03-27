import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from zoneinfo import ZoneInfo
import os

# ======================================================
# CONFIGURAÇÃO (PRIMEIRA COISA)
# ======================================================
st.set_page_config(
    page_title="Dashboard DRE",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================
# LOGIN (Mantido conforme original)
# =============================
def check_password():
    def password_entered():
        if st.session_state["password"] == "claro2026":
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False
    
    if "password_correct" not in st.session_state:
        st.title("🔒 Acesso Restrito")
        st.text_input("Digite a senha", type="password", on_change=password_entered, key="password")
        st.stop()
    elif not st.session_state["password_correct"]:
        st.text_input("Digite a senha", type="password", on_change=password_entered, key="password")
        st.error("Senha incorreta")
        st.stop()

check_password()

# ======================================================
# TÍTULO E DATA (GMT-3)
# ======================================================
agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
st.title("📊 Dashboard DRE")
st.caption(f"Atualizado em {agora.strftime('%d/%m/%Y %H:%M')}")

# ======================================================
# CSS GLOBAL DOS CARDS
# ======================================================
st.markdown("""
<style>
.card {background:#fff;border:1px solid #E5E7EB;border-radius:22px;
padding:20px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.06);}
.card-title{font-size:13px;color:#6B7280;text-transform:uppercase;margin-bottom:8px;}
.card-value{font-size:26px;font-weight:700;}
.card-blue{color:#1F77B4;}
.card-green{color:#2CA02C;}
.card-orange{color:#F05A28;}
</style>
""", unsafe_allow_html=True)

def card(t, v, c):
    return f"<div class='card'><div class='card-title'>{t}</div><div class='card-value {c}'>{v}</div></div>"

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

def fmt_mi(v): 
    return "" if pd.isna(v) or v == 0 else f"R$ {v/1e6:,.2f} Mi".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_pct(v): 
    return "" if pd.isna(v) else f"{v:.2f}%".replace(".", ",")

# ======================================================
# LEITURA DO XLSX DO REPOSITÓRIO
# ======================================================
@st.cache_data
def carregar():
    df = pd.read_excel(ARQUIVO, header=None)
    df.columns = ["cidade","empresa","categoria","tipo_conta","tipo","data","valor"]
    df["tipo"] = df["tipo"].str.upper().str.strip()
    df["tipo_conta"] = df["tipo_conta"].str.strip()
    df["empresa"] = df["empresa"].str.strip()
    df["data"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df = df.dropna(subset=["data","valor"])
    df["ano"] = df["data"].dt.year
    df["mes_num"] = df["data"].dt.month
    df["mes_nome"] = df["mes_num"].map(MAPA_MESES)
    return df

df = carregar()

# ======================================================
# SIDEBAR
# ======================================================
anos = sorted(df["ano"].unique())
ano_default = 2026 if 2026 in anos else anos[-1]

with st.sidebar:
    visao = st.radio("Visão", ["Consolidado", "Filial", "Comparativo"])
    ano = st.selectbox("Ano", anos, index=anos.index(ano_default))
    tipo_conta = st.multiselect("Tipo da Conta",
        sorted(df["tipo_conta"].unique()),
        default=["Centralizadas"] if "Centralizadas" in df["tipo_conta"].unique() else None
    )
    empresa = st.multiselect("Empresa", sorted(df["empresa"].unique()))

# ======================================================
# BASE FILTRADA
# ======================================================
base = df[df["ano"] == ano]
if tipo_conta:
    base = base[base["tipo_conta"].isin(tipo_conta)]
if empresa:
    base = base[base["empresa"].isin(empresa)]

# ======================================================
# VISÃO COMPARATIVO
# ======================================================
if visao == "Comparativo":
    anos_comp = st.multiselect("Anos para comparação", anos, default=anos[-2:])
    comp = base[base["ano"].isin(anos_comp)]
    fig = px.line(
        comp.groupby(["ano","mes_num","mes_nome"])["valor"].sum().reset_index(),
        x="mes_nome", y="valor", color="ano",
        category_orders={"mes_nome":ORDEM_MESES},
        markers=True
    )
    st.plotly_chart(fig, use_container_width=True)

# ======================================================
# CONSOLIDADO / FILIAL
# ======================================================
else:
    mensal = base.groupby(["mes_num","mes_nome","tipo"])["valor"].sum().reset_index()
    fig = px.line(
        mensal, x="mes_nome", y="valor", color="tipo",
        category_orders={"mes_nome":ORDEM_MESES}, markers=True
    )
    st.plotly_chart(fig, use_container_width=True)

    tabela = mensal.pivot(index="tipo", columns="mes_nome", values="valor").reindex(columns=ORDEM_MESES)
    st.dataframe(tabela.applymap(fmt_mi), use_container_width=True)
