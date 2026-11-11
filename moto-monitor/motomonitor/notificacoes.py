"""Envio de alertas: notificação na área de trabalho (plyer) e Telegram (opcional).

O próprio site também avisa: a página consulta /api/alertas a cada minuto e mostra
notificação do navegador + som quando chega alerta novo.
"""
import logging

import requests

from .textos import moeda

log = logging.getLogger(__name__)


def mensagem(anuncio: dict, motivos: list[str]) -> str:
    partes = [f"{anuncio['modelo_nome']} {anuncio.get('ano') or ''}".strip(),
              f"{moeda(anuncio['preco'])} — {anuncio.get('cidade') or '?'}",
              " / ".join(motivos)]
    return "\n".join(partes)


def enviar(config: dict, anuncio: dict, motivos: list[str]):
    cfg = config.get("notificacoes", {})
    texto = mensagem(anuncio, motivos)
    if cfg.get("desktop", True):
        try:
            from plyer import notification
            notification.notify(title="🏍️ Moto em oferta!", message=texto[:250],
                                app_name="Moto Monitor", timeout=15)
        except Exception as erro:
            log.debug("Notificação desktop indisponível: %s", erro)
    tg = cfg.get("telegram", {})
    if tg.get("ativo") and tg.get("token") and tg.get("chat_id"):
        try:
            requests.post(f"https://api.telegram.org/bot{tg['token']}/sendMessage",
                          json={"chat_id": tg["chat_id"], "text": f"🏍️ {texto}\n{anuncio['url']}"},
                          timeout=15)
        except Exception as erro:
            log.warning("Falha no Telegram: %s", erro)
