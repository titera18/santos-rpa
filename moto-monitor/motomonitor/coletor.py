"""Uma rodada de coleta: busca cada modelo em cada fonte, consulta a FIPE, aplica as
regras, grava no banco e dispara alertas."""
import json
import logging
import threading
import time

from . import notificacoes, regras
from .db import Banco, agora
from .fipe import Fipe
from .fontes import criar_fontes
from .modelos import catalogo, identificar
from .textos import normalizar

log = logging.getLogger(__name__)


class Coletor:
    def __init__(self, config: dict, banco: Banco, fontes=None, fipe=None, notificar=None):
        self.config = config
        self.banco = banco
        self.fontes = fontes if fontes is not None else criar_fontes(config)
        self.fipe = fipe or Fipe(banco, config["fipe"]["url_base"], config["fipe"].get("token", ""))
        self.notificar = notificar or (lambda a, m: notificacoes.enviar(config, a, m))
        self.modelos = catalogo(config)
        self.cidades = {normalizar(c) for c in config.get("cidades", [])}
        self.trava = threading.Lock()
        self.status = {"rodando": False, "progresso": "", "ultima": None}

    def cidade_ok(self, cidade: str) -> bool:
        if not self.cidades or not cidade:
            return True  # sem informação: mantém (a busca já é regional)
        return normalizar(cidade) in self.cidades

    def processar(self, bruto) -> tuple[bool, bool]:
        """Grava um anúncio. Devolve (novo, alertou)."""
        r = self.config["regras"]
        modelo = identificar(bruto.titulo, self.modelos)
        if not modelo or not bruto.preco:
            return False, False
        if not r.get("preco_minimo_plausivel", 0) <= bruto.preco <= r["preco_maximo_coleta"]:
            return False, False
        if not self.cidade_ok(bruto.cidade):
            return False, False
        fipe, ref = self.fipe.consultar(modelo, bruto.ano)
        motivos = regras.avaliar(bruto.preco, fipe, r)
        dados = {
            "id": bruto.id, "fonte": bruto.fonte, "url": bruto.url, "titulo": bruto.titulo,
            "imagem": bruto.imagem, "preco": bruto.preco, "ano": bruto.ano, "km": bruto.km,
            "cidade": bruto.cidade, "modelo_chave": modelo.chave, "modelo_nome": modelo.nome,
            "estilo": modelo.estilo, "fipe": fipe, "fipe_ref": ref,
            "desconto": regras.desconto(bruto.preco, fipe),
            "motivos": json.dumps(motivos, ensure_ascii=False),
            "alerta": int(bool(motivos)),
        }
        novo, _ = self.banco.salvar_anuncio(dados)
        alertou = False
        if motivos:
            menor_alertado = self.banco.ja_alertado(bruto.id)
            # alerta na 1ª vez e de novo se o preço cair ainda mais
            if menor_alertado is None or bruto.preco < menor_alertado:
                self.banco.registrar_alerta(bruto.id, bruto.preco, motivos)
                self.notificar({**dados, "motivos": motivos}, motivos)
                alertou = True
        return novo, alertou

    def rodar(self) -> dict:
        if not self.trava.acquire(blocking=False):
            return {"ok": False, "erro": "Coleta já em andamento"}
        inicio = agora()
        vistos = novos = alertas = 0
        erros = []
        self.status.update(rodando=True)
        try:
            buscas = {}
            for m in self.modelos:  # termos repetidos só são buscados uma vez
                buscas.setdefault(m.busca, m)
            total = len(buscas) * len(self.fontes)
            passo = 0
            for fonte in self.fontes:
                for termo in buscas:
                    passo += 1
                    self.status["progresso"] = f"{fonte.nome}: {termo} ({passo}/{total})"
                    try:
                        achados = fonte.buscar(termo)
                    except Exception as erro:
                        msg = f"{fonte.nome} '{termo}': {erro}"
                        log.warning(msg)
                        erros.append(msg)
                        continue
                    for bruto in achados:
                        vistos += 1
                        try:
                            n, a = self.processar(bruto)
                            novos += n
                            alertas += a
                        except Exception as erro:
                            log.exception("Erro processando %s", bruto.url)
                            erros.append(f"{bruto.url}: {erro}")
        finally:
            fim = agora()
            self.banco.registrar_coleta(inicio, fim, vistos, novos, alertas, erros[-30:])
            self.status.update(rodando=False, progresso="", ultima=fim)
            self.trava.release()
        log.info("Coleta: %d vistos, %d novos, %d alertas, %d erros", vistos, novos, alertas, len(erros))
        return {"ok": True, "vistos": vistos, "novos": novos, "alertas": alertas, "erros": erros}

    def em_segundo_plano(self):
        threading.Thread(target=self.rodar, daemon=True).start()

    def agendar(self):
        """Roda já e depois a cada `intervalo_minutos`."""
        intervalo = max(5, int(self.config.get("intervalo_minutos", 30))) * 60

        def laco():
            while True:
                try:
                    self.rodar()
                except Exception:
                    log.exception("Falha na coleta agendada")
                time.sleep(intervalo)

        threading.Thread(target=laco, daemon=True, name="agendador").start()
