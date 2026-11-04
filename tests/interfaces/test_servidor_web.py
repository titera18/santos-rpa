import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from santos_rpa.interfaces.servidor_web import criar_servidor


class ServidorDoPainel(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.dashboard = Path(self.pasta.name) / "dashboard.html"
        self.dashboard.write_text("<h1>Santos</h1>", encoding="utf-8")
        (Path(self.pasta.name) / "santos_noticias.db").write_text("segredo", encoding="utf-8")
        self.servidor = criar_servidor(self.dashboard, "127.0.0.1", 0)
        self.base = f"http://127.0.0.1:{self.servidor.server_address[1]}"
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()

    def tearDown(self):
        self.servidor.shutdown()
        self.servidor.server_close()
        self.pasta.cleanup()

    def codigo(self, caminho):
        try:
            with urllib.request.urlopen(self.base + caminho) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    def test_entrega_o_dashboard_sem_cache(self):
        with urllib.request.urlopen(self.base + "/") as r:
            self.assertEqual(r.read().decode(), "<h1>Santos</h1>")
            self.assertEqual(r.headers["Cache-Control"], "no-store")

    def test_nao_entrega_outros_arquivos(self):
        for caminho in ("/santos_noticias.db", "/../santos_noticias.db", "/%2e%2e/santos_noticias.db"):
            self.assertEqual(self.codigo(caminho), 404, caminho)

    def test_sem_dashboard_responde_503(self):
        self.dashboard.unlink()
        self.assertEqual(self.codigo("/"), 503)

    def test_so_escuta_neste_computador(self):
        self.assertEqual(self.servidor.server_address[0], "127.0.0.1")
