import unittest
from unittest import mock

from santos_rpa.infraestrutura.ia.classificador import ClassificadorComCache
from santos_rpa.infraestrutura.persistencia.repositorio_sqlite import RepositorioSqlite, conectar


def modelo_falso(**kwargs):
    modelo = mock.Mock(**kwargs)
    modelo.nome = "falso"
    return modelo


class Classificador(unittest.TestCase):
    def setUp(self):
        self.repo = RepositorioSqlite(conectar(":memory:"))
        self.addCleanup(self.repo.fechar)

    def test_falha_do_modelo_nao_derruba_e_nao_grava(self):
        classificador = ClassificadorComCache(modelo_falso(prever=mock.Mock(side_effect=RuntimeError("sem modelo"))), self.repo)
        with self.assertLogs("rpa.ia", "WARNING"):
            self.assertEqual(classificador.probabilidades(["Santos treina"]), {})
        self.assertEqual(self.repo.previsoes_guardadas("falso"), {})
        self.assertTrue(classificador.indisponivel)

    def test_previsao_guardada_nao_recalcula(self):
        p = {"negativo": 0.1, "neutro": 0.1, "positivo": 0.8}
        modelo = modelo_falso(prever=mock.Mock(return_value={"Santos treina": p}))
        classificador = ClassificadorComCache(modelo, self.repo)
        classificador.probabilidades(["Santos treina"])
        self.assertEqual(classificador.probabilidades(["Santos treina"]), {"Santos treina": p})
        modelo.prever.assert_called_once()
        self.assertFalse(classificador.indisponivel)
