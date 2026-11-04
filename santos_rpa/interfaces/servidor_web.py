"""Serve o dashboard em http://localhost:8765, acessível só neste computador.

Entrega apenas o dashboard: o banco, os logs e o código não ficam disponíveis pelo servidor.
"""
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

log = logging.getLogger("servidor")


def criar_servidor(dashboard: Path, host: str, porta: int) -> ThreadingHTTPServer:
    class Painel(BaseHTTPRequestHandler):
        def _responder(self, enviar_corpo: bool):
            if self.path.split("?")[0] not in ("/", "/dashboard.html"):
                self.send_error(404)
                return
            try:
                corpo = dashboard.read_bytes()  # lido a cada acesso: sempre mostra a última execução do robô
            except OSError:
                self.send_error(503, "Dashboard ainda nao gerado")
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

    return ThreadingHTTPServer((host, porta), Painel)
