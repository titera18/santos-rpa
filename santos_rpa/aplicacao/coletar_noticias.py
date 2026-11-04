"""Caso de uso: buscar notícias em todas as fontes e gravar as que tratam do clube."""
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from santos_rpa.dominio.foco import avaliar_foco
from santos_rpa.dominio.modelo import ItemColetado, ResultadoDaFonte
from santos_rpa.dominio.portas import FonteDeNoticias, RepositorioDeNoticias
from santos_rpa.dominio.texto import chave

IDADE_MAXIMA_DIAS = 90

log = logging.getLogger("rpa")


def _buscar(fonte: FonteDeNoticias, ja_conhecida):
    inicio = time.monotonic()
    try:
        return fonte, fonte.coletar(ja_conhecida), None, time.monotonic() - inicio
    except Exception as e:  # uma fonte fora do ar não pode derrubar o robô
        log.warning("Fonte %s falhou: %s", fonte.nome, e)
        return fonte, [], f"{type(e).__name__}: {e}"[:300], time.monotonic() - inicio


def _gravar_itens(repo: RepositorioDeNoticias, itens: list[ItemColetado], agora: datetime) -> tuple[int, int]:
    """Filtra e grava. Retorna (aceitos, novos)."""
    aceitos = novos = 0
    limite = agora - timedelta(days=IDADE_MAXIMA_DIAS)
    for item in itens:
        publicado = item.publicado_em or agora
        origem = item.data_origem if item.publicado_em else "coleta"
        publicado = min(publicado.astimezone(timezone.utc), agora)  # datas futuras viram "agora"
        if publicado < limite:
            repo.registrar_descarte(item.url, item.titulo, item.fonte, "mais de 90 dias", agora)
            continue
        foco, motivo = avaliar_foco(item.titulo, item.resumo, item.url, item.fonte)
        identidade = chave(item.titulo, item.fonte)
        # Em nova execução a matéria não é reaberta e vem sem resumo: o que já foi aceito continua aceito.
        if foco == 0 and repo.existe(identidade):
            foco = 1
        if foco == 0:
            repo.registrar_descarte(item.url, item.titulo, item.fonte, motivo, agora)
            continue
        aceitos += 1
        novos += repo.inserir(item, identidade, publicado, origem, foco, agora)
    return aceitos, novos


def coletar_noticias(repo: RepositorioDeNoticias, fontes: list[FonteDeNoticias], agora: datetime) -> tuple[int, int]:
    """Retorna (notícias novas, fontes com erro). O número de erros é -1 se todas as fontes falharem."""
    execucao = repo.iniciar_execucao(agora)
    repo.confirmar()

    conhecidas = repo.identificadores_conhecidos()

    def ja_conhecida(item: ItemColetado) -> bool:
        return item.url in conhecidas or chave(item.titulo, item.fonte) in conhecidas

    with ThreadPoolExecutor(max_workers=len(fontes)) as pool:
        resultados = list(pool.map(lambda f: _buscar(f, ja_conhecida), fontes))

    resultados.sort(key=lambda r: r[0].agregador)  # fontes diretas primeiro
    total_novas = erros = 0
    for fonte, itens, erro, segundos in resultados:
        aceitos, novos = _gravar_itens(repo, itens, agora)
        status = "erro" if erro else ("ok" if aceitos else "vazio")
        erros += bool(erro)
        total_novas += novos
        repo.registrar_fonte(execucao, ResultadoDaFonte(fonte.nome, status, len(itens), aceitos, novos, erro,
                                                        round(segundos, 1)))
        log.info("%-22s %-5s brutos=%-4d aceitos=%-4d novos=%-4d %.1fs", fonte.nome, status, len(itens), aceitos, novos, segundos)

    situacao = "falhou" if erros == len(fontes) else ("parcial" if erros else "ok")
    repo.concluir_execucao(execucao, total_novas, situacao)
    repo.confirmar()
    return total_novas, erros if erros < len(fontes) else -1
