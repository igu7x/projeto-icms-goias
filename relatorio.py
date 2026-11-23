"""
Gera o Relatório Técnico Executivo (docs/Relatorio_Tecnico.pdf) direto do banco.
Os números do texto saem do próprio modelo, então sempre batem com o painel.

Para incluir os prints do painel, salve as imagens em docs/prints/
(ex.: 1_projeto.png, 2_visao.png, 3_regressao.png, 4_simulador.png) e rode:
    python relatorio.py
"""
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np
from matplotlib.patches import FancyBboxPatch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

import config
from modelo import ajustar, carregar_dados, prever

PASTA_DOCS = config.PASTA_PROJETO / "docs"
PASTA_FIG = PASTA_DOCS / "figuras"
PASTA_PRINTS = PASTA_DOCS / "prints"
SAIDA = PASTA_DOCS / "Relatorio_Tecnico.pdf"

# Fonte DejaVu (vem junto com o matplotlib) para os símbolos Σ, x̄, Ŷ, √ e ²
_FONTES = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
pdfmetrics.registerFont(TTFont("DejaVu", str(_FONTES / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(_FONTES / "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("DejaVu-Oblique", str(_FONTES / "DejaVuSans-Oblique.ttf")))
pdfmetrics.registerFont(TTFont("DejaVu-BoldOblique", str(_FONTES / "DejaVuSans-BoldOblique.ttf")))
pdfmetrics.registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold",
                              italic="DejaVu-Oblique", boldItalic="DejaVu-BoldOblique")

EQUIPE = [
    ("Igor Freitas", "ETL e banco de dados"),
    ("João Pedro", "Modelagem estatística (correlação e regressão)"),
    ("Ryan", "Painel de BI em Streamlit"),
    ("Hebert", "Problema de negócio, relatório e conclusões"),
]


def reais(v):
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def inteiro(v):
    return f"{v:,.0f}".replace(",", ".")


def num(v, casas=4):
    return f"{v:.{casas}f}".replace(".", ",")


# ----------------------------------------------------------------------------
# Figuras
# ----------------------------------------------------------------------------
def figura_diagrama():
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.axis("off")
    caixas = {
        "municipio": (0.345, 0.55, ["PK id_municipio  INTEGER", "nome  TEXT (único)"]),
        "repasse_icms": (0.0, 0.0, ["PK id  INTEGER", "FK id_municipio", "ano_mes  INTEGER",
                                    "valor_icms  REAL"]),
        "frota": (0.69, 0.0, ["PK id  INTEGER", "FK id_municipio", "referencia  INTEGER",
                              "especie  TEXT", "quantidade  INTEGER"]),
    }
    for nome, (x, y, campos) in caixas.items():
        altura = 0.09 * (len(campos) + 1) + 0.02
        ax.add_patch(FancyBboxPatch((x, y), 0.31, altura, boxstyle="round,pad=0.01",
                                    fc="#eef3fb", ec="#2b5797", lw=1.5))
        ax.text(x + 0.155, y + altura - 0.06, nome, ha="center", fontweight="bold", fontsize=10)
        for i, c in enumerate(campos):
            ax.text(x + 0.015, y + altura - 0.15 - 0.09 * i, c, fontsize=8.5, family="monospace")
    ax.plot([0.155, 0.155, 0.335], [0.48, 0.70, 0.70], color="#2b5797", lw=1.3)
    ax.plot([0.845, 0.845, 0.665], [0.57, 0.70, 0.70], color="#2b5797", lw=1.3)
    ax.text(0.16, 0.72, "1 : N", fontsize=9)
    ax.text(0.78, 0.72, "1 : N", fontsize=9)
    ax.text(0.5, 0.36, "vw_analise\n(frota_total x icms_total\npor município)", ha="center",
            fontsize=8.5, style="italic", color="#555")
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.05, 0.85)
    caminho = PASTA_FIG / "diagrama_banco.png"
    fig.savefig(caminho, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return caminho


def figura_dispersao(dados, m):
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    ax.scatter(dados["frota_total"], dados["icms_total"] / 1e6, alpha=0.6, s=18, label="Municípios")
    xs = np.linspace(0, dados["frota_total"].max(), 100)
    ax.plot(xs, (m["b"] + m["a"] * xs) / 1e6, color="red", lw=2, label="Reta ajustada")
    for _, linha in dados.head(4).iterrows():
        ax.annotate(linha["municipio"].title(), (linha["frota_total"], linha["icms_total"] / 1e6),
                    fontsize=7, xytext=(4, 4), textcoords="offset points")
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: inteiro(v)))
    ax.set_xlabel("Frota ativa de veículos (X)")
    ax.set_ylabel("ICMS no ano (R$ milhões) (Y)")
    ax.grid(alpha=0.3)
    ax.legend()
    caminho = PASTA_FIG / "dispersao.png"
    fig.savefig(caminho, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return caminho


def figura_top10(dados):
    top = dados.head(10).iloc[::-1]
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    ax.barh(top["municipio"].str.title(), top["icms_total"] / 1e6, color="#2b5797")
    ax.set_xlabel("ICMS no ano (R$ milhões)")
    ax.grid(axis="x", alpha=0.3)
    caminho = PASTA_FIG / "top10.png"
    fig.savefig(caminho, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return caminho


# ----------------------------------------------------------------------------
# PDF
# ----------------------------------------------------------------------------
def montar():
    PASTA_FIG.mkdir(parents=True, exist_ok=True)
    dados = carregar_dados()
    m = ajustar(dados)
    sem_capital = ajustar(dados[dados["municipio"] != "GOIANIA"])

    with sqlite3.connect(config.CAMINHO_BANCO) as con:
        n_icms = con.execute("SELECT COUNT(*) FROM repasse_icms").fetchone()[0]
        n_frota = con.execute("SELECT COUNT(*) FROM frota").fetchone()[0]
        n_mun = con.execute("SELECT COUNT(*) FROM municipio").fetchone()[0]

    frota_mediana = int(dados["frota_total"].median())
    y_med, _, _ = prever(m, frota_mediana)

    est = getSampleStyleSheet()
    corpo = ParagraphStyle("corpo", parent=est["BodyText"], fontName="DejaVu", fontSize=10, leading=15, alignment=TA_JUSTIFY)
    h1 = ParagraphStyle("h1", parent=est["Heading2"], fontName="DejaVu-Bold", textColor=colors.HexColor("#2b5797"), spaceBefore=10)
    titulo = ParagraphStyle("titulo", parent=est["Title"], fontName="DejaVu-Bold", fontSize=17, leading=22)
    centro = ParagraphStyle("centro", parent=corpo, alignment=TA_CENTER)
    legenda = ParagraphStyle("legenda", parent=corpo, fontSize=8.5, alignment=TA_CENTER, textColor=colors.grey)

    def P(t):
        return Paragraph(t, corpo)

    def img(caminho, largura=15.5):
        from reportlab.lib.utils import ImageReader
        w, h = ImageReader(str(caminho)).getSize()
        return Image(str(caminho), width=largura * cm, height=largura * cm * h / w)

    def tabela(linhas, larguras):
        t = Table(linhas, colWidths=[l * cm for l in larguras])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b5797")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, -1), "DejaVu"),
            ("FONTNAME", (0, 0), (-1, 0), "DejaVu-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        return t

    h = []
    # Capa --------------------------------------------------------------------
    h += [Spacer(1, 2 * cm),
          Paragraph("Faculdade SENAI FATESG", centro),
          Paragraph("Curso Superior de Tecnologia em Inteligência Artificial", centro),
          Paragraph("Business Intelligence – Prof. Msc. Ujeverson Tavares Sampaio", centro),
          Spacer(1, 2.5 * cm),
          Paragraph("Frota de veículos como termômetro do ICMS:<br/>uma análise dos municípios goianos", titulo),
          Paragraph("Relatório Técnico Executivo", centro),
          Spacer(1, 2.5 * cm)]
    h.append(tabela([["Integrante", "Responsabilidade"]] + [list(e) for e in EQUIPE], [5, 10]))
    h += [Spacer(1, 3 * cm), Paragraph("Goiânia, novembro de 2026", centro), PageBreak()]

    # 1. Problema -------------------------------------------------------------
    h.append(Paragraph("1. Problema de negócio", h1))
    h.append(P(
        "O ICMS é a principal receita transferida pelo Estado aos municípios: 25% do que é arrecadado "
        "pertence às prefeituras, e a divisão segue principalmente o valor adicionado gerado em cada "
        "cidade. O problema é que esse índice é calculado com atraso, e a prefeitura nem sempre "
        "consegue antecipar quanto vai receber."))
    h.append(P(
        "Escolhemos a <b>frota de veículos</b> como segunda variável porque ela é publicada todo mês "
        "pelo DETRAN-GO, existe para todos os municípios e acompanha a atividade econômica: onde há mais "
        "comércio, indústria e agronegócio, há mais carros, motos e caminhões circulando. A pergunta que "
        "guiou o trabalho foi: <b>a frota de um município ajuda a explicar quanto ICMS ele recebe?</b>"))

    # 2. Dados ------------------------------------------------------------------
    h.append(Paragraph("2. Bases utilizadas", h1))
    h.append(tabela([
        ["Base", "Órgão", "Recorte usado", "Granularidade"],
        ["Repasses aos municípios", "SEFAZ-GO", f"ICMS creditado, jan–dez/{config.ANO}", "Município / repasse"],
        ["Frota de veículos", "DETRAN-GO", f"Frota ativa, dez/{config.ANO}", "Município / espécie"],
    ], [4.2, 2.6, 4.8, 4]))
    h.append(Spacer(1, 6))
    h.append(P(
        "As duas bases foram baixadas do Portal Dados Abertos Goiás (dadosabertos.go.gov.br) e cruzadas "
        f"pelo nome do município, chegando a <b>{m['n']} municípios</b> com as duas informações."))

    # 3. ETL ------------------------------------------------------------------
    h.append(Paragraph("3. Tratamento dos dados (ETL)", h1))
    h.append(P(
        "Todo o tratamento está no script <i>etl.py</i>, feito com pandas e numpy. Os principais passos foram:"))
    for passo in [
        "leitura automática do encoding (UTF-8 ou Latin-1) e do separador dos arquivos;",
        "padronização dos nomes dos municípios (maiúsculas, sem acento, sem apóstrofo) e correção das "
        "grafias que mudam entre as bases, como <i>Valparaíso</i> e <i>Valparaíso de Goiás</i>;",
        "conversão dos valores para número, aceitando tanto 1234.56 quanto 1.234,56;",
        "remoção de linhas duplicadas e de registros com município, data ou valor nulo;",
        "no ICMS, soma dos vários repasses semanais em um total mensal por município;",
        "na frota, uso apenas da frota <b>ativa</b> (a base também traz veículos inativos) e soma por espécie.",
    ]:
        h.append(P("• " + passo))

    # 4. Banco ----------------------------------------------------------------
    h.append(Paragraph("4. Banco de dados", h1))
    h.append(P(
        "Usamos SQLite por ser leve e ficar num único arquivo (<i>data/icms_goias.db</i>), fácil de "
        "versionar no GitHub. O modelo tem uma tabela de municípios e duas tabelas de fatos. As chaves "
        "UNIQUE impedem duplicidade e os CHECK barram valores negativos. A view <i>vw_analise</i> entrega "
        "uma linha por município, já pronta para a regressão. O script de criação está em <i>sql/schema.sql</i>."))
    h.append(img(figura_diagrama(), 14))
    h.append(Paragraph("Figura 1 – Modelo físico do banco", legenda))
    h.append(tabela([["Tabela", "Registros"], ["municipio", inteiro(n_mun)],
                     ["repasse_icms", inteiro(n_icms)], ["frota", inteiro(n_frota)]], [5, 3]))
    h.append(PageBreak())

    # 5. Modelagem --------------------------------------------------------------
    h.append(Paragraph("5. Modelagem estatística", h1))
    h.append(P(
        "<b>Variável explicativa (X):</b> frota ativa do município. <b>Variável resposta (Y):</b> ICMS "
        f"creditado ao município em {config.ANO}. A escolha segue a lógica do problema: queremos usar um "
        "dado que sai rápido (frota) para estimar um valor que interessa à gestão (ICMS)."))
    h.append(P("Os coeficientes foram calculados pelas fórmulas de mínimos quadrados:"))
    h.append(Paragraph("a = Σ(x − x̄)(y − ȳ) / Σ(x − x̄)²  &nbsp;&nbsp;&nbsp; b = ȳ − a·x̄ "
                       "&nbsp;&nbsp;&nbsp; r = Σ(x − x̄)(y − ȳ) / √[Σ(x − x̄)² · Σ(y − ȳ)²]", centro))
    h.append(Spacer(1, 6))
    h.append(P("e depois conferidos com a função OLS do statsmodels, que deu exatamente o mesmo resultado:"))
    h.append(tabela([
        ["Medida", "Cálculo manual", "statsmodels"],
        ["a (inclinação)", num(m["a"]), num(m["a_statsmodels"])],
        ["b (intercepto)", num(m["b"], 2), num(m["b_statsmodels"], 2)],
        ["r de Pearson", num(m["r"]), "–"],
        ["R²", num(m["r2"]), num(m["ols"].rsquared)],
        ["p-valor de a", f"{m['p_valor']:.2e}", "–"],
    ], [5, 4.5, 4.5]))
    h.append(Spacer(1, 8))
    h.append(Paragraph(f"<b>Ŷ = {reais(m['b'])} + {reais(m['a'])} · X</b>", centro))
    h.append(Spacer(1, 8))
    h.append(img(figura_dispersao(dados, m), 15))
    h.append(Paragraph("Figura 2 – Dispersão ICMS x Frota com a reta ajustada", legenda))

    # 6. Interpretação ----------------------------------------------------------
    h.append(Paragraph("6. Interpretação", h1))
    h.append(P(
        f"O r de {num(m['r'], 3)} indica uma correlação <b>{m['classificacao']}</b>. O R² mostra que "
        f"cerca de {m['r2']*100:.0f}% da diferença de ICMS entre os municípios acompanha a diferença de "
        f"frota. Na prática, cada veículo a mais está associado a aproximadamente {reais(m['a'])} a mais "
        f"de ICMS por ano. Para um município com a frota mediana de Goiás ({inteiro(frota_mediana)} veículos), "
        f"o modelo estima {reais(y_med)} no ano."))
    h.append(P(
        f"Testamos também o modelo <b>sem Goiânia</b>, que fica muito acima dos demais. O r passou para "
        f"{num(sem_capital['r'], 3)} ({sem_capital['classificacao']}), o que mostra se a relação se mantém "
        "nos outros municípios ou se era puxada só pela capital."))
    h.append(P(
        "Cuidados: correlação não é causa (a frota não gera ICMS, ela acompanha o tamanho da economia); "
        "municípios com indústria pesada ou usinas recebem bem mais do que a frota sugere; e o modelo só "
        "vale dentro da faixa de frota observada."))
    h.append(img(figura_top10(dados), 13))
    h.append(Paragraph("Figura 3 – Municípios que mais receberam ICMS", legenda))

    # 7. Painel ---------------------------------------------------------------
    h.append(PageBreak())
    h.append(Paragraph("7. Painel de BI", h1))
    h.append(P(
        "O painel foi feito em Streamlit (<i>app.py</i>) e faz consultas SQL direto no banco a cada "
        "interação, sem ler CSV. Ele tem cinco abas: <b>O projeto</b> (resumo do problema e do método), "
        "<b>Visão geral</b> (top 10, ICMS por mês, boxplot e frota por tipo), <b>Regressão</b> (dispersão "
        "com a reta, equação, r e R²), <b>Simulador</b> (digita-se a frota e o painel calcula Ŷ na hora, "
        "com intervalo de confiança, ou compara com um município real) e <b>Dados</b> (tabela com previsto e "
        "resíduo). Na barra lateral dá para escolher os tipos de veículo e excluir Goiânia."))
    prints = sorted(PASTA_PRINTS.glob("*.png")) + sorted(PASTA_PRINTS.glob("*.jpg"))
    for i, p in enumerate(prints, start=1):
        h.append(img(p, 15))
        h.append(Paragraph(f"Figura {3 + i} – {p.stem.replace('_', ' ').lstrip('0123456789 ').capitalize()}",
                           legenda))
        h.append(Spacer(1, 6))

    # 8. Conclusão ------------------------------------------------------------
    h.append(Paragraph("8. Conclusão", h1))
    h.append(P(
        f"A frota de veículos mostrou correlação {m['classificacao']} com o ICMS recebido pelos municípios "
        "goianos. Como a frota é atualizada todo mês, ela pode servir como um indicador rápido para a "
        "prefeitura ou para o Estado anteciparem a receita de ICMS e identificarem municípios fora do "
        "padrão (os resíduos do modelo). Como próximos passos, sugerimos testar outras variáveis junto com "
        "a frota (população, PIB, empregos) numa regressão múltipla e repetir a análise para outros anos."))
    h.append(P("<b>Repositório:</b> código, banco populado e este relatório estão no GitHub do grupo."))

    doc = SimpleDocTemplate(str(SAIDA), pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm,
                            title="Relatório Técnico - ICMS x Frota (Goiás)")
    doc.build(h)
    print(f"Relatório gerado: {SAIDA}  ({len(prints)} print(s) do painel incluído(s))")


if __name__ == "__main__":
    montar()
