"""HTTP educado: se identifica, respeita o robots.txt e espera entre acessos ao mesmo domínio."""
import threading
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = "Mozilla/5.0 (compatible; SantosNewsRPA/1.0; uso pessoal)"
ESPERA_POR_DOMINIO = 1.0   # segundos entre requisições ao mesmo domínio


class BloqueadoPorRobots(Exception):
    pass


class Cliente:
    """HTTP educado: robots.txt em cache, espera por domínio e novas tentativas."""

    def __init__(self):
        self.sessao = requests.Session()
        self.sessao.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9"})
        retry = Retry(total=2, backoff_factor=1.5, status_forcelist=[429, 500, 502, 503, 504])
        self.sessao.mount("https://", HTTPAdapter(max_retries=retry))
        self._robots: dict[str, RobotFileParser | None] = {}
        self._ultimo: dict[str, float] = {}
        self._trava = threading.Lock()

    def _permitido(self, url: str) -> bool:
        p = urlparse(url)
        base = f"{p.scheme}://{p.netloc}"
        with self._trava:
            conhecido = base in self._robots
            robo = self._robots.get(base)
        if not conhecido:
            robo = None
            try:
                r = self.sessao.get(f"{base}/robots.txt", timeout=10)
                if r.status_code == 200:
                    robo = RobotFileParser()
                    robo.parse(r.text.splitlines())
            except requests.RequestException:
                pass  # sem robots.txt acessível: segue, mantendo a espera por domínio
            with self._trava:
                self._robots[base] = robo
        return robo is None or robo.can_fetch(USER_AGENT, url)

    def _aguardar_vez(self, dominio: str):
        with self._trava:
            agora = time.monotonic()
            livre = max(agora, self._ultimo.get(dominio, 0) + ESPERA_POR_DOMINIO)
            self._ultimo[dominio] = livre
        if livre > agora:
            time.sleep(livre - agora)

    def get(self, url: str, ignorar_robots: bool = False) -> requests.Response:
        if not ignorar_robots and not self._permitido(url):
            raise BloqueadoPorRobots(url)
        self._aguardar_vez(urlparse(url).netloc)
        r = self.sessao.get(url, timeout=20)
        r.raise_for_status()
        return r
