"""Coleta de notícias: feeds RSS, Google News e páginas HTML dos veículos.

O robô se identifica no User-Agent, respeita o robots.txt, espera entre requisições
ao mesmo domínio e guarda apenas título, resumo e link, nunca o texto integral.
"""
import calendar
import json
import logging
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, quote_plus, urlencode, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import feedparser
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger("rpa.coleta")

USER_AGENT = "Mozilla/5.0 (compatible; SantosNewsRPA/1.0; uso pessoal)"
BRT = timezone(timedelta(hours=-3))
ESPERA_POR_DOMINIO = 1.0   # segundos entre requisições ao mesmo domínio
MAX_ARTIGOS_POR_FONTE = 200  # páginas de matérias novas abertas por fonte a cada execução
FONTES_IGNORADAS = {"instagram", "facebook", "youtube", "tiktok", "x", "linkedin"}  # redes sociais não são veículos

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


@dataclass
class ItemBruto:
    titulo: str
    url: str
    fonte: str
    coletor: str
    resumo: str = ""
    publicado_em: datetime | None = None
    data_origem: str = "coleta"


class BloqueadoPorRobots(Exception):
    pass


class Cliente:
    """HTTP educado: robots.txt em cache, espera por domínio e novas tentativas."""

    def __init__(self):
        self.sessao = requests.Session()
        self.sessao.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9"})
        retry = Retry(total=2, backoff_factor=1.5, status_forcelist=[429, 500, 502, 503, 504])
        self.sessao.mount("https://", HTTPAdapter(max_retries=retry))
        self._robots: dict[str, RobotFileParser | None] = {}
        self._ultimo: dict[str, float] = {}
        self._trava = threading.Lock()

    def _permitido(self, url: str) -> bool:
        p = urlparse(url)
        base = f"{p.scheme}://{p.netloc}"
        with self._trava:
            conhecido = base in self._robots
            robo = self._robots.get(base)
        if not conhecido:
            robo = None
            try:
                r = self.sessao.get(f"{base}/robots.txt", timeout=10)
                if r.status_code == 200:
                    robo = RobotFileParser()
                    robo.parse(r.text.splitlines())
            except requests.RequestException:
                pass  # sem robots.txt acessível: segue, mantendo a espera por domínio
            with self._trava:
                self._robots[base] = robo
        return robo is None or robo.can_fetch(USER_AGENT, url)

    def _aguardar_vez(self, dominio: str):
        with self._trava:
            agora = time.monotonic()
            livre = max(agora, self._ultimo.get(dominio, 0) + ESPERA_POR_DOMINIO)
            self._ultimo[dominio] = livre
        if livre > agora:
            time.sleep(livre - agora)

    def get(self, url: str, ignorar_robots: bool = False) -> requests.Response:
        if not ignorar_robots and not self._permitido(url):
            raise BloqueadoPorRobots(url)
        self._aguardar_vez(urlparse(url).netloc)
        r = self.sessao.get(url, timeout=20)
        r.raise_for_status()
        return r


def limpar_url(url: str) -> str:
    """Remove fragmentos e parâmetros de rastreamento (utm_*, etc.)."""
    p = urlparse(url)
    q = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith(("utm_", "fbclid", "gclid"))]
    return urlunparse(p._replace(query=urlencode(q), fragment=""))


def _texto(html: str, limite: int = 300) -> str:
    t = " ".join(BeautifulSoup(html or "", "lxml").get_text(" ", strip=True).split())
    return t[:limite]


def _data_feed(entry) -> datetime | None:
    st = entry.get("published_parsed") or entry.get("updated_parsed")
    return datetime.fromtimestamp(calendar.timegm(st), timezone.utc) if st else None


def interpretar_data(bruto: str | None) -> datetime | None:
    """Converte datas ISO; sem fuso, assume horário de Brasília."""
    if not bruto:
        return None
    try:
        d = datetime.fromisoformat(bruto.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return d.replace(tzinfo=BRT) if d.tzinfo is None else d


def _data_na_url(url: str) -> datetime | None:
    m = re.search(r"/(20\d{2})/(\d{2})/(\d{2})/", url)
    if not m:
        return None
    try:
        return datetime(int(m[1]), int(m[2]), int(m[3]), 12, tzinfo=BRT)
    except ValueError:
        return None


def _procurar_data_jsonld(no) -> str | None:
    if isinstance(no, dict):
        if isinstance(no.get("datePublished"), str):
            return no["datePublished"]
        no = list(no.values())
    if isinstance(no, list):
        for filho in no:
            achada = _procurar_data_jsonld(filho) if isinstance(filho, (dict, list)) else None
            if achada:
                return achada
    return None


def metadados_do_artigo(html: bytes) -> tuple[datetime | None, str]:
    """Extrai data de publicação e descrição das meta tags da matéria."""
    s = BeautifulSoup(html, "lxml")
    data = None
    for attrs in ({"property": "article:published_time"}, {"name": "article:published_time"},
                  {"itemprop": "datePublished"}, {"name": "date"}):
        tag = s.find("meta", attrs=attrs)
        data = interpretar_data(tag.get("content")) if tag else None
        if data:
            break
    if not data:
        for bloco in s.select('script[type="application/ld+json"]'):
            try:
                data = interpretar_data(_procurar_data_jsonld(json.loads(bloco.string or "")))
            except (ValueError, TypeError):
                continue
            if data:
                break
    if not data:
        tag = s.find("time", attrs={"datetime": True})
        data = interpretar_data(tag["datetime"]) if tag else None
    desc = s.find("meta", attrs={"property": "og:description"}) or s.find("meta", attrs={"name": "description"})
    return data, _texto(desc.get("content", "")) if desc else ""


def coletar_rss(cliente: Cliente, fonte: str, urls: list[str]) -> list[ItemBruto]:
    itens, erro = [], None
    for url in urls:
        try:
            feed = feedparser.parse(cliente.get(url).content)
        except requests.RequestException as e:
            erro = e  # páginas extras do feed podem não existir; só falha se nada vier
            continue
        for e in feed.entries:
            if e.get("title") and e.get("link"):
                itens.append(ItemBruto(_texto(e.title, 250), limpar_url(e.link), fonte, "rss",
                                       _texto(e.get("summary", "")), _data_feed(e), "feed"))
    if not itens and erro:
        raise erro
    return itens


def coletar_google_news(cliente: Cliente) -> list[ItemBruto]:
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
            titulo = _texto(e.title, 250)
            # O Google acrescenta o veículo ao título, às vezes mais de uma vez ("X | Ge - ge").
            sufixo = re.compile(rf"\s*[-|]\s*{re.escape(veiculo)}\s*$", re.IGNORECASE)
            while sufixo.search(titulo):
                titulo = sufixo.sub("", titulo)
            itens.append(ItemBruto(titulo, e.link, normalizar_fonte(veiculo), "google_news",
                                   "", _data_feed(e), "feed"))
    if not itens and erro:
        raise erro
    return itens


def coletar_html(cliente: Cliente, fonte: str, pagina: str, padrao: str, ja_conhecida) -> list[ItemBruto]:
    """Lê a listagem do veículo e abre as matérias novas para obter data e resumo."""
    s = BeautifulSoup(cliente.get(pagina).content, "lxml")
    regex = re.compile(padrao)
    dominio_base = urlparse(pagina).netloc
    achados: dict[str, ItemBruto] = {}
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
            achados[url] = ItemBruto(titulo, url, veiculo, "html", "", _data_na_url(url),
                                     "url" if _data_na_url(url) else "coleta")

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


def tarefas_de_coleta(cliente: Cliente, ja_conhecida):
    """Retorna (nome da fonte, função sem argumentos) para cada fonte configurada."""
    tarefas = [(f, lambda f=f, u=u: coletar_rss(cliente, f, u)) for f, u in FONTES_RSS]
    tarefas += [(f, lambda f=f, p=p, r=r: coletar_html(cliente, f, p, r, ja_conhecida)) for f, p, r in FONTES_HTML]
    tarefas.append(("Google News", lambda: coletar_google_news(cliente)))
    return tarefas
