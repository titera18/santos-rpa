"""Consulta à Tabela FIPE pela API pública parallelum (https://deividfortuna.github.io/fipe/).

As respostas ficam em cache no SQLite para não estourar o limite diário da API:
marcas/modelos/anos por 30 dias e valores por 7 dias.
"""
import logging
import statistics

import requests

from .modelos import Modelo
from .textos import normalizar, para_inteiro

log = logging.getLogger(__name__)


class Fipe:
    def __init__(self, banco, url_base: str, token: str = "", sessao=None):
        self.banco = banco
        self.url_base = url_base.rstrip("/")
        self.sessao = sessao or requests.Session()
        self.sessao.headers.update({"User-Agent": "moto-monitor/1.0"})
        if token:
            self.sessao.headers["X-Subscription-Token"] = token

    def _get(self, caminho: str, dias_cache: float):
        chave = "fipe:" + caminho
        guardado = self.banco.cache_ler(chave, dias_cache)
        if guardado is not None:
            return guardado
        resp = self.sessao.get(f"{self.url_base}/{caminho}", timeout=20)
        resp.raise_for_status()
        dados = resp.json()
        self.banco.cache_gravar(chave, dados)
        return dados

    def marcas(self):
        return self._get("marcas", 30)

    def modelos_da_marca(self, marca_id):
        dados = self._get(f"marcas/{marca_id}/modelos", 30)
        return dados["modelos"] if isinstance(dados, dict) else dados

    def anos(self, marca_id, modelo_id):
        return self._get(f"marcas/{marca_id}/modelos/{modelo_id}/anos", 30)

    def valor(self, marca_id, modelo_id, ano_codigo):
        return self._get(f"marcas/{marca_id}/modelos/{modelo_id}/anos/{ano_codigo}", 7)

    # ------------------------------------------------------------------
    def candidatos(self, modelo: Modelo) -> list[tuple]:
        """(marca_id, modelo_id, nome) de todos os modelos FIPE que casam com o catálogo."""
        achados = []
        tokens = [normalizar(t) for t in modelo.fipe_tokens]
        excluir = [normalizar(t) for t in modelo.fipe_excluir]
        for marca in self.marcas():
            if normalizar(modelo.fipe_marca) not in normalizar(marca["nome"]):
                continue
            for m in self.modelos_da_marca(marca["codigo"]):
                nome = normalizar(m["nome"])
                palavras = nome.split()
                if all(t in palavras or t in nome.replace(" ", "") for t in tokens) \
                        and not any(e in nome for e in excluir):
                    achados.append((marca["codigo"], m["codigo"], m["nome"]))
        return achados

    def consultar(self, modelo: Modelo, ano: int | None, max_variantes: int = 4) -> tuple[float | None, str]:
        """Valor FIPE (mediana das variantes encontradas) e descrição de referência."""
        if not ano:
            return None, ""
        try:
            valores, nomes = [], []
            for marca_id, modelo_id, nome in self.candidatos(modelo):
                if len(valores) >= max_variantes:
                    break
                codigos = [a["codigo"] for a in self.anos(marca_id, modelo_id)
                           if str(a["codigo"]).startswith(f"{ano}-")]
                if not codigos:
                    continue
                dados = self.valor(marca_id, modelo_id, codigos[0])
                v = para_inteiro(dados.get("Valor"))
                if v:
                    valores.append(v)
                    nomes.append(f"{nome} {ano}: R$ {v:,}".replace(",", "."))
            if not valores:
                return None, ""
            return float(statistics.median(valores)), " | ".join(nomes)
        except Exception as erro:  # rede, limite da API etc.
            log.warning("FIPE indisponível para %s %s: %s", modelo.nome, ano, erro)
            return None, ""
