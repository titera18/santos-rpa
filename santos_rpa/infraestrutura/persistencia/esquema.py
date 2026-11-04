"""Tabelas do banco SQLite."""

ESQUEMA = """
CREATE TABLE IF NOT EXISTS noticias (
    id                INTEGER PRIMARY KEY,
    chave             TEXT NOT NULL UNIQUE,   -- hash de título + veículo (evita duplicatas)
    titulo            TEXT NOT NULL,
    resumo            TEXT,
    url               TEXT NOT NULL,
    fonte             TEXT NOT NULL,          -- veículo que publicou
    coletor           TEXT NOT NULL,          -- rss | html | google_news
    publicado_em      TEXT NOT NULL,          -- ISO 8601 em UTC
    data_origem       TEXT NOT NULL,          -- feed | pagina | url | coleta (estimada)
    coletado_em       TEXT NOT NULL,
    visto_em          TEXT NOT NULL,
    foco              REAL NOT NULL,          -- 0-30: quão central o clube é na notícia
    tema              TEXT,
    tema_pts          REAL DEFAULT 0,         -- 0-25: peso do tema
    repercussao_pts   REAL DEFAULT 0,         -- 0-25: quantos veículos cobriram a história
    recencia_pts      REAL DEFAULT 0,         -- 0-20: decai com a idade da notícia
    relevancia        REAL DEFAULT 0,         -- 0-100: soma dos quatro componentes
    sentimento        TEXT,                   -- positivo | neutro | negativo
    sentimento_score  REAL DEFAULT 0,         -- de -1 (ruim para o clube) a 1 (bom para o clube)
    sentimento_termos TEXT DEFAULT '[]',      -- JSON com os termos que pesaram na nota
    sentimento_origem TEXT DEFAULT 'regras',  -- regras | ia
    historia_id       INTEGER,                -- agrupa notícias sobre o mesmo fato
    veiculos_historia INTEGER DEFAULT 1,
    nomes             TEXT DEFAULT '[]'       -- JSON com nomes próprios do título
);
CREATE INDEX IF NOT EXISTS ix_noticias_data ON noticias(publicado_em);
CREATE INDEX IF NOT EXISTS ix_noticias_relev ON noticias(relevancia DESC);

-- Previsões do modelo de IA por título, para não repetir o cálculo a cada execução.
CREATE TABLE IF NOT EXISTS ia_previsoes (
    titulo   TEXT NOT NULL,
    modelo   TEXT NOT NULL,
    negativo REAL NOT NULL,
    neutro   REAL NOT NULL,
    positivo REAL NOT NULL,
    PRIMARY KEY (titulo, modelo)
);

-- Itens rejeitados pelo filtro, para auditar falsos negativos.
CREATE TABLE IF NOT EXISTS descartes (
    url        TEXT PRIMARY KEY,
    titulo     TEXT,
    fonte      TEXT,
    motivo     TEXT,
    visto_em   TEXT
);

CREATE TABLE IF NOT EXISTS execucoes (
    id      INTEGER PRIMARY KEY,
    inicio  TEXT NOT NULL,
    fim     TEXT,
    novas   INTEGER DEFAULT 0,
    status  TEXT
);

CREATE TABLE IF NOT EXISTS execucao_fontes (
    execucao_id INTEGER NOT NULL REFERENCES execucoes(id),
    fonte       TEXT NOT NULL,
    status      TEXT NOT NULL,   -- ok | vazio | erro
    brutos      INTEGER DEFAULT 0,
    aceitos     INTEGER DEFAULT 0,
    novos       INTEGER DEFAULT 0,
    erro        TEXT,
    segundos    REAL
);
"""
