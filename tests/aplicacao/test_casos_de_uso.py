"""Casos de uso de ponta a ponta, com banco em memória e fontes falsas: nada acessa a internet."""
import unittest
from datetime import datetime, timedelta, timezone

from santos_rpa import configuracao as cfg
from santos_rpa.aplicacao.avaliar_sentimento import avaliar_sentimento
from santos_rpa.aplicacao.coletar_noticias import coletar_noticias
from santos_rpa.aplicacao.executar_robo import executar_robo
from santos_rpa.dominio.modelo import ItemColetado
from santos_rpa.infraestrutura.persistencia.repositorio_sqlite import RepositorioSqlite, conectar
from santos_rpa.infraestrutura.persistencia.rotulos_csv import carregar_rotulos

AGORA = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)


def item(titulo, fonte="ge", url=None, dias=0, coletor="rss"):
    return ItemColetado(titulo, url or f"https://exemplo.com/{abs(hash(titulo + fonte))}", fonte, coletor, "",
                        AGORA - timedelta(days=dias), "feed")


class FonteFalsa:
    def __init__(self, nome, itens=(), erro=None, agregador=False):
        self.nome, self.itens, self.erro, self.agregador = nome, list(itens), erro, agregador

    def coletar(self, ja_conhecida):
        if self.erro:
            raise self.erro
        return self.itens


class SemModelo:
    indisponivel = False

    def probabilidades(self, titulos):
        return {}


class ComBanco(unittest.TestCase):
    def repositorio(self):
        repo = RepositorioSqlite(conectar(":memory:"))
        self.addCleanup(repo.fechar)
        return repo


class Coleta(ComBanco):
    def test_grava_o_que_e_do_clube_e_descarta_o_resto(self):
        repo = self.repositorio()
        fonte = FonteFalsa("ge", [item("Santos vence o Remo no Mangueirão"),
                                  item("Porto de Santos bate recorde de exportação de soja"),
                                  item("São Paulo x Corinthians: clássico será na Vila Belmiro")])
        self.assertEqual(coletar_noticias(repo, [fonte], AGORA), (1, 0))
        self.assertEqual(repo.contar_descartes(), 2)

    def test_mesma_noticia_nao_duplica(self):
        repo = self.repositorio()
        fonte = FonteFalsa("ge", [item("Santos vence o Remo no Mangueirão")])
        coletar_noticias(repo, [fonte], AGORA)
        self.assertEqual(coletar_noticias(repo, [fonte], AGORA)[0], 0)
        self.assertEqual(len(repo.listar_para_reclassificar()), 1)

    def test_noticia_antiga_e_descartada(self):
        repo = self.repositorio()
        coletar_noticias(repo, [FonteFalsa("ge", [item("Santos vence o Remo no Mangueirão", dias=91)])], AGORA)
        self.assertEqual(repo.listar_para_reclassificar(), [])

    def test_uma_fonte_com_erro_nao_derruba_as_outras(self):
        repo = self.repositorio()
        fontes = [FonteFalsa("ruim", erro=RuntimeError("fora do ar")),
                  FonteFalsa("ge", [item("Santos vence o Remo no Mangueirão")])]
        self.assertEqual(coletar_noticias(repo, fontes, AGORA), (1, 1))
        status = {f["fonte"]: f["status"] for f in repo.saude_das_fontes()}
        self.assertEqual(status, {"ruim": "erro", "ge": "ok"})

    def test_todas_as_fontes_com_erro(self):
        self.assertEqual(coletar_noticias(self.repositorio(), [FonteFalsa("ruim", erro=RuntimeError("x"))], AGORA), (0, -1))

    def test_link_direto_substitui_o_do_agregador(self):
        repo = self.repositorio()
        titulo = "Santos vence o Remo no Mangueirão"
        agregador = FonteFalsa("Google News", [item(titulo, url="https://news.google.com/x", coletor="google_news")], agregador=True)
        direta = FonteFalsa("ge", [item(titulo, url="https://ge.globo.com/x")])
        coletar_noticias(repo, [agregador], AGORA)
        coletar_noticias(repo, [direta], AGORA)
        self.assertEqual(repo.listar_para_reclassificar()[0].url, "https://ge.globo.com/x")


class Robo(ComBanco):
    def executar(self, repo, fontes):
        publicados = []

        def publicar(dados):
            publicados.append(dados)
            return "painel"
        codigo = executar_robo(repo, fontes, SemModelo(), [], publicar, AGORA)
        return codigo, publicados[0]

    def test_execucao_completa_classifica_e_publica(self):
        repo = self.repositorio()
        fontes = [FonteFalsa("ge", [item("Palmeiras vence o Santos com gol de Vitor Roque")]),
                  FonteFalsa("Lance", [item("Palmeiras vence o Santos com gol de Vitor Roque", fonte="Lance")])]
        codigo, dados = self.executar(repo, fontes)
        self.assertEqual(codigo, 0)
        self.assertEqual(len(dados["noticias"]), 2)
        primeira = dados["noticias"][0]
        self.assertEqual(primeira["s"], "negativo")
        self.assertEqual(primeira["n"], 2)  # dois veículos na mesma história
        self.assertEqual(primeira["c"][2], 8.3)  # repercussão de 2 veículos

    def test_sem_fontes_nao_coleta(self):
        repo = self.repositorio()
        _, dados = self.executar(repo, None)
        self.assertEqual(dados["execucoes"], 0)

    def test_regra_nova_tira_noticia_antiga_da_base(self):
        repo = self.repositorio()
        repo.inserir(item("Porto de Santos bate recorde de exportação de soja"), "c1", AGORA, "feed", 25, AGORA)
        _, dados = self.executar(repo, None)
        self.assertEqual(dados["noticias"], [])
        self.assertEqual(dados["descartes"], 1)

    def test_codigo_de_erro_quando_todas_as_fontes_falham(self):
        codigo, _ = self.executar(self.repositorio(), [FonteFalsa("ruim", erro=RuntimeError("x"))])
        self.assertEqual(codigo, 1)


class Avaliacao(unittest.TestCase):
    def test_acerto_nao_piora_nos_titulos_rotulados(self):
        # Referência medida às cegas em 219 títulos: 74%. Se cair, alguma regra nova piorou o resultado.
        medidas = avaliar_sentimento(carregar_rotulos(cfg.ROTULOS_DE_AVALIACAO))
        self.assertEqual(medidas["total"], 219)
        self.assertGreaterEqual(medidas["acerto"], 74)
        self.assertFalse(medidas["com_ia"])

    def test_sem_rotulos_nao_ha_medida(self):
        self.assertIsNone(avaliar_sentimento([]))
