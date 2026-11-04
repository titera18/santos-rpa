"""Caso de uso principal: coleta, reclassifica, analisa e publica o dashboard."""
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from santos_rpa.aplicacao.coletar_noticias import coletar_noticias
from santos_rpa.aplicacao.montar_painel import montar_painel
from santos_rpa.aplicacao.reclassificar_base import reclassificar_base
from santos_rpa.dominio.portas import ClassificadorDeSentimento, FonteDeNoticias, RepositorioDeNoticias

log = logging.getLogger("rpa")


def executar_robo(repo: RepositorioDeNoticias, fontes: list[FonteDeNoticias] | None,
                  classificador: ClassificadorDeSentimento, rotulados: list[tuple[str, str]],
                  publicar_painel: Callable[[dict], Path], agora: datetime) -> int:
    """Retorna o código de saída: 1 se todas as fontes falharem. Sem fontes, não acessa a internet."""
    codigo = 0
    if fontes is not None:
        novas, erros = coletar_noticias(repo, fontes, agora)
        log.info("Coleta concluída: %d notícias novas, %s", novas,
                 "todas as fontes falharam" if erros < 0 else f"{erros} fontes com erro")
        if erros < 0:
            codigo = 1
    total = reclassificar_base(repo, classificador, agora)
    repo.confirmar()
    dados = montar_painel(repo, classificador, rotulados, agora)
    repo.confirmar()  # a avaliação pode ter guardado novas previsões do modelo
    destino = publicar_painel(dados)
    log.info("Base com %d notícias. Dashboard: %s", total, destino)
    for frase in dados["conclusoes"]:
        log.info("  - %s", frase)
    return codigo
