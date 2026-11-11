"""Uso:
    python -m motomonitor            # sobe o site e coleta a cada N minutos
    python -m motomonitor --uma-vez  # faz uma coleta só e sai (bom p/ Agendador de Tarefas)
    python -m motomonitor --sem-coleta  # só o site, sem buscar
"""
import argparse
import logging
import webbrowser

from .coletor import Coletor
from .config import carregar
from .db import Banco


def main():
    p = argparse.ArgumentParser(prog="motomonitor")
    p.add_argument("--uma-vez", action="store_true", help="faz uma coleta e sai")
    p.add_argument("--sem-coleta", action="store_true", help="só abre o site")
    p.add_argument("--nao-abrir", action="store_true", help="não abre o navegador")
    p.add_argument("--config", help="caminho do config.json")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    config = carregar(args.config)
    banco = Banco(config["banco"])
    coletor = Coletor(config, banco)

    if args.uma_vez:
        print(coletor.rodar())
        return

    from .web import criar_app
    app = criar_app(config, banco, coletor)
    if not args.sem_coleta:
        coletor.agendar()
    url = f"http://localhost:{config['porta']}"
    print(f"\n  Moto Monitor rodando em {url}  (Ctrl+C para sair)\n")
    if not args.nao_abrir:
        webbrowser.open(url)
    app.run(host="127.0.0.1", port=config["porta"], debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
