"""Serve o dashboard em http://localhost:8765, acessível só neste computador.

Entrega apenas o dashboard.html: o banco, os logs e o código não ficam disponíveis pelo servidor.
"""
import logging
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from logging.handlers import RotatingFileHandler
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
CAMINHO_DASHBOARD = RAIZ / "dashboard.html"
CAMINHO_LOG = RAIZ / "logs" / "servidor.log"
HOST = "127.0.0.1"
PORTA = 8765

log = logging.getLogger("servidor")


class Dashboard(BaseHTTPRequestHandler):
    def _responder(self, enviar_corpo: bool):
        if self.path.split("?")[0] not in ("/", "/dashboard.html"):
            self.send_error(404)
            return
        try:
            corpo = CAMINHO_DASHBOARD.read_bytes()  # lido a cada acesso: sempre mostra a última execução do robô
        except OSError:
            self.send_error(503, "Dashboard ainda não gerado")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if enviar_corpo:
            self.wfile.write(corpo)

    def do_GET(self):
        self._responder(True)

    def do_HEAD(self):
        self._responder(False)

    def log_message(self, formato, *args):
        log.debug(formato, *args)


def main() -> int:
    CAMINHO_LOG.parent.mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s",
                        handlers=[RotatingFileHandler(CAMINHO_LOG, maxBytes=1_000_000, backupCount=1, encoding="utf-8")])
    try:
        servidor = ThreadingHTTPServer((HOST, PORTA), Dashboard)
    except OSError as e:
        log.error("Não foi possível usar a porta %d: %s", PORTA, e)
        return 1
    log.info("Dashboard em http://localhost:%d", PORTA)
    servidor.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
