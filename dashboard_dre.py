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
    df["mes_num"] = df["data"].dt.month
    df["mes_nome"] = df["mes_num"].map(MAPA_MESES)

    return df

df = load()

# ======================================================
# ESTADO DO DRILL-DOWN
# ======================================================
if "empresa_rank" not in st.session_state:
    st.session_state.empresa_rank = None

# ======================================================
# SIDEBAR
# ======================================================
anos = sorted(df.ano.unique())
ano_padrao = max(anos)
tipos = sorted(df.tipo_conta.dropna().unique())

with st.sidebar:
    visao = st.radio(
        "Visão",
        ["Consolidado", "Filial", "Comparativo"]
    )

    if visao != "Comparativo":
        ano = st.selectbox(
            "Ano",
            anos,
            index=anos.index(ano_padrao)
        )
    else:
        ano = None

    tipo_conta = st.multiselect(
        "Tipo da Conta",
        tipos,
        default=["Centralizadas"] if "Centralizadas" in tipos else []
    )

    bloquear_empresa = st.session_state.empresa_rank is None

    empresa = st.multiselect(
        "Empresa",
        sorted(df.empresa.unique()),
        disabled=bloquear_empresa
    )

    if bloquear_empresa:
        st.caption("ℹ️ Selecione uma empresa no ranking para habilitar este filtro")

    filial = None
    if visao == "Filial":
        filial = st.selectbox(
            "Filial",
            sorted(df.cidade.unique())
        )

# ======================================================
# BASES
# ======================================================
base_rank = df.copy()
if ano:
    base_rank = base_rank[base_rank.ano == ano]
if tipo_conta:
    base_rank = base_rank[base_rank.tipo_conta.isin(tipo_conta)]
if filial:
    base_rank = base_rank[base_rank.cidade == filial]

base = base_rank.copy()
if empresa:
    base = base[base.empresa.isin(empresa)]

# ======================================================
# COMPARATIVO
# ======================================================
if visao == "Comparativo":

    anos_comp = st.multiselect(
        "Anos para comparação",
        anos,
        default=anos[-2:] if len(anos) >= 2 else anos
    )

    base_comp = df[df.tipo == "REALIZADO"].copy()

    if tipo_conta:
        base_comp = base_comp[base_comp.tipo_conta.isin(tipo_conta)]

    if empresa:
        base_comp = base_comp[base_comp.empresa.isin(empresa)]

    comp = (
        base_comp[base_comp.ano.isin(anos_comp)]
        .groupby(["ano", "mes_num", "mes_nome"], as_index=False)
        .agg(valor=("valor", "sum"))
        .sort_values("mes_num")
    )

    fig_comp = px.line(
        comp,
        x="mes_nome",
        y="valor",
        color="ano",
        category_orders={"mes_nome": ORDEM_MESES},
        markers=True
    )

    fig_comp.update_layout(
        xaxis_title="Mês",
        yaxis_title="Valor Realizado (R$)",
        legend_title="Ano"
    )

    st.plotly_chart(fig_comp, use_container_width=True)

    tabela = (
        comp
        .pivot(index="ano", columns="mes_nome", values="valor")
        .reindex(columns=ORDEM_MESES)
    )

    if len(tabela.index) == 2:
        a1, a2 = tabela.index.sort_values()
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
    # ==================================================
    # RANKING DE GASTOS – REALIZADO
    # ==================================================
    st.subheader("Ranking de Gastos por Empresa – Realizado")

    base_real_rank = base_rank[base_rank.tipo == "REALIZADO"]

    if st.session_state.empresa_rank is None:

        rank_empresa = (
            base_real_rank
            .groupby("empresa", as_index=False)
            .agg(gasto=("valor","sum"))
            .sort_values("gasto")
        )

        fig_rank = px.bar(
            rank_empresa,
            y="empresa",
            x="gasto",
            orientation="h",
            color="gasto",
            text=rank_empresa["gasto"].apply(fmt_mi),
            color_continuous_scale="RdYlGn"
        )

        fig_rank.update_layout(
            xaxis_title="Gasto Realizado (R$)",
            yaxis_title="Empresa",
            showlegend=False
        )

        st.plotly_chart(fig_rank, use_container_width=True)

        empresa_sel = st.selectbox(
            "Clique para detalhar a empresa:",
            [""] + rank_empresa["empresa"].tolist()
        )

        if empresa_sel:
            st.session_state.empresa_rank = empresa_sel
            st.rerun()

    else:
        if empresa:
            emp = empresa[0]
        else:
            emp = st.session_state.empresa_rank

        st.subheader(f"Detalhamento Mensal – {emp}")

        detalhe = (
            base_real_rank[base_real_rank.empresa == emp]
            .groupby(["mes_num","mes_nome"], as_index=False)
            .agg(valor=("valor","sum"))
            .sort_values("mes_num")
        )

        fig_det = px.bar(
            detalhe,
            x="mes_nome",
            y="valor",
            text=detalhe["valor"].apply(fmt_mi),
            color="valor",
            color_continuous_scale="Blues"
        )

        fig_det.update_layout(
            xaxis_title="Mês",
            yaxis_title="Gasto Realizado (R$)",
            showlegend=False
        )

        st.plotly_chart(fig_det, use_container_width=True)

        if st.button("⬅ Voltar ao Ranking"):
            st.session_state.empresa_rank = None
            st.rerun()
