import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import os

# ======================================================
# 🔐 LOGIN SIMPLES
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
# CONFIGURAÇÃO
# ======================================================
st.set_page_config(page_title="Dashboard DRE", layout="wide")
st.title("📊 Dashboard DRE")
st.caption(f"Atualizado em {datetime.now().strftime('%d/%m/%Y %H:%M')}")

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
# FORMATADORES SEGUROS (SEM NaN)
# ======================================================
def fmt_mi(v):
    if v is None or pd.isna(v) or v == 0:
        return ""
    return f"R$ {v/1e6:,.2f} Mi".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_rs(v):
    if v is None or pd.isna(v):
        return ""
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_pct(v):
    if v is None or pd.isna(v):
        return ""
    return f"{v:.2f}%".replace(".", ",")

# ======================================================
# LEITURA DO ARQUIVO XLSX FIXO
# ======================================================
@st.cache_data
def carregar():
    if not os.path.exists(ARQUIVO_DRE):
        st.error(f"❌ Arquivo '{ARQUIVO_DRE}' não encontrado no repositório.")
        st.stop()

    df = pd.read_excel(ARQUIVO_DRE, header=None, engine="openpyxl")
    df.columns = ["cidade","empresa","categoria","tipo_conta","tipo","data","valor"]

    df["tipo"] = df["tipo"].astype(str).str.upper().str.strip()
    df["empresa"] = df["empresa"].astype(str).str.strip()
    df["tipo_conta"] = df["tipo_conta"].astype(str).str.strip()

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
with st.sidebar:
    visao = st.radio("Visão", ["Consolidado", "Filial", "Comparativo"])
    tipo_conta = st.multiselect(
        "Tipo da Conta",
        sorted(df["tipo_conta"].dropna().unique())
    )
    empresa = st.multiselect(
        "Empresa",
        sorted(df["empresa"].dropna().unique())
    )

base = df.copy()
if tipo_conta:
    base = base[base["tipo_conta"].isin(tipo_conta)]
if empresa:
    base = base[base["empresa"].isin(empresa)]

# ======================================================
# VISÃO COMPARATIVO
# ======================================================
if visao == "Comparativo":

    anos = st.multiselect(
        "Anos para comparação",
        sorted(base["ano"].unique()),
        default=sorted(base["ano"].unique())[-2:]
    )

    comp = (
        base[(base["ano"].isin(anos)) & (base["tipo"]=="REALIZADO")]
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

    fig.update_layout(
        template="plotly_white",
        yaxis_tickformat=".2s",
        xaxis_title="Mês",
        yaxis_title="R$"
    )
    st.plotly_chart(fig, use_container_width=True)

    tabela_num = comp.pivot(index="ano", columns="mes_nome", values="valor").reindex(columns=ORDEM_MESES)

    if len(anos) == 2:
        a1, a2 = sorted(anos)
        tabela_num.loc["Variação %"] = ((tabela_num.loc[a2] / tabela_num.loc[a1]) - 1) * 100

    def style_variacao(row):
        if row.name != "Variação %":
            return [""] * len(row)
        estilos = []
        for v in row:
            try:
                v_num = float(v)
            except:
                estilos.append("")
                continue
            estilos.append(
                "color: green; font-weight:600" if v_num > 0
                else "color: red; font-weight:600"
            )
        return estilos

    tabela_fmt = tabela_num.copy()
    for idx in tabela_fmt.index:
        tabela_fmt.loc[idx] = (
            tabela_fmt.loc[idx].apply(fmt_pct)
            if idx == "Variação %"
            else tabela_fmt.loc[idx].apply(fmt_rs)
        )

    st.dataframe(
        tabela_fmt.style.apply(style_variacao, axis=1),
        use_container_width=True
    )

# ======================================================
# CONSOLIDADO / FILIAL
# ======================================================
else:

    ano = st.selectbox("Ano", sorted(base["ano"].unique()))

    if visao == "Filial":
        filial = st.selectbox("Filial", sorted(base["cidade"].unique()))
        base = base[(base["ano"] == ano) & (base["cidade"] == filial)]
    else:
        base = base[base["ano"] == ano]

    mensal = (
        base.groupby(["mes_num","mes_nome","tipo"], as_index=False)
        .agg(valor=("valor","sum"))
        .sort_values("mes_num")
    )

    # ================= CARDS =================
    mes_real = mensal[mensal["tipo"]=="REALIZADO"]["mes_num"].max() or 0

    realizado = mensal[(mensal["tipo"]=="REALIZADO") & (mensal["mes_num"]<=mes_real)]["valor"].sum()
    forecast_rest = mensal[(mensal["tipo"]=="FORECAST") & (mensal["mes_num"]>mes_real)]["valor"].sum()
    total_forecast = mensal[mensal["tipo"]=="FORECAST"]["valor"].sum()

    acum_forecast = realizado + forecast_rest
    pct_forecast = (acum_forecast/total_forecast*100) if total_forecast else None

    st.markdown("### Indicadores")

    st.metric("REALIZADO x FORECAST", fmt_pct(pct_forecast))
    st.metric("ACUMULADO FORECAST", fmt_mi(acum_forecast))

    fig2 = px.line(
        mensal,
        x="mes_nome",
        y="valor",
        color="tipo",
        markers=True,
        color_discrete_map=CORES,
        category_orders={"mes_nome": ORDEM_MESES}
    )

    fig2.update_layout(
        template="plotly_white",
        yaxis_tickformat=".2s",
        xaxis_title="Mês",
        yaxis_title="R$"
    )
    st.plotly_chart(fig2, use_container_width=True)

    st.subheader(f"Ano {ano}")

    tabela = mensal.pivot(index="tipo", columns="mes_nome", values="valor").reindex(columns=ORDEM_MESES)
    st.dataframe(tabela.applymap(fmt_mi), use_container_width=True)
