"""Regras de alerta.

Um anúncio de moto do catálogo gera alerta quando:
  1. preço <= preco_alvo (padrão R$ 18.000); OU
  2. preço <= teto_fipe (padrão R$ 30.000) E pelo menos desconto_fipe (10%) abaixo da FIPE.
Preços absurdamente baixos (< preco_minimo_plausivel) costumam ser entrada/parcela
ou golpe, então são ignorados.
"""
from .textos import moeda


def desconto(preco: int, fipe: float | None) -> float | None:
    if not fipe or not preco:
        return None
    return round((fipe - preco) / fipe, 4)


def avaliar(preco: int | None, fipe: float | None, regras: dict) -> list[str]:
    if not preco or preco < regras.get("preco_minimo_plausivel", 0):
        return []
    motivos = []
    if preco <= regras["preco_alvo"]:
        motivos.append(f"Abaixo de {moeda(regras['preco_alvo'])}")
    d = desconto(preco, fipe)
    if d is not None and preco <= regras["teto_fipe"] and d >= regras["desconto_fipe"]:
        motivos.append(f"{d * 100:.0f}% abaixo da FIPE ({moeda(fipe)})")
    return motivos
