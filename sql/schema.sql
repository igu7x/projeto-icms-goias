-- =====================================================================
-- Banco: icms_goias.db (SQLite)
-- Modelo relacional simples: 1 tabela dimensão (municipio)
-- e 2 tabelas fato (repasse_icms e frota), ligadas pelo id_municipio.
-- =====================================================================

PRAGMA foreign_keys = ON;

DROP VIEW  IF EXISTS vw_analise;
DROP TABLE IF EXISTS frota;
DROP TABLE IF EXISTS repasse_icms;
DROP TABLE IF EXISTS municipio;

-- Dimensão: os 246 municípios goianos (nome padronizado, sem acento)
CREATE TABLE municipio (
    id_municipio  INTEGER PRIMARY KEY AUTOINCREMENT,
    nome          TEXT NOT NULL UNIQUE
);

-- Fato 1: ICMS repassado pelo Estado a cada município, por mês (R$)
CREATE TABLE repasse_icms (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    id_municipio  INTEGER NOT NULL REFERENCES municipio(id_municipio),
    ano_mes       INTEGER NOT NULL CHECK (ano_mes BETWEEN 200001 AND 209912),
    valor_icms    REAL    NOT NULL CHECK (valor_icms >= 0),
    UNIQUE (id_municipio, ano_mes)          -- impede duplicidade
);

-- Fato 2: frota ATIVA de veículos por município e espécie (DETRAN)
CREATE TABLE frota (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    id_municipio  INTEGER NOT NULL REFERENCES municipio(id_municipio),
    referencia    INTEGER NOT NULL,          -- ano/mês da posição da frota
    especie       TEXT    NOT NULL,          -- AUTOMOVEL, MOTOCICLETA...
    quantidade    INTEGER NOT NULL CHECK (quantidade >= 0),
    UNIQUE (id_municipio, referencia, especie)
);

CREATE INDEX idx_icms_mun  ON repasse_icms(id_municipio);
CREATE INDEX idx_frota_mun ON frota(id_municipio);

-- View usada na regressão: 1 linha por município
-- (subconsultas separadas para não multiplicar valores no JOIN)
CREATE VIEW vw_analise AS
SELECT m.id_municipio,
       m.nome                         AS municipio,
       f.frota_total,
       i.icms_total
FROM municipio m
JOIN (SELECT id_municipio, SUM(quantidade) AS frota_total
        FROM frota GROUP BY id_municipio) f ON f.id_municipio = m.id_municipio
JOIN (SELECT id_municipio, SUM(valor_icms) AS icms_total
        FROM repasse_icms GROUP BY id_municipio) i ON i.id_municipio = m.id_municipio;
