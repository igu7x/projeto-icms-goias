"""
Configurações gerais do projeto.
Se quiser trocar o ano analisado, é só mudar aqui (e as URLs correspondentes).
"""
from pathlib import Path

PASTA_PROJETO = Path(__file__).resolve().parent
PASTA_RAW = PASTA_PROJETO / "data" / "raw"
CAMINHO_BANCO = PASTA_PROJETO / "data" / "icms_goias.db"
CAMINHO_SCHEMA = PASTA_PROJETO / "sql" / "schema.sql"

# Ano analisado: ICMS somado de jan a dez/2025 x frota ativa de dez/2025
ANO = 2025
REFERENCIA_FROTA = 202512

# Fonte 1 - Repasses aos municípios (SEFAZ/GO) - arquivo anual compactado
URL_REPASSES = (
    "https://dadosabertos.go.gov.br/dataset/cd82f643-f203-41d9-9542-9250df93cd14/"
    "resource/2b247d3c-0299-4b50-a7a9-2040f1cf9099/download/repasses_municipios_ano_2025.zip"
)
ARQ_REPASSES = PASTA_RAW / "repasses_municipios_ano_2025.zip"

# Fonte 2 - Frota de veículos por município (DETRAN/GO) - posição de dez/2025
URL_FROTA = (
    "https://dadosabertos.go.gov.br/dataset/63d3d2c3-d12a-4c70-9706-94814772773e/"
    "resource/0037a7ef-35e4-4f34-bcc9-8c7713db7ed5/download/da_frota_202512.csv"
)
ARQ_FROTA = PASTA_RAW / "da_frota_202512.csv"
