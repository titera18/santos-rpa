"""Linha de comando e montagem das dependências: é aqui que as camadas se conectam.

    python -m santos_rpa robo               execução completa
    python -m santos_rpa robo --sem-coleta  só refaz a análise e o dashboard, sem acessar a internet
    python -m santos_rpa robo --abrir       abre o dashboard ao terminar
    python -m santos_rpa painel             serve o dashboard em http://localhost:8765
"""
import argparse
import logging
import os
import sys
import webbrowser
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

from santos_rpa import configuracao as cfg

log = logging.getLogger("rpa")


def _configurar_log(arquivo: str, tamanho: int, copias: int):
    cfg.PASTA_LOGS.mkdir(exist_ok=True)
    if sys.stdout is None:  # no agendador roda sem janela (pythonw), e as bibliotecas ainda tentam escrever na saída
        sys.stdout = sys.stderr = open(os.devnull, "w", encoding="utf-8")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        handlers=[RotatingFileHandler(cfg.PASTA_LOGS / arquivo, maxBytes=tamanho, backupCount=copias, encoding="utf-8"),
                  logging.StreamHandler(sys.stdout)],
    )
    for ruidoso in ("urllib3", "httpx", "httpcore"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)
    for ruidoso in ("huggingface_hub", "transformers"):
        logging.getLogger(ruidoso).setLevel(logging.ERROR)


def _robo(args) -> int:
    from santos_rpa.aplicacao.executar_robo import executar_robo
    from santos_rpa.infraestrutura.coleta.fontes import criar_fontes
    from santos_rpa.infraestrutura.ia.classificador import ClassificadorComCache
    from santos_rpa.infraestrutura.ia.modelo_local import ModeloLocal
    from santos_rpa.infraestrutura.painel.publicador import publicar_painel
    from santos_rpa.infraestrutura.persistencia.repositorio_sqlite import RepositorioSqlite, conectar
    from santos_rpa.infraestrutura.persistencia.rotulos_csv import carregar_rotulos

    _configurar_log("rpa.log", 5_000_000, 2)
    cfg.PASTA_DADOS.mkdir(exist_ok=True)
    repo = RepositorioSqlite(conectar(cfg.CAMINHO_BANCO))
    try:
        codigo = executar_robo(
            repo=repo,
            fontes=None if args.sem_coleta else criar_fontes(),
            classificador=ClassificadorComCache(ModeloLocal(cfg.PASTA_MODELOS), repo),
            rotulados=carregar_rotulos(cfg.ROTULOS_DE_AVALIACAO),
            publicar_painel=lambda dados: publicar_painel(dados, cfg.CAMINHO_DASHBOARD),
            agora=datetime.now(timezone.utc),
        )
    finally:
        repo.fechar()
    if args.abrir:
        webbrowser.open(cfg.CAMINHO_DASHBOARD.as_uri())
    return codigo


def _painel(_args) -> int:
    from santos_rpa.interfaces.servidor_web import criar_servidor

    _configurar_log("servidor.log", 1_000_000, 1)
    try:
        servidor = criar_servidor(cfg.CAMINHO_DASHBOARD, cfg.HOST_PAINEL, cfg.PORTA_PAINEL)
    except OSError as e:
        log.error("Não foi possível usar a porta %d: %s", cfg.PORTA_PAINEL, e)
        return 1
    log.info("Dashboard em http://localhost:%d", cfg.PORTA_PAINEL)
    servidor.serve_forever()
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="santos_rpa", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    comandos = ap.add_subparsers(dest="comando", required=True)
    robo = comandos.add_parser("robo", help="coleta, analisa e gera o dashboard")
    robo.add_argument("--sem-coleta", action="store_true", help="não acessa a internet; só refaz análise e dashboard")
    robo.add_argument("--abrir", action="store_true", help="abre o dashboard ao terminar")
    robo.set_defaults(executar=_robo)
    comandos.add_parser("painel", help="serve o dashboard em localhost").set_defaults(executar=_painel)
    args = ap.parse_args(argv)
    return args.executar(args)
