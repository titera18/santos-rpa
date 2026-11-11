"""Mercado Livre — página de listagem de motos no Paraná.

Lê os cards do HTML (layout novo "poly-card" e o antigo "ui-search-result").
O filtro de cidade é feito depois, pelo coletor, usando a lista do config.
"""
import re
from urllib.parse import quote

from bs4 import BeautifulSoup

from ..textos import extrair_ano, extrair_km, para_inteiro
from .base import Anuncio, Fonte, log

URL_PADRAO = "https://lista.mercadolivre.com.br/veiculos/motos/parana/{termo}"


def _texto(el):
    return el.get_text(" ", strip=True) if el else ""


def interpretar(html: str) -> list[Anuncio]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("li.ui-search-layout__item, div.poly-card, div.ui-search-result__wrapper")
    anuncios, vistos = [], set()
    for card in cards:
        link = card.select_one("a.poly-component__title, h3 a, a.ui-search-link, a.ui-search-item__group__element, a[href]")
        if not link or not link.get("href"):
            continue
        url = link["href"].split("#")[0]
        m = re.search(r"(MLB-?\d+)", url)
        id_ext = m.group(1).replace("-", "") if m else url.split("?")[0]
        if id_ext in vistos:
            continue
        vistos.add(id_ext)
        titulo = _texto(card.select_one(".poly-component__title, .ui-search-item__title, h2, h3")) or _texto(link)
        preco_el = card.select_one(".poly-price__current .andes-money-amount__fraction, "
                                   ".andes-money-amount__fraction")
        preco = para_inteiro(_texto(preco_el))
        atributos = " ".join(_texto(a) for a in card.select(
            ".poly-attributes_list__item, .poly-attributes-list__item, .ui-search-card-attributes__attribute"))
        local = _texto(card.select_one(".poly-component__location, .ui-search-item__location, .ui-search-item__group__element--location"))
        cidade = local.split(" - ")[0].split(",")[0].strip() if local else ""
        img = card.find("img")
        imagem = (img.get("data-src") or img.get("src") or "") if img else ""
        km_m = re.search(r"[\d\.]+\s*km", atributos.lower())
        anuncios.append(Anuncio(
            "mercadolivre", id_ext, titulo, preco, url, cidade,
            extrair_ano(atributos, titulo), extrair_km(km_m.group(0)) if km_m else None,
            imagem if imagem.startswith("http") else "",
            {"local_completo": local}))
    return anuncios


class MercadoLivre(Fonte):
    nome = "mercadolivre"

    def buscar(self, termo: str) -> list[Anuncio]:
        modelo_url = self.config.get("url_busca", URL_PADRAO)
        paginas = int(self.config.get("paginas", 1))
        teto = self.config.get("_preco_max")
        base = modelo_url.format(termo=quote(termo.replace(" ", "-")))
        if teto:
            base += f"_PriceRange_0-{teto}"
        resultado = []
        for pagina in range(paginas):
            url = base if pagina == 0 else f"{base}_Desde_{pagina * 48 + 1}"
            achados = interpretar(self.baixar(url))
            log.info("Mercado Livre '%s' pág. %d: %d anúncios", termo, pagina + 1, len(achados))
            resultado.extend(achados)
            if len(achados) < 40:
                break
        return resultado
