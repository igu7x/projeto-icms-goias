# ICMS x Frota de Veículos – Municípios de Goiás

Situação de Aprendizagem – Business Intelligence · Faculdade SENAI FATESG

**Equipe:** Igor Freitas · João Pedro · Ryan · Hebert

## Pergunta
Municípios com mais veículos recebem mais ICMS? Usamos a frota ativa (DETRAN-GO) como
variável explicativa **X** e o ICMS repassado no ano (SEFAZ-GO) como variável resposta **Y**,
e ajustamos uma regressão linear simples **Ŷ = b + aX**.

## Fontes (Portal Dados Abertos Goiás)
| Base | Link | Recorte |
|---|---|---|
| Repasses aos municípios | https://dadosabertos.go.gov.br/dataset/repasses | ICMS creditado, jan–dez/2025 |
| Frota de veículos (DETRAN) | https://dadosabertos.go.gov.br/dataset/frota-de-veiculos | Frota ativa, dez/2025 |

## Estrutura
```
├── config.py          # caminhos, ano e URLs
├── etl.py             # extração, limpeza, cruzamento e carga no banco
├── sql/schema.sql     # DDL do banco (tabelas, chaves, view)
├── modelo.py          # correlação + regressão (manual e statsmodels)
├── app.py             # painel Streamlit (consulta o banco em tempo real)
├── relatorio.py       # gera docs/Relatorio_Tecnico.pdf a partir do banco
├── data/
│   ├── raw/           # arquivos baixados do portal
│   └── icms_goias.db  # banco SQLite populado
└── docs/              # relatório, figuras e prints do painel
```

## Como rodar (Python 3.11 ou superior)
```bash
pip install -r requirements.txt
python etl.py            # baixa os dados e cria data/icms_goias.db
python modelo.py         # mostra a, b, r e R² no terminal
streamlit run app.py     # abre o painel no navegador
python relatorio.py      # gera o PDF do relatório
```
No Windows dá para só dar dois cliques em `rodar.bat`.

Se o download pelo script falhar (o portal às vezes fica lento), baixe os dois arquivos
pelo navegador e coloque em `data/raw/` com estes nomes:
`repasses_municipios_ano_2025.zip` e `da_frota_202512.csv`. O ETL usa os arquivos locais.

## Banco de dados
- `municipio (id_municipio PK, nome UNIQUE)`
- `repasse_icms (id PK, id_municipio FK, ano_mes, valor_icms)` – UNIQUE(id_municipio, ano_mes)
- `frota (id PK, id_municipio FK, referencia, especie, quantidade)` – UNIQUE(id_municipio, referencia, especie)
- `vw_analise` – uma linha por município com `frota_total` e `icms_total`
