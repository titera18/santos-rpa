"""As fontes de notícias. Para adicionar uma, edite FONTES_RSS ou FONTES_HTML."""

MAX_ARTIGOS_POR_FONTE = 200  # páginas de matérias novas abertas por fonte a cada execução
FONTES_IGNORADAS ={"instagram", "facebook", "youtube", "tiktok", "x", "linkedin"}  # redes sociais não são veículos

GOOGLE_NEWS = "https://news.google.com/rss/search?q={q}+when:30d&hl=pt-BR&gl=BR&ceid=BR:pt-419"
BUSCAS_GOOGLE = [
    '"Santos FC"',
    '"Santos Futebol Clube"',
    '"Santos" Brasileirão',
    '"Vila Belmiro"',
    '"Santos" mercado da bola reforço',
    '"Santos" técnico elenco lesão',
]

FONTES_RSS = [
    ("Gazeta Esportiva", ["https://www.gazetaesportiva.com/times/santos/feed/"]),
    ("Santos FC (oficial)", [
        "https://www.santosfc.com.br/feed/",
        "https://www.santosfc.com.br/feed/?paged=2",
        "https://www.santosfc.com.br/feed/?paged=3",
    ]),
]

# (veículo, página de listagem, regex que identifica o link de uma matéria)
FONTES_HTML = [
    ("ge", "https://ge.globo.com/sp/santos-e-regiao/futebol/times/santos/", r"/noticia/\d{4}/\d{2}/\d{2}/"),
    ("Lance", "https://www.lance.com.br/santos", r"lance\.com\.br/[\w-]+/[\w-]+\.html"),
    ("UOL", "https://www.uol.com.br/esporte/futebol/times/santos/", r"uol\.com\.br/esporte/(futebol|colunas)/.*/\d{4}/\d{2}/\d{2}/"),
    ("Terra", "https://www.terra.com.br/esportes/santos/", r"(terra\.com\.br/esportes/[\w/-]+|santistas\.net/noticias-do-santos/[\w-]+)"),
    ("CNN Brasil", "https://www.cnnbrasil.com.br/tudo-sobre/santos/", r"cnnbrasil\.com\.br/esportes/[\w/-]+"),
]

# Veículos no Google News aparecem com nomes variados.
APELIDOS_FONTE = {
    "ge.globo.com": "ge", "globo.com": "ge", "ge": "ge",
    "lance!": "Lance", "lance": "Lance", "lance.com.br": "Lance",
    "uol": "UOL", "uol esporte": "UOL", "uol.com.br": "UOL",
    "terra": "Terra", "terra.com.br": "Terra",
    "cnn brasil": "CNN Brasil", "cnnbrasil.com.br": "CNN Brasil",
    "gazeta esportiva": "Gazeta Esportiva", "gazetaesportiva.com": "Gazeta Esportiva",
    "santos fc": "Santos FC (oficial)", "santosfc.com.br": "Santos FC (oficial)",
    "santos futebol clube": "Santos FC (oficial)",
    "santistas.net": "Santistas.net", "santistas": "Santistas.net",
}


def normalizar_fonte(nome: str) -> str:
    return APELIDOS_FONTE.get(nome.strip().lower(), nome.strip())
