"""Extrai título, data e resumo do HTML e dos feeds."""
import calendar
import json
import re
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup

from santos_rpa.dominio.modelo import BRT

def limpar_url(url: str) -> str:
    """Remove fragmentos e parâmetros de rastreamento (utm_*, etc.)."""
    p = urlparse(url)
    q = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith(("utm_", "fbclid", "gclid"))]
    return urlunparse(p._replace(query=urlencode(q), fragment=""))


def texto_limpo(html: str, limite: int = 300) -> str:
    t = " ".join(BeautifulSoup(html or "", "lxml").get_text(" ", strip=True).split())
    return t[:limite]


def data_do_feed(entry) -> datetime | None:
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


def data_na_url(url: str) -> datetime | None:
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
    return data, texto_limpo(desc.get("content", "")) if desc else ""
