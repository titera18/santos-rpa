"""Adaptadores da porta FonteDeNoticias: feeds RSS, Google News e páginas HTML dos veículos.

Guardam apenas título, resumo e link, nunca o texto integral.
"""
import logging
import re
from dataclasses import dataclass
from urllib.parse import quote_plus, urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

from santos_rpa.dominio.modelo import ItemColetado
from santos_rpa.infraestrutura.coleta.catalogo import (BUSCAS_GOOGLE, FONTES_HTML, FONTES_IGNORADAS, FONTES_RSS,
                                                       GOOGLE_NEWS, MAX_ARTIGOS_POR_FONTE, normalizar_fonte)
from santos_rpa.infraestrutura.coleta.cliente_http import BloqueadoPorRobots, Cliente
from santos_rpa.infraestrutura.coleta.extracao import (data_do_feed, data_na_url, limpar_url, metadados_do_artigo,
                                                       texto_limpo)

log = logging.getLogger("rpa.coleta")

def coletar_rss(cliente: Cliente, fonte: str, urls: list[str]) -> list[ItemColetado]:
    itens, erro = [], None
    for url in urls:
        try:
            feed = feedparser.parse(cliente.get(url).content)
        except requests.RequestException as e:
            erro = e  # páginas extras do feed podem não existir; só falha se nada vier
            continue
        for e in feed.entries:
            if e.get("title") and e.get("link"):
                itens.append(ItemColetado(texto_limpo(e.title, 250), limpar_url(e.link), fonte, "rss",
                                       texto_limpo(e.get("summary", "")), data_do_feed(e), "feed"))
    if not itens and erro:
        raise erro
    return itens


def coletar_google_news(cliente: Cliente) -> list[ItemColetado]:
    itens, vistos, erro = [], set(), None
    for busca in BUSCAS_GOOGLE:
        url = GOOGLE_NEWS.format(q=quote_plus(busca))
        try:
            feed = feedparser.parse(cliente.get(url, ignorar_robots=True).content)  # feed público de busca
        except requests.RequestException as e:
            erro = e
            continue
        for e in feed.entries:
            if e.link in vistos:
                continue
            vistos.add(e.link)
            veiculo = (e.get("source") or {}).get("title", "").strip() or "Google News"
            if veiculo.lower() in FONTES_IGNORADAS:
                continue
            titulo = texto_limpo(e.title, 250)
            # O Google acrescenta o veículo ao título, às vezes mais de uma vez ("X | Ge - ge").
            sufixo = re.compile(rf"\s*[-|]\s*{re.escape(veiculo)}\s*$", re.IGNORECASE)
            while sufixo.search(titulo):
                titulo = sufixo.sub("", titulo)
            itens.append(ItemColetado(titulo, e.link, normalizar_fonte(veiculo), "google_news",
                                   "", data_do_feed(e), "feed"))
    if not itens and erro:
        raise erro
    return itens


def coletar_html(cliente: Cliente, fonte: str, pagina: str, padrao: str, ja_conhecida) -> list[ItemColetado]:
    """Lê a listagem do veículo e abre as matérias novas para obter data e resumo."""
    s = BeautifulSoup(cliente.get(pagina).content, "lxml")
    regex = re.compile(padrao)
    dominio_base = urlparse(pagina).netloc
    achados: dict[str, ItemColetado] = {}
    for a in s.find_all("a", href=True):
        url = limpar_url(urljoin(pagina, a["href"]))
        if url.rstrip("/") == pagina.rstrip("/") or not regex.search(url) or "/videos/" in url:
            continue
        titulo = " ".join(a.get_text(" ", strip=True).split())
        if not 25 <= len(titulo) <= 200:
            continue
        host = urlparse(url).netloc
        veiculo = fonte if host == dominio_base else normalizar_fonte(host.removeprefix("www."))
        if url not in achados:
            achados[url] = ItemColetado(titulo, url, veiculo, "html", "", data_na_url(url),
                                     "url" if data_na_url(url) else "coleta")

    abertos = 0
    for item in achados.values():
        if abertos >= MAX_ARTIGOS_POR_FONTE or ja_conhecida(item):
            continue
        abertos += 1
        try:
            data, resumo = metadados_do_artigo(cliente.get(item.url).content)
        except (requests.RequestException, BloqueadoPorRobots) as e:
            log.debug("artigo não lido %s: %s", item.url, e)
            continue
        item.resumo = resumo
        if data:
            item.publicado_em, item.data_origem = data, "pagina"
    return list(achados.values())


@dataclass
class FonteRss:
    nome: str
    urls: list[str]
    cliente: Cliente
    agregador: bool = False

    def coletar(self, ja_conhecida) -> list[ItemColetado]:
        return coletar_rss(self.cliente, self.nome, self.urls)


@dataclass
class FonteHtml:
    nome: str
    pagina: str
    padrao: str
    cliente: Cliente
    agregador: bool = False

    def coletar(self, ja_conhecida) -> list[ItemColetado]:
        return coletar_html(self.cliente, self.nome, self.pagina, self.padrao, ja_conhecida)


@dataclass
class FonteGoogleNews:
    cliente: Cliente
    nome: str = "Google News"
    agregador: bool = True  # o link direto do veículo tem prioridade sobre o redirecionamento do agregador

    def coletar(self, ja_conhecida) -> list[ItemColetado]:
        return coletar_google_news(self.cliente)


def criar_fontes() -> list:
    """Monta todas as fontes do catálogo."""
    cliente = Cliente()
    return ([FonteRss(nome, urls, cliente) for nome, urls in FONTES_RSS]
            + [FonteHtml(nome, pagina, padrao, cliente) for nome, pagina, padrao in FONTES_HTML]
            + [FonteGoogleNews(cliente)])
