"""Gera o dashboard em um único arquivo HTML, que funciona sem internet."""
import json
import os
import time
from pathlib import Path

MODELO_HTML = Path(__file__).with_name("modelo.html")


def publicar_painel(dados: dict, destino: Path) -> Path:
    # "<" escapado para que títulos vindos da web não fechem a tag <script>.
    json_seguro = json.dumps(dados, ensure_ascii=False).replace("<", "\\u003c")
    html = MODELO_HTML.read_text(encoding="utf-8").replace("/*__DADOS__*/{}", json_seguro)
    # Troca o arquivo de uma vez, para o servidor nunca entregar uma página pela metade.
    temporario = destino.with_suffix(".html.tmp")
    temporario.write_text(html, encoding="utf-8")
    for tentativa in range(5):
        try:
            os.replace(temporario, destino)
            return destino
        except PermissionError:  # no Windows, falha se o servidor estiver lendo o arquivo naquele instante
            if tentativa == 4:
                raise
            time.sleep(1)
    return destino
