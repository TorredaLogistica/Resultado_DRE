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
    def password_entered():
        if st.session_state["password"] == "claro2026":
            st.session_state["authenticated"] = True
            del st.session_state["password"]
        else:
            st.session_state["authenticated"] = False

    if "authenticated" not in st.session_state:
        st.text_input("Digite a senha", type="password",
                      on_change=password_entered, key="password")
        st.stop()

    if not st.session_state["authenticated"]:
        st.text_input("Digite a senha", type="password",
                      on_change=password_entered, key="password")
        st.error("Senha incorreta")
        st.stop()

check_password()

# ======================================================
# TÍTULO / DATA (BRASIL)
# ======================================================
agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
st.title("📊 Dashboard DRE")
st.caption(f"Atualizado em {agora.strftime('%d/%m/%Y %H:%M')}")

# ======================================================
# CSS DOS CARDS
# ======================================================
st.markdown("""
<style>
.card{background:white;border:1px solid #E5E7EB;border-radius:22px;
padding:20px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.06);}
.card-title{font-size:13px;color:#6B7280;text-transform:uppercase;margin-bottom:6px;}
.card-value{font-size:26px;font-weight:700;}
.card-blue{color:#1F77B4;}
.card-green{color:#2CA02C;}
.card-orange{color:#F05A28;}
</style>
""", unsafe_allow_html=True)

def card(t, v, c):
    return f"""
    <div class="card">
        <div class="card-title">{t}</div>
        <div class="card-value {c}">{v}</div>
    </div>
    """

# ======================================================
# CONSTANTES
# ======================================================
ARQUIVO = "Resultado_dre.xlsx"

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
    return f"R$ {v/1e6:,.2f} Mi".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_pct(v):
    if v is None or pd.isna(v):
        return ""
    return f"{v:.2f}%".replace(".", ",")

# ======================================================
# LEITURA DO XLSX
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
# SIDEBAR (FILTROS)
# ======================================================
anos = sorted(df["ano"].unique())
ano_default = max(anos)

tipos_validos = sorted(
    df["tipo_conta"].dropna().astype(str).unique()
)

with st.sidebar:
    visao = st.radio("Visão", ["Consolidado", "Filial", "Comparativo"])
    ano = st.selectbox("Ano", anos, index=anos.index(ano_default))
    tipo_conta = st.multiselect(
        "Tipo da Conta",
        tipos_validos,
        default=["Centralizadas"] if "Centralizadas" in tipos_validos else []
    )

    if visao == "Filial":
        cidade = st.selectbox("Filial", sorted(df["cidade"].unique()))
    else:
        cidade = None

# ======================================================
# BASE FILTRADA
# ======================================================
base = df[df["ano"] == ano]
if tipo_conta:
    base = base[base["tipo_conta"].isin(tipo_conta)]
if cidade:
    base = base[base["cidade"] == cidade]

# ======================================================
# VISÃO COMPARATIVO ✅
# ======================================================
if visao == "Comparativo":

    anos_comp = st.multiselect(
        "Anos para comparação",
        anos,
        default=anos[-2:] if len(anos) >= 2 else anos
    )

    comp = (
        df[(df["ano"].isin(anos_comp)) & (df["tipo"] == "REALIZADO")]
        .groupby(["ano","mes_num","mes_nome"], as_index=False)
        .agg(valor=("valor","sum"))
        .sort_values("mes_num")
    )

    fig = px.line(
        comp,
        x="mes_nome",
        y="valor",
        color="ano",
        category_orders={"mes_nome": ORDEM_MESES},
        markers=True
    )

    fig.update_layout(xaxis_title="Mês", yaxis_title="R$")
    st.plotly_chart(fig, use_container_width=True)

    tabela = (
        comp.pivot(index="ano", columns="mes_nome", values="valor")
        .reindex(columns=ORDEM_MESES)
    )

    st.dataframe(tabela.applymap(fmt_mi), use_container_width=True)

# ======================================================
# CONSOLIDADO / FILIAL ✅
# ======================================================
else:

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

    # CARDS
    c1,c2,c3 = st.columns(3)
    c1.markdown(card("REALIZADO x FORECAST", fmt_pct(pct_forecast), "card-blue"), True)
    c2.markdown(card("ACUMULADO FORECAST", fmt_mi(acum_forecast), "card-blue"), True)
    c3.markdown(card("TOTAL FORECAST", fmt_mi(total_forecast), "card-blue"), True)

    c4,c5,c6 = st.columns(3)
    c4.markdown(card("REALIZADO x ORÇADO", fmt_pct(pct_orcado), "card-green"), True)
    c5.markdown(card("ACUMULADO ORÇAMENTO", fmt_mi(acum_orcado), "card-green"), True)
    c6.markdown(card("TOTAL ORÇAMENTO", fmt_mi(total_orcado), "card-green"), True)

    c7,c8 = st.columns(2)
    c7.markdown(card("ACUMULADO REALIZADO", fmt_mi(realizado), "card-orange"), True)
    c8.markdown(card("REALIZADO + FORECAST", fmt_mi(acum_forecast), "card-orange"), True)

    # GRÁFICO
    fig = px.line(
        mensal,
        x="mes_nome",
        y="valor",
        color="tipo",
        category_orders={"mes_nome": ORDEM_MESES},
        markers=True
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader(f"Ano {ano}")
    tab = mensal.pivot(index="tipo", columns="mes_nome", values="valor").reindex(columns=ORDEM_MESES)
    st.dataframe(tab.applymap(fmt_mi), use_container_width=True)
