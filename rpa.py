"""Robô de notícias do Santos FC: coleta, grava no SQLite, analisa e gera o dashboard.

Uso:
    python rpa.py               # execução completa
    python rpa.py --sem-coleta  # só recalcula a análise e o dashboard
    python rpa.py --abrir       # abre o dashboard no navegador ao terminar
"""
import argparse
import json
import logging
import os
import sys
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

import analise
import banco
import coletores
import relevancia

RAIZ = Path(__file__).resolve().parent
CAMINHO_BANCO = RAIZ / "santos_noticias.db"
CAMINHO_LOG = RAIZ / "logs" / "rpa.log"
MODELO_DASHBOARD = RAIZ / "dashboard_modelo.html"
CAMINHO_DASHBOARD = RAIZ / "dashboard.html"
IDADE_MAXIMA_DIAS = 90

log = logging.getLogger("rpa")


def configurar_log():
    CAMINHO_LOG.parent.mkdir(exist_ok=True)
    if sys.stdout is None:  # no agendador roda sem janela (pythonw), e as bibliotecas ainda tentam escrever na saída
        sys.stdout = sys.stderr = open(os.devnull, "w", encoding="utf-8")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        handlers=[RotatingFileHandler(CAMINHO_LOG, maxBytes=5_000_000, backupCount=2, encoding="utf-8"),
                  logging.StreamHandler(sys.stdout)],
    )
    for ruidoso in ("urllib3", "httpx", "httpcore", "huggingface_hub", "transformers"):
        logging.getLogger(ruidoso).setLevel(logging.ERROR if ruidoso in ("huggingface_hub", "transformers") else logging.WARNING)


def _executar_fonte(nome, tarefa):
    inicio = time.monotonic()
    try:
        itens = tarefa()
        return nome, itens, None, time.monotonic() - inicio
    except Exception as e:  # uma fonte fora do ar não pode derrubar o robô
        log.warning("Fonte %s falhou: %s", nome, e)
        return nome, [], f"{type(e).__name__}: {e}"[:300], time.monotonic() - inicio


def _gravar_itens(con, itens, agora):
    """Filtra e grava. Retorna (aceitos, novos)."""
    agora_iso = agora.isoformat()
    aceitos = novos = 0
    limite = agora - timedelta(days=IDADE_MAXIMA_DIAS)
    for item in itens:
        publicado = item.publicado_em or agora
        origem = item.data_origem if item.publicado_em else "coleta"
        publicado = min(publicado.astimezone(timezone.utc), agora)  # datas futuras viram "agora"
        if publicado < limite:
            banco.registrar_descarte(con, item.url, item.titulo, item.fonte, "mais de 90 dias", agora_iso)
            continue
        foco, motivo = relevancia.avaliar_foco(item.titulo, item.resumo, item.url, item.fonte)
        chave = relevancia.chave(item.titulo, item.fonte)
        # Em nova execução a matéria não é reaberta e vem sem resumo: o que já foi aceito continua aceito.
        if foco == 0 and con.execute("SELECT 1 FROM noticias WHERE chave = ?", (chave,)).fetchone():
            foco = 1
        if foco == 0:
            banco.registrar_descarte(con, item.url, item.titulo, item.fonte, motivo, agora_iso)
            continue
        aceitos += 1
        novos += banco.inserir_noticia(con, {
            "chave": chave,
            "titulo": item.titulo, "resumo": item.resumo, "url": item.url, "fonte": item.fonte,
            "coletor": item.coletor, "publicado_em": publicado.isoformat(), "data_origem": origem,
            "agora": agora_iso, "foco": foco,
        })
    return aceitos, novos


def coletar(con, agora) -> tuple[int, int]:
    """Roda todas as fontes. Retorna (novas notícias, fontes com erro)."""
    exec_id = con.execute("INSERT INTO execucoes (inicio) VALUES (?)", (agora.isoformat(),)).lastrowid
    con.commit()

    conhecidas = {r[0] for r in con.execute("SELECT chave FROM noticias")}
    conhecidas |= {r[0] for r in con.execute("SELECT url FROM descartes")}

    def ja_conhecida(item):
        return item.url in conhecidas or relevancia.chave(item.titulo, item.fonte) in conhecidas

    cliente = coletores.Cliente()
    tarefas = coletores.tarefas_de_coleta(cliente, ja_conhecida)
    with ThreadPoolExecutor(max_workers=len(tarefas)) as pool:
        resultados = list(pool.map(lambda t: _executar_fonte(*t), tarefas))

    # Fontes diretas primeiro: o link do veículo tem prioridade sobre o do Google News.
    resultados.sort(key=lambda r: r[0] == "Google News")
    total_novas = erros = 0
    for nome, itens, erro, segundos in resultados:
        aceitos, novos = _gravar_itens(con, itens, agora)
        status = "erro" if erro else ("ok" if aceitos else "vazio")
        erros += bool(erro)
        total_novas += novos
        con.execute(
            "INSERT INTO execucao_fontes (execucao_id, fonte, status, brutos, aceitos, novos, erro, segundos) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (exec_id, nome, status, len(itens), aceitos, novos, erro, round(segundos, 1)),
        )
        log.info("%-22s %-5s brutos=%-4d aceitos=%-4d novos=%-4d %.1fs", nome, status, len(itens), aceitos, novos, segundos)

    situacao = "falhou" if erros == len(tarefas) else ("parcial" if erros else "ok")
    con.execute("UPDATE execucoes SET fim=?, novas=?, status=? WHERE id=?",
                (datetime.now(timezone.utc).isoformat(), total_novas, situacao, exec_id))
    con.commit()
    return total_novas, erros if erros < len(tarefas) else -1


def gerar_dashboard(dados: dict):
    # "<" escapado para que títulos vindos da web não fechem a tag <script>.
    json_seguro = json.dumps(dados, ensure_ascii=False).replace("<", "\\u003c")
    html = MODELO_DASHBOARD.read_text(encoding="utf-8").replace("/*__DADOS__*/{}", json_seguro)
    # Troca o arquivo de uma vez, para o servidor nunca entregar uma página pela metade.
    temporario = CAMINHO_DASHBOARD.with_suffix(".html.tmp")
    temporario.write_text(html, encoding="utf-8")
    for tentativa in range(5):
        try:
            os.replace(temporario, CAMINHO_DASHBOARD)
            return
        except PermissionError:  # no Windows, falha se o servidor estiver lendo o arquivo naquele instante
            if tentativa == 4:
                raise
            time.sleep(1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sem-coleta", action="store_true", help="não acessa a internet; só refaz análise e dashboard")
    ap.add_argument("--abrir", action="store_true", help="abre o dashboard ao terminar")
    args = ap.parse_args()

    configurar_log()
    agora = datetime.now(timezone.utc)
    con = banco.conectar(CAMINHO_BANCO)
    codigo = 0
    try:
        if not args.sem_coleta:
            novas, erros = coletar(con, agora)
            log.info("Coleta concluída: %d notícias novas, %s", novas,
                     "todas as fontes falharam" if erros < 0 else f"{erros} fontes com erro")
            if erros < 0:
                codigo = 1
        total = relevancia.recalcular(con, agora)
        con.commit()
        dados = analise.montar_dados(con, agora)
        con.commit()  # a avaliação pode ter guardado novas previsões do modelo
        gerar_dashboard(dados)
        log.info("Base com %d notícias. Dashboard: %s", total, CAMINHO_DASHBOARD)
        for frase in dados["conclusoes"]:
            log.info("  - %s", frase)
    finally:
        con.close()
    if args.abrir:
        webbrowser.open(CAMINHO_DASHBOARD.as_uri())
    return codigo


if __name__ == "__main__":
    sys.exit(main())
