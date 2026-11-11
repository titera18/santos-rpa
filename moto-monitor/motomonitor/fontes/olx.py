"""OLX — busca na categoria Motos da região de Curitiba e Paranaguá.

A página da OLX é feita em Next.js e traz os anúncios em JSON dentro de
<script id="__NEXT_DATA__">. Em vez de depender do caminho exato do JSON (que muda
de tempos em tempos), procuramos recursivamente objetos que tenham cara de
anúncio (subject + price + url). Se o JSON não existir, cai para o HTML dos cards.
"""
import json
import re

from bs4 import BeautifulSoup

from ..textos import extrair_ano, extrair_km, para_inteiro
from .base import Anuncio, Fonte, log

URL_PADRAO = "https://www.olx.com.br/autos-e-pecas/motos/estado-pr/regiao-de-curitiba-e-paranagua"


def _procurar_anuncios(no, achados: list):
    if isinstance(no, dict):
        if ("subject" in no or "title" in no) and "url" in no and ("price" in no or "priceValue" in no):
            achados.append(no)
            return
        for valor in no.values():
            _procurar_anuncios(valor, achados)
    elif isinstance(no, list):
        for item in no:
            _procurar_anuncios(item, achados)


def _propriedade(ad: dict, *nomes):
    for p in ad.get("properties") or []:
        if p.get("name") in nomes or p.get("label") in nomes:
            return p.get("value")
    return None


def _cidade(ad: dict) -> str:
    loc = ad.get("location")
    if isinstance(loc, str):
        return loc.split(",")[0].split(" - ")[0].strip()
    det = ad.get("locationDetails") or {}
    if det.get("municipality"):
        return det["municipality"]
    if isinstance(loc, dict):
        return loc.get("municipality") or loc.get("city") or ""
    return ""


def interpretar(html: str) -> list[Anuncio]:
    soup = BeautifulSoup(html, "html.parser")
    anuncios: list[Anuncio] = []
    script = soup.find("script", id="__NEXT_DATA__")
    if script and script.string:
        try:
            dados = json.loads(script.string)
        except json.JSONDecodeError:
            dados = None
        brutos: list = []
        _procurar_anuncios(dados, brutos)
        for ad in brutos:
            url = ad.get("url") or ""
            id_ext = str(ad.get("listId") or ad.get("id") or (re.findall(r"(\d{6,})", url) or [url])[-1])
            titulo = ad.get("subject") or ad.get("title") or ""
            preco = para_inteiro(ad.get("priceValue") or ad.get("price"))
            ano = extrair_ano(_propriedade(ad, "regdate", "Ano"), titulo)
            km = extrair_km(_propriedade(ad, "mileage", "Quilometragem"))
            imagem = ""
            imgs = ad.get("images") or []
            if imgs and isinstance(imgs[0], dict):
                imagem = imgs[0].get("original") or imgs[0].get("originalWebp") or ""
            elif ad.get("thumbnail"):
                imagem = ad["thumbnail"]
            anuncios.append(Anuncio("olx", id_ext, titulo, preco, url, _cidade(ad), ano, km, imagem))
        if anuncios:
            return _sem_repetidos(anuncios)

    # Plano B: HTML dos cards
    for card in soup.select("section.olx-adcard, li[data-ds-component='DS-AdCard'], div[data-ds-component='DS-AdCard']"):
        link = card.find("a", href=True)
        if not link:
            continue
        titulo_el = card.find(["h2", "h3"])
        titulo = titulo_el.get_text(" ", strip=True) if titulo_el else link.get("title", "")
        texto = card.get_text(" ", strip=True)
        preco_m = re.search(r"R\$\s*[\d\.]+", texto)
        url = link["href"]
        id_ext = (re.findall(r"(\d{6,})", url) or [url])[-1]
        local = card.select_one(".olx-adcard__location, [class*='location']")
        cidade = local.get_text(strip=True).split(",")[0] if local else ""
        img = card.find("img")
        anuncios.append(Anuncio(
            "olx", id_ext, titulo, para_inteiro(preco_m.group(0)) if preco_m else None, url, cidade,
            extrair_ano(texto), extrair_km(re.search(r"[\d\.]+\s*km", texto).group(0)) if re.search(r"[\d\.]+\s*km", texto) else None,
            img.get("src", "") if img else ""))
    return _sem_repetidos(anuncios)


def _sem_repetidos(anuncios):
    vistos, saida = set(), []
    for a in anuncios:
        if a.id_externo not in vistos:
            vistos.add(a.id_externo)
            saida.append(a)
    return saida


class OLX(Fonte):
    nome = "olx"

    def buscar(self, termo: str) -> list[Anuncio]:
        url = self.config.get("url_busca", URL_PADRAO)
        paginas = int(self.config.get("paginas", 2))
        teto = self.config.get("_preco_max")
        resultado: list[Anuncio] = []
        for pagina in range(1, paginas + 1):
            params = {"q": termo}
            if teto:
                params["pe"] = teto
            if pagina > 1:
                params["o"] = pagina
            html = self.baixar(url, params)
            achados = interpretar(html)
            log.info("OLX '%s' pág. %d: %d anúncios", termo, pagina, len(achados))
            resultado.extend(achados)
            if len(achados) < 20:
                break
        return resultado
