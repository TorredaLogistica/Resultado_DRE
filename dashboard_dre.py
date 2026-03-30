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
        st.error("Arquivo Resultado DRE.xlsx não encontrado no repositório.")
        st.stop()

    df = pd.read_excel(caminho, header=None)
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

df = load()


# ========================================
# ESTADO DO DRILL-DOWN (RANKING EMPRESA)
# ========================================
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

    # 🔹 Filtro de ano NÃO aparece no Comparativo
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
     st.caption("ℹ️ Selecione uma empresa no ranking para habilitar o filtro")

    empresa = st.multiselect(
        "Empresa",
        sorted(df.empresa.unique()),
        disabled=bloquear_empresa
    )

    filial = None
    if visao == "Filial":
        filial = st.selectbox(
            "Filial",
            sorted(df.cidade.unique())
        )


# ============================
# BASE PARA RANKING (IGNORA EMPRESA)
# ============================
base_rank = df.copy()
if ano:
    base_rank = base_rank[base_rank.ano == ano]
if tipo_conta:
    base_rank = base_rank[base_rank.tipo_conta.isin(tipo_conta)]
if filial:
    base_rank = base_rank[base_rank.cidade == filial]

# ============================
# BASE PARA DETALHE (RESPEITA EMPRESA)
# ============================
base = base_rank.copy()
if empresa:
    base = base[base.empresa.isin(empresa)]

# ======================================================
# COMPARATIVO (PRINT 3)
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

    tabela_fmt = tabela.copy()
    for idx in tabela_fmt.index:
        tabela_fmt.loc[idx] = tabela_fmt.loc[idx].apply(fmt_pct if idx == "Variação %" else fmt_mi)

    st.dataframe(tabela_fmt, use_container_width=True)

# ======================================================
# CONSOLIDADO / FILIAL (PRINT 1 e 2)
# ======================================================
else:

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

    tabela = mensal.pivot(index="tipo", columns="mes_nome", values="valor").reindex(columns=ORDEM_MESES)
    st.dataframe(tabela.applymap(fmt_mi), use_container_width=True)

# ======================================================
# RANKING DE GASTOS (APENAS REALIZADO)
# ======================================================

st.subheader("Ranking de Gastos por Empresa – Realizado")

base_real_rank = base_rank[base_rank.tipo == "REALIZADO"]

# ======================================================
# VISÃO 1 – RANKING GERAL
# ======================================================
if st.session_state.empresa_rank is None:
    
    rank_empresa = (
        base_real_rank
        .groupby("empresa", as_index=False)
        .agg(gasto=("valor", "sum"))
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

# ======================================================
# VISÃO 2 – DETALHE MENSAL
# ======================================================

else:
    # -------------------------------
    # Define empresa do detalhamento
    # -------------------------------
    if empresa:
        emp = empresa[0]
    else:
        emp = st.session_state.empresa_rank

    st.markdown(f"### 📊 Detalhamento Mensal – **{emp}**")

    detalhe = (
        base_real_rank[base_real_rank.empresa == emp]
        .groupby(["mes_num", "mes_nome"], as_index=False)
        .agg(valor=("valor", "sum"))
        .sort_values("mes_num")
    )

    fig_det = px.bar(
        detalhe,
        x="mes_nome",
        y="valor",
        color="valor",
        text=detalhe["valor"].apply(fmt_mi),
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
