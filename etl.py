"""
ETL - Extração, Tratamento e Carga
-----------------------------------
1) Baixa os dados do Portal Dados Abertos Goiás (ou usa os arquivos já
   salvos em data/raw/, caso o download falhe).
2) Limpa e padroniza: nomes de municípios, valores numéricos, nulos e duplicados.
3) Cruza ICMS x Frota pelo nome do município.
4) Cria o banco SQLite (sql/schema.sql) e carrega tudo.

Como rodar:  python etl.py
"""
import io
import re
import sqlite3
import unicodedata
import zipfile
from difflib import get_close_matches

import numpy as np
import pandas as pd
import requests

import config

# Algumas grafias mudam de uma base para outra. Corrigimos as conhecidas na mão
# e o resto tentamos casar por semelhança (difflib) mais abaixo.
APELIDOS = {
    "BOM JESUS": "BOM JESUS DE GOIAS",
    "VALPARAISO": "VALPARAISO DE GOIAS",
    "SANTA TERESA DE GOIAS": "SANTA TEREZA DE GOIAS",
    "SAO LUIZ DE MONTES BELOS": "SAO LUIS DE MONTES BELOS",
    "SAO LUIS DO NORTE": "SAO LUIZ DO NORTE",
}


# ----------------------------------------------------------------------------
# Funções auxiliares
# ----------------------------------------------------------------------------
def baixar(url, destino):
    """Baixa o arquivo só se ele ainda não existir em data/raw/."""
    if destino.exists():
        print(f"  - usando arquivo local: {destino.name}")
        return
    print(f"  - baixando {destino.name} ...")
    destino.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, timeout=180, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    destino.write_bytes(resp.content)


def padronizar_nome(nome):
    """'São João d'Aliança ' -> 'SAO JOAO DALIANCA'"""
    if pd.isna(nome):
        return np.nan
    nome = unicodedata.normalize("NFKD", str(nome)).encode("ascii", "ignore").decode()
    nome = nome.upper().replace("'", "").replace("`", "").replace("-", " ")
    nome = re.sub(r"\s+", " ", nome).strip()
    return APELIDOS.get(nome, nome)


def padronizar_coluna(col):
    col = unicodedata.normalize("NFKD", str(col)).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]+", "_", col.upper().strip().strip('"')).strip("_")


def para_numero(serie):
    """Aceita '1234.56' e também '1.234,56' (padrão brasileiro)."""
    s = serie.astype(str).str.strip().str.replace("R$", "", regex=False)
    tem_virgula = s.str.contains(",", regex=False)
    s = s.where(~tem_virgula, s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
    return pd.to_numeric(s, errors="coerce")


def ler_csv(conteudo_bytes):
    """Lê CSV detectando encoding (utf-8 ou latin-1) e separador (; ou ,)."""
    for enc in ("utf-8-sig", "latin-1"):
        try:
            texto = conteudo_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    primeira_linha = texto.splitlines()[0]
    sep = ";" if primeira_linha.count(";") >= primeira_linha.count(",") else ","
    df = pd.read_csv(io.StringIO(texto), sep=sep, dtype=str)
    df.columns = [padronizar_coluna(c) for c in df.columns]
    return df


# ----------------------------------------------------------------------------
# Extração + tratamento: ICMS
# ----------------------------------------------------------------------------
def escolher_coluna_icms(colunas):
    """
    Pelo dicionário de dados existem 3 colunas de ICMS: dedução FUNDEB,
    valor bruto e valor creditado. Usamos o valor CREDITADO (o que de fato
    entra no caixa da prefeitura). Se não houver, usamos o bruto.
    """
    icms = [c for c in colunas if "ICMS" in c and "FUNDEB" not in c and "DEDU" not in c]
    if not icms:
        return None
    for c in icms:                      # 1º: coluna com "CRED" (valor creditado)
        if "CRED" in c:
            return c
    for c in icms:                      # 2º: coluna só com o nome do imposto (ex.: VALR_ICMS)
        if c in ("ICMS", "VALR_ICMS", "VALOR_ICMS", "VL_ICMS"):
            return c
    for c in icms:                      # 3º: valor bruto
        if "BRUTO" in c:
            return c
    return icms[0]


def extrair_icms():
    baixar(config.URL_REPASSES, config.ARQ_REPASSES)

    partes = []
    with zipfile.ZipFile(config.ARQ_REPASSES) as z:
        for nome in z.namelist():
            if not nome.lower().endswith((".csv", ".txt")):
                continue
            df = ler_csv(z.read(nome))
            col_icms = escolher_coluna_icms(df.columns)
            col_mun = next((c for c in df.columns if "MUN" in c), None)
            col_anomes = next((c for c in df.columns if "ANO_MES" in c), None)
            col_data = next((c for c in df.columns if "DATA" in c and "REPASSE" in c), None) \
                or next((c for c in df.columns if "DATA" in c), None)

            if col_icms is None or col_mun is None:
                print(f"  ! {nome}: sem coluna de ICMS ou município, ignorado")
                continue
            print(f"  - {nome}: {len(df)} linhas | ICMS = '{col_icms}' | município = '{col_mun}'")

            if col_anomes:
                ano_mes = pd.to_numeric(df[col_anomes].str[:6], errors="coerce")
            else:  # deriva o ano/mês da data do repasse (AAAA-MM-DD...)
                data = pd.to_datetime(df[col_data], errors="coerce", dayfirst=False)
                ano_mes = data.dt.year * 100 + data.dt.month

            partes.append(pd.DataFrame({
                "municipio": df[col_mun].map(padronizar_nome),
                "ano_mes": ano_mes,
                "valor_icms": para_numero(df[col_icms]),
                "duplicada": df.duplicated(),   # linha idêntica a outra já lida
            }))

    if not partes:
        raise SystemExit("Nenhum arquivo com coluna de ICMS foi encontrado no ZIP de repasses.")

    bruto = pd.concat(partes, ignore_index=True)
    n0 = len(bruto)

    # Limpeza
    n_dup = int(bruto["duplicada"].sum())
    bruto = bruto[~bruto["duplicada"]]                             # linhas repetidas
    bruto = bruto.dropna(subset=["municipio", "ano_mes", "valor_icms"])  # nulos
    bruto = bruto[~bruto["municipio"].str.contains("NAO INFORMADO")]   # linha sem município
    bruto = bruto[bruto["ano_mes"] // 100 == config.ANO]          # só o ano analisado
    bruto = bruto[bruto["valor_icms"] >= 0]

    # Vários repasses no mês (semanais) -> soma mensal por município
    icms = (bruto.groupby(["municipio", "ano_mes"], as_index=False)["valor_icms"].sum())
    icms["ano_mes"] = icms["ano_mes"].astype(int)
    icms["valor_icms"] = icms["valor_icms"].round(2)

    print(f"  > ICMS: {n0} linhas lidas, {n_dup} duplicadas removidas, "
          f"{icms['municipio'].nunique()} municípios, {icms['ano_mes'].nunique()} meses")
    return icms


# ----------------------------------------------------------------------------
# Extração + tratamento: Frota
# ----------------------------------------------------------------------------
def extrair_frota():
    baixar(config.URL_FROTA, config.ARQ_FROTA)
    df = ler_csv(config.ARQ_FROTA.read_bytes())
    n0 = len(df)

    # Só a frota ATIVA (a base traz também a frota inativa/baixada)
    situacao = df["SITUACAO"].fillna("").str.upper()
    df = df[situacao.str.contains("ATIVA") & ~situacao.str.contains("INATIVA")].copy()

    df["municipio"] = df["MUNICIPIO"].map(padronizar_nome)
    df["especie"] = df["ESPECIE"].fillna("NAO INFORMADO").str.upper().str.strip()
    df["quantidade"] = para_numero(df["QTD"])
    df = df.dropna(subset=["municipio", "quantidade"])

    frota = (df.groupby(["municipio", "especie"], as_index=False)["quantidade"].sum())
    frota["quantidade"] = frota["quantidade"].astype(int)
    frota["referencia"] = config.REFERENCIA_FROTA

    print(f"  > Frota: {n0} linhas lidas, {len(df)} de frota ativa, "
          f"{frota['municipio'].nunique()} municípios, {int(frota['quantidade'].sum()):,} veículos")
    return frota


# ----------------------------------------------------------------------------
# Cruzamento dos nomes
# ----------------------------------------------------------------------------
def casar_municipios(icms, frota):
    """A lista oficial de municípios vem do ICMS. Nomes da frota que não
    batem exatamente são aproximados por semelhança (>= 90%)."""
    oficiais = sorted(icms["municipio"].unique())
    nomes_frota = frota["municipio"].unique()

    mapa, descartados = {}, []
    for n in nomes_frota:
        if n in oficiais:
            mapa[n] = n
        else:
            parecido = get_close_matches(n, oficiais, n=1, cutoff=0.9)
            if parecido:
                mapa[n] = parecido[0]
                print(f"  ~ '{n}' casado com '{parecido[0]}'")
            else:
                descartados.append(n)

    if descartados:
        print(f"  ! {len(descartados)} nome(s) da frota sem correspondência (ignorados): "
              f"{', '.join(descartados[:10])}")

    frota = frota[frota["municipio"].isin(mapa)].copy()
    frota["municipio"] = frota["municipio"].map(mapa)
    frota = frota.groupby(["municipio", "especie", "referencia"], as_index=False)["quantidade"].sum()

    sem_frota = set(oficiais) - set(frota["municipio"])
    if sem_frota:
        print(f"  ! municípios com ICMS mas sem frota: {', '.join(sorted(sem_frota))}")
    return oficiais, frota


# ----------------------------------------------------------------------------
# Carga no banco
# ----------------------------------------------------------------------------
def carregar(oficiais, icms, frota):
    config.CAMINHO_BANCO.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.CAMINHO_BANCO)
    con.executescript(config.CAMINHO_SCHEMA.read_text(encoding="utf-8"))

    con.executemany("INSERT INTO municipio (nome) VALUES (?)", [(n,) for n in oficiais])
    ids = dict(con.execute("SELECT nome, id_municipio FROM municipio").fetchall())

    con.executemany(
        "INSERT INTO repasse_icms (id_municipio, ano_mes, valor_icms) VALUES (?, ?, ?)",
        [(ids[r.municipio], int(r.ano_mes), float(r.valor_icms)) for r in icms.itertuples()],
    )
    con.executemany(
        "INSERT INTO frota (id_municipio, referencia, especie, quantidade) VALUES (?, ?, ?, ?)",
        [(ids[r.municipio], int(r.referencia), r.especie, int(r.quantidade)) for r in frota.itertuples()],
    )
    con.commit()

    # Validação rápida de integridade
    print("\n  Validação:")
    for tabela in ("municipio", "repasse_icms", "frota", "vw_analise"):
        n = con.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
        print(f"    {tabela:<13} {n:>6} registros")
    nulos = con.execute("SELECT COUNT(*) FROM vw_analise WHERE frota_total IS NULL OR icms_total IS NULL").fetchone()[0]
    print(f"    nulos na view: {nulos}")
    con.close()


def main():
    print("[1/4] ICMS")
    icms = extrair_icms()
    print("[2/4] Frota")
    frota = extrair_frota()
    print("[3/4] Cruzando municípios")
    oficiais, frota = casar_municipios(icms, frota)
    print("[4/4] Gravando no banco")
    carregar(oficiais, icms, frota)
    print(f"\nPronto! Banco salvo em {config.CAMINHO_BANCO}")


if __name__ == "__main__":
    main()
