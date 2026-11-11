"""Base comum dos coletores de anúncios."""
import logging
import random
import time
from dataclasses import dataclass, field

import requests

log = logging.getLogger(__name__)

CABECALHOS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


@dataclass
class Anuncio:
    fonte: str
    id_externo: str
    titulo: str
    preco: int | None
    url: str
    cidade: str = ""
    ano: int | None = None
    km: int | None = None
    imagem: str = ""
    extras: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        return f"{self.fonte}:{self.id_externo}"


class Fonte:
    nome = "base"

    def __init__(self, config: dict, pausa=(2, 5), sessao=None):
        self.config = config
        self.pausa = pausa
        self.sessao = sessao or requests.Session()
        self.sessao.headers.update(CABECALHOS)

    def baixar(self, url: str, params=None) -> str:
        time.sleep(random.uniform(*self.pausa))
        resp = self.sessao.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.text

    def buscar(self, termo: str) -> list[Anuncio]:
        raise NotImplementedError
