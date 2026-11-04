"""Modelo de IA que roda no computador, sem enviar títulos a serviços externos."""
import logging
import os
from pathlib import Path

log = logging.getLogger("rpa.ia")

MODELO = "cardiffnlp/twitter-xlm-roberta-base-sentiment"
REVISAO = "f2f1202b1bdeb07342385c3f807f9c07cd8f5cf8"  # versão fixa: o acerto medido vale para ela
ROTULOS = {"negative": "negativo", "neutral": "neutro", "positive": "positivo"}


class ModeloLocal:
    nome = MODELO

    def __init__(self, pasta: Path):
        self.pasta = pasta
        self._classificador = None

    def _carregar(self):
        if self._classificador is None:
            marca_pronto = self.pasta / ".pronto"
            os.environ.setdefault("HF_HOME", str(self.pasta))
            if marca_pronto.exists():
                os.environ.setdefault("HF_HUB_OFFLINE", "1")  # já baixado: não depende da internet
            else:
                self.pasta.mkdir(parents=True, exist_ok=True)
                log.info("Baixando o modelo de IA na primeira execução (cerca de 2 GB)...")
            from transformers import pipeline  # import pesado: só quando há título novo para analisar
            self._classificador = pipeline("text-classification", model=MODELO, revision=REVISAO, top_k=None, device=-1)
            marca_pronto.touch()
        return self._classificador

    def prever(self, titulos: list[str]) -> dict[str, dict[str, float]]:
        resultados = self._carregar()(titulos, batch_size=16, truncation=True)
        return {t: {ROTULOS[x["label"].lower()]: x["score"] for x in r} for t, r in zip(titulos, resultados)}
