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

# =============================
# LOGIN
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
        st.text_input(
            "Digite a senha",
            type="password",
            on_change=password_entered,
            key="password"
        )
        st.stop()
    elif not st.session_state["password_correct"]:
        st.text_input(
            "Digite a senha",
            type="password",
            on_change=password_entered,
            key="password"
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
        .replace(",", "X").replace(".", ",").replace("X", ".")
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
    1:"janeiro", 2:"fevereiro", 3:"março", 4:"abril",
    5:"maio", 6:"junho", 7:"julho", 8:"agosto",
    9:"setembro", 10:"outubro", 11:"novembro", 12:"dezembro"
}
ORDEM_MESES = list(MAPA_MESES.values())

@st.cache_data
def load():
    caminho = os.path.join(os.path.dirname(__file__), ARQUIVO)
    if not os.path.exists(caminho):
        st.error("Arquivo Resultado DRE.xlsx não encontrado.")
        st.stop()

    df = pd.read_excel(caminho, header=None)
    df.columns = [
        "cidade","empresa","categoria",
        "tipo_conta","tipo","data","valor"
    ]

    df["tipo"] = df["tipo"].str.upper().str.strip()
    df["empresa"] = df["empresa"].str.strip()
    df["tipo_conta"] = df["tipo_conta"].str.strip()
    df["data"] = pd.to_datetime(df["data"], dayfirst=True, errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")

    df = df.dropna(subset=["data","valor"])
    df["ano"] = df["data"].dt.year
