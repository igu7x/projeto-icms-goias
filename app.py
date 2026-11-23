"""
Painel de BI - ICMS x Frota de Veículos nos municípios de Goiás
Rodar com:  streamlit run app.py

Todas as informações vêm de consultas SQL ao banco data/icms_goias.db
(nenhum CSV é lido aqui).
"""
import sqlite3

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import config
from modelo import ajustar, periodo_icms, prever

st.set_page_config(page_title="ICMS x Frota - Goiás", page_icon="📊", layout="wide")


# ----------------------------------------------------------------------------
# Acesso ao banco
# ----------------------------------------------------------------------------
def consultar(sql, params=()):
    with sqlite3.connect(config.CAMINHO_BANCO) as con:
        return pd.read_sql_query(sql, con, params=params)


def fmt_reais(v):
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_int(v):
    return f"{v:,.0f}".replace(",", ".")


if not config.CAMINHO_BANCO.exists():
    st.error("Banco não encontrado. Rode antes:  python etl.py")
    st.stop()


# ----------------------------------------------------------------------------
# Filtros (barra lateral)
# ----------------------------------------------------------------------------
PERIODO = periodo_icms()
st.sidebar.header("Filtros")
especies_todas = consultar("SELECT DISTINCT especie FROM frota ORDER BY especie")["especie"].tolist()
especies = st.sidebar.multiselect(
    "Tipos de veículo considerados na frota (X)", especies_todas, default=especies_todas
)
tirar_capital = st.sidebar.checkbox("Excluir Goiânia (ponto muito fora da curva)", value=False)
st.sidebar.caption(f"Fonte: Portal Dados Abertos Goiás · ICMS {PERIODO} · Frota dez/{config.ANO}")

if not especies:
    st.warning("Selecione pelo menos um tipo de veículo.")
    st.stop()

# Consulta principal: 1 linha por município, já filtrada
marcadores = ",".join("?" * len(especies))
dados = consultar(f"""
    SELECT m.nome AS municipio,
           f.frota_total,
           i.icms_total
    FROM municipio m
    JOIN (SELECT id_municipio, SUM(quantidade) AS frota_total
            FROM frota WHERE especie IN ({marcadores})
           GROUP BY id_municipio) f ON f.id_municipio = m.id_municipio
    JOIN (SELECT id_municipio, SUM(valor_icms) AS icms_total
            FROM repasse_icms GROUP BY id_municipio) i ON i.id_municipio = m.id_municipio
    WHERE (? = 0 OR m.nome <> 'GOIANIA')
    ORDER BY i.icms_total DESC
""", (*especies, int(tirar_capital)))

modelo = ajustar(dados)

# ----------------------------------------------------------------------------
# Cabeçalho + indicadores
# ----------------------------------------------------------------------------
st.title("ICMS x Frota de Veículos nos municípios de Goiás")
st.caption("Business Intelligence · Faculdade SENAI FATESG · "
           "Igor Freitas, João Pedro, Ryan e Hebert")

k1, k2, k3, k4 = st.columns(4)
k1.metric("Municípios analisados", fmt_int(modelo["n"]))
k2.metric(f"ICMS repassado ({PERIODO})", fmt_reais(dados["icms_total"].sum() / 1e9) + " bi")
k3.metric("Frota ativa", fmt_int(dados["frota_total"].sum()))
k4.metric("Correlação (r)", f"{modelo['r']:.3f}".replace(".", ","))

aba_proj, aba_visao, aba_reg, aba_sim, aba_dados = st.tabs(
    ["📌 O projeto", "📊 Visão geral", "📈 Regressão", "🧮 Simulador", "🗃️ Dados"]
)

# ----------------------------------------------------------------------------
# Aba 1 - O projeto (serve de "slide" na apresentação)
# ----------------------------------------------------------------------------
with aba_proj:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Pergunta de negócio")
        st.markdown(
            "**Municípios com mais veículos recebem mais ICMS?**\n\n"
            "O ICMS repassado a cada município depende principalmente do quanto a "
            "economia local movimenta (valor adicionado). A frota de veículos é um "
            "dado fácil de obter e atualizado todo mês, então pode servir como um "
            "*termômetro* da atividade econômica e ajudar a estimar o repasse."
        )
        st.subheader("Variáveis")
        st.markdown(
            "- **X (explicativa):** frota ativa de veículos do município (DETRAN-GO, dez/2025)\n"
            f"- **Y (resposta):** ICMS creditado ao município em {PERIODO} (SEFAZ-GO). "
            "O arquivo de 2025 do portal traz ICMS só até julho."
        )
    with c2:
        st.subheader("Como foi feito")
        st.markdown(
            "1. **ETL (pandas/numpy):** download no portal, padronização dos nomes, "
            "tratamento de nulos e duplicados, soma mensal do ICMS e da frota ativa\n"
            "2. **Banco SQLite:** tabelas `municipio`, `repasse_icms` e `frota` + view `vw_analise`\n"
            "3. **Modelo:** correlação de Pearson e regressão linear simples "
            "(cálculo manual conferido com statsmodels)\n"
            "4. **Painel:** Streamlit consultando o banco em tempo real"
        )
        st.latex(r"\hat{Y} = b + aX \qquad a=\frac{\sum (x-\bar{x})(y-\bar{y})}{\sum (x-\bar{x})^2}"
                 r"\qquad b=\bar{y}-a\bar{x}")

# ----------------------------------------------------------------------------
# Aba 2 - Visão geral (gráficos descritivos)
# ----------------------------------------------------------------------------
with aba_visao:
    c1, c2 = st.columns(2)
    top = dados.head(10).sort_values("icms_total")
    c1.plotly_chart(
        px.bar(top, x="icms_total", y="municipio", orientation="h",
               title="Top 10 municípios em ICMS recebido",
               labels={"icms_total": "ICMS (R$)", "municipio": ""}),
        width="stretch",
    )
    meses = consultar("""
        SELECT ano_mes, SUM(valor_icms) AS icms FROM repasse_icms
        GROUP BY ano_mes ORDER BY ano_mes""")
    meses["mes"] = meses["ano_mes"].astype(str).str[4:] + "/" + meses["ano_mes"].astype(str).str[:4]
    c2.plotly_chart(
        px.bar(meses, x="mes", y="icms", title="ICMS repassado por mês (todos os municípios)",
               labels={"icms": "ICMS (R$)", "mes": ""}),
        width="stretch",
    )

    c3, c4 = st.columns(2)
    c3.plotly_chart(
        px.box(dados, y="icms_total", points="all", hover_name="municipio", log_y=True,
               title="Distribuição do ICMS por município (escala log)",
               labels={"icms_total": "ICMS (R$)"}),
        width="stretch",
    )
    por_especie = consultar(f"""
        SELECT especie, SUM(quantidade) AS qtd FROM frota
        WHERE especie IN ({marcadores}) GROUP BY especie ORDER BY qtd DESC LIMIT 8""", especies)
    c4.plotly_chart(
        px.bar(por_especie, x="especie", y="qtd", title="Frota ativa por tipo de veículo",
               labels={"qtd": "Veículos", "especie": ""}),
        width="stretch",
    )
    lideres = ", ".join(n.title() for n in dados["municipio"].head(4))
    st.info("A maior parte dos municípios recebe pouco e poucos recebem muito: "
            f"a distribuição é bem assimétrica, puxada por {lideres}.")

# ----------------------------------------------------------------------------
# Aba 3 - Regressão
# ----------------------------------------------------------------------------
with aba_reg:
    c1, c2 = st.columns([2, 1])
    xs = np.linspace(0, dados["frota_total"].max(), 100)
    fig = px.scatter(dados, x="frota_total", y="icms_total", hover_name="municipio",
                     labels={"frota_total": "Frota ativa (X)", "icms_total": f"ICMS {PERIODO} (Y)"},
                     title="Dispersão ICMS x Frota com reta de regressão", opacity=0.7)
    fig.add_trace(go.Scatter(x=xs, y=modelo["b"] + modelo["a"] * xs, mode="lines",
                             name="Reta ajustada", line=dict(color="red", width=3)))
    c1.plotly_chart(fig, width="stretch")

    with c2:
        st.subheader("Resultado")
        st.markdown(f"**Equação:**  \nŶ = {fmt_reais(modelo['b'])} + {fmt_reais(modelo['a'])} · X")
        st.markdown(f"- **a (inclinação):** {fmt_reais(modelo['a'])} por veículo")
        st.markdown(f"- **b (intercepto):** {fmt_reais(modelo['b'])}")
        st.markdown(f"- **r de Pearson:** {modelo['r']:.4f} → correlação **{modelo['classificacao']}**")
        st.markdown(f"- **R²:** {modelo['r2']:.4f} ({modelo['r2']*100:.1f}% da variação do ICMS "
                    "é explicada pela frota)")
        st.markdown(f"- **p-valor:** {modelo['p_valor']:.2e}")
        st.caption(f"Conferência statsmodels: a = {modelo['a_statsmodels']:.4f} · "
                   f"b = {modelo['b_statsmodels']:.2f}")

    st.markdown(
        f"**Leitura:** cada veículo a mais na frota está associado, em média, a "
        f"**{fmt_reais(modelo['a'])}** a mais de ICMS no período. Isso é associação, "
        "não causa: a frota não gera ICMS sozinha, ela acompanha o tamanho da economia local."
    )

# ----------------------------------------------------------------------------
# Aba 4 - Simulador preditivo
# ----------------------------------------------------------------------------
with aba_sim:
    st.subheader("Quanto de ICMS esperar para uma frota de X veículos?")
    c1, c2 = st.columns([1, 2])
    with c1:
        frota_sim = st.number_input("Frota ativa (X)", min_value=0, value=20000, step=1000)
        cidade = st.selectbox("...ou compare com um município real", ["(nenhum)"] + dados["municipio"].tolist())
        if cidade != "(nenhum)":
            frota_sim = int(dados.loc[dados["municipio"] == cidade, "frota_total"].iloc[0])
            st.caption(f"Frota de {cidade}: {fmt_int(frota_sim)} veículos")

    y_hat, ic_inf, ic_sup = prever(modelo, frota_sim)
    with c2:
        st.metric(f"ICMS estimado em {PERIODO} (Ŷ)", fmt_reais(y_hat))
        st.caption(f"Intervalo de confiança 95% da média: {fmt_reais(ic_inf)} a {fmt_reais(ic_sup)}")
        st.code(f"Ŷ = {modelo['b']:,.2f} + {modelo['a']:,.2f} × {frota_sim:,}  =  {y_hat:,.2f}")
        if cidade != "(nenhum)":
            real = float(dados.loc[dados["municipio"] == cidade, "icms_total"].iloc[0])
            erro = (real - y_hat) / real * 100 if real else 0
            st.write(f"ICMS real de {cidade}: **{fmt_reais(real)}** "
                     f"(diferença de {erro:+.1f}% em relação ao previsto)")
    if frota_sim > dados["frota_total"].max():
        st.warning("Esse valor de X está fora da faixa usada no modelo: a previsão fica pouco confiável.")

# ----------------------------------------------------------------------------
# Aba 5 - Dados
# ----------------------------------------------------------------------------
with aba_dados:
    tabela = dados.copy()
    tabela["previsto"] = modelo["b"] + modelo["a"] * tabela["frota_total"]
    tabela["residuo"] = tabela["icms_total"] - tabela["previsto"]
    st.dataframe(tabela, width="stretch", hide_index=True)
    st.caption("Resíduo positivo = município recebe mais ICMS do que a frota dele sugere "
               "(ex.: polos industriais e de agronegócio).")
