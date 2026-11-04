"""Modelo de IA local que complementa as regras de sentimento.

As regras decidem primeiro, pois leem a notícia do ponto de vista do clube. O modelo só opina quando
elas dão neutro e ele tem confiança suficiente. Roda no computador, sem enviar títulos a serviços externos.
Se o modelo falhar, o robô segue só com as regras.
"""
import logging
import os
from pathlib import Path

log = logging.getLogger("rpa.ia")

MODELO = "cardiffnlp/twitter-xlm-roberta-base-sentiment"
REVISAO = "f2f1202b1bdeb07342385c3f807f9c07cd8f5cf8"  # versão fixa: o acerto medido vale para ela
CONFIANCA_MINIMA = 0.70
PASTA_MODELOS = Path(__file__).resolve().parent / "modelos"
MARCA_PRONTO = PASTA_MODELOS / ".pronto"
ROTULOS = {"negative": "negativo", "neutral": "neutro", "positive": "positivo"}

_classificador = None
indisponivel = False  # o modelo falhou nesta execução


def _carregar():
    global _classificador
    if _classificador is None:
        os.environ.setdefault("HF_HOME", str(PASTA_MODELOS))
        if MARCA_PRONTO.exists():
            os.environ.setdefault("HF_HUB_OFFLINE", "1")  # já baixado: não depende da internet
        else:
            log.info("Baixando o modelo de IA na primeira execução (cerca de 2 GB)...")
        from transformers import pipeline
        _classificador = pipeline("text-classification", model=MODELO, revision=REVISAO, top_k=None, device=-1)
        MARCA_PRONTO.touch()
    return _classificador


def _prever(titulos: list[str]) -> dict[str, dict[str, float]]:
    resultados = _carregar()(titulos, batch_size=16, truncation=True)
    return {t: {ROTULOS[x["label"].lower()]: x["score"] for x in r} for t, r in zip(titulos, resultados)}


def probabilidades(con, titulos: list[str]) -> dict[str, dict[str, float]]:
    """Previsões dos títulos, usando o que já está no banco. Sem o modelo, devolve só o que há no banco."""
    global indisponivel
    titulos = sorted(set(titulos))
    guardadas = {
        r["titulo"]: {"negativo": r["negativo"], "neutro": r["neutro"], "positivo": r["positivo"]}
        for r in con.execute("SELECT titulo, negativo, neutro, positivo FROM ia_previsoes WHERE modelo = ?", (MODELO,))
    }
    faltando = [t for t in titulos if t not in guardadas]
    if faltando:
        try:
            novas = _prever(faltando)
        except Exception as e:  # uma falha do modelo não pode derrubar o robô
            log.warning("Modelo de IA indisponível; %d títulos ficam só com as regras: %s", len(faltando), e)
            indisponivel = True
            novas = {}
        con.executemany(
            "INSERT OR REPLACE INTO ia_previsoes (titulo, modelo, negativo, neutro, positivo) VALUES (?,?,?,?,?)",
            [(t, MODELO, p["negativo"], p["neutro"], p["positivo"]) for t, p in novas.items()],
        )
        guardadas.update(novas)
    return {t: guardadas[t] for t in titulos if t in guardadas}


def combinar(rotulo: str, nota: float, probs: dict[str, float] | None) -> tuple[str, float, str]:
    """Retorna (rótulo, nota de -1 a 1, origem). A nota do modelo vai até 0,5 em módulo: nunca supera um resultado de jogo."""
    if rotulo != "neutro" or not probs:
        return rotulo, nota, "regras"
    maior = max(probs, key=probs.get)
    if maior == "neutro" or probs[maior] < CONFIANCA_MINIMA:
        return rotulo, nota, "regras"
    sinal = 1 if maior == "positivo" else -1
    return maior, round(sinal * probs[maior] / 2, 2), "ia"
