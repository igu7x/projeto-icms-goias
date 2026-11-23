# Roteiro da apresentação (15 min + 5 de perguntas)

A apresentação inteira é feita **dentro do painel** (não precisa de slides).
Deixe o painel aberto (`streamlit run app.py`) e o VS Code aberto com o código antes de começar.

---

## 1. Hebert — O problema (3 min) · aba "📌 O projeto"
- Apresenta o grupo e quem fez o quê.
- "O ICMS é a maior transferência do Estado para as prefeituras. 25% do ICMS arrecadado é dos
  municípios, e a divisão depende do quanto cada cidade movimenta na economia."
- "Só que esse cálculo sai com atraso. A gente quis ver se um dado que sai todo mês, a **frota de
  veículos**, ajuda a explicar e estimar quanto cada município recebe."
- Mostra X e Y na tela: **X = frota ativa**, **Y = ICMS do ano**.

## 2. Igor — Dados, ETL e banco (4 min) · VS Code: `etl.py` e `sql/schema.sql`
- Duas bases do portal: Repasses (SEFAZ) e Frota (DETRAN), as duas por município.
- Problemas que encontramos e como resolvemos:
  - nomes diferentes entre as bases (acento, "Valparaíso" x "Valparaíso de Goiás") → padronização + correção;
  - ICMS vem em vários repasses por mês → somamos por mês;
  - frota vem com veículos inativos → filtramos só a frota ativa;
  - nulos e duplicados → removidos.
- Abre o `schema.sql`: 3 tabelas + 1 view, chaves UNIQUE para não duplicar, CHECK para não ter valor negativo.
- Mostra o terminal rodando `python etl.py` (ou o print da saída) com a validação no final.

## 3. João Pedro — Estatística (4 min) · aba "📈 Regressão"
- Mostra o gráfico de dispersão com a reta vermelha.
- Lê a equação na tela: **Ŷ = b + aX**, e explica:
  - **a** = quanto o ICMS sobe, em média, para cada veículo a mais;
  - **b** = ponto onde a reta corta o eixo Y (sozinho não tem muito sentido prático).
- Lê o **r** e o **R²** do painel e usa a tabela abaixo para interpretar.
- Mostra que o cálculo manual bateu com o statsmodels (legenda embaixo).
- Marca "Excluir Goiânia" na barra lateral e comenta se o r caiu muito ou pouco.
- Frase de efeito: "correlação não é causa: a frota não gera ICMS, ela acompanha o tamanho da economia."

| r (em módulo) | como falar |
|---|---|
| 0,9 a 1 | muito forte |
| 0,7 a 0,9 | forte |
| 0,5 a 0,7 | moderada |
| 0,3 a 0,5 | fraca |
| abaixo de 0,3 | praticamente não há relação linear |

## 4. Ryan — Painel e simulador (3 min) · abas "📊 Visão geral", "🧮 Simulador", "🗃️ Dados"
- Visão geral: top 10, ICMS mês a mês, boxplot (mostra que poucos municípios concentram muito).
- Simulador: digita uma frota (ex.: 20.000) e mostra o Ŷ calculado na hora.
- Escolhe um município real (ex.: o da cidade de alguém do grupo) e compara previsto x real.
- Aba Dados: explica o resíduo (positivo = recebe mais do que a frota sugere → polo industrial/agro).
- Reforça: "tudo aqui é consulta SQL no banco, não tem CSV sendo lido".

## 5. Hebert — Fecha (1 min)
- Conclusão em uma frase usando o r que apareceu.
- Uso prático: prefeitura/Estado podem usar a frota como termômetro rápido da receita.
- Próximo passo: regressão múltipla (frota + população + PIB).

---

## Perguntas que a banca pode fazer

**Por que a frota é X e o ICMS é Y?**
Porque a ideia é usar um dado rápido (frota, mensal) para estimar um dado que interessa à gestão (ICMS).
Faz sentido de negócio: a frota acompanha a atividade econômica, que é o que define o repasse.

**A correlação alta não é só porque cidade grande tem tudo maior?**
Em boa parte, sim, e a gente não esconde isso: a frota funciona como um indicador do tamanho econômico.
Por isso testamos sem Goiânia no filtro. Uma melhoria seria dividir as duas variáveis pela população (per capita).

**O que é o R²?**
A proporção da variação do ICMS entre os municípios que a reta consegue explicar. R² de 0,80 = 80%.

**O que é o p-valor?**
A chance de achar uma inclinação dessas se na verdade não houvesse relação nenhuma. Bem abaixo de 0,05 = relação estatisticamente significativa.

**Como vocês calcularam a e b?**
Pelas fórmulas de mínimos quadrados no `modelo.py` (função `ajustar`), e conferimos com `statsmodels.OLS`: deu igual.

**Por que SQLite?**
É relacional, não precisa de servidor, fica num arquivo só e dá para subir no GitHub junto com o código.

**Como garantiram que não tem duplicado?**
Removemos no pandas e o banco tem `UNIQUE (id_municipio, ano_mes)` e `UNIQUE (id_municipio, referencia, especie)`: se tentar inserir repetido, dá erro.

**Por que valor creditado e não bruto?**
O creditado é o que realmente entra na conta da prefeitura, depois da dedução de 20% do FUNDEB. Como a dedução é proporcional, a correlação seria praticamente a mesma com o bruto.

**Qual a limitação do simulador?**
Só vale dentro da faixa de frota observada e mostra a média esperada; cada município tem suas particularidades (indústria, usinas, mineração).
