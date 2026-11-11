from .base import Anuncio, Fonte
from .mercadolivre import MercadoLivre
from .olx import OLX

DISPONIVEIS = {"olx": OLX, "mercadolivre": MercadoLivre}


def criar_fontes(config: dict) -> list[Fonte]:
    pausa = tuple(config.get("pausa_entre_requisicoes", [2, 5]))
    teto = config["regras"].get("preco_maximo_coleta")
    fontes = []
    for nome, opcoes in config.get("fontes", {}).items():
        if nome in DISPONIVEIS and opcoes.get("ativa", True):
            fontes.append(DISPONIVEIS[nome]({**opcoes, "_preco_max": teto}, pausa=pausa))
    return fontes


__all__ = ["Anuncio", "Fonte", "OLX", "MercadoLivre", "criar_fontes", "DISPONIVEIS"]
