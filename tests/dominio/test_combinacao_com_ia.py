import unittest

from santos_rpa.dominio.sentimento import combinar


class CombinacaoComIA(unittest.TestCase):
    def test_regras_decidem_primeiro(self):
        probs = {"negativo": 0.01, "neutro": 0.01, "positivo": 0.98}
        self.assertEqual(combinar("negativo", -0.75, probs), ("negativo", -0.75, "regras"))

    def test_modelo_decide_neutro_com_confianca(self):
        self.assertEqual(combinar("neutro", 0.0, {"negativo": 0.1, "neutro": 0.1, "positivo": 0.8}), ("positivo", 0.4, "ia"))
        self.assertEqual(combinar("neutro", 0.0, {"negativo": 0.8, "neutro": 0.1, "positivo": 0.1}), ("negativo", -0.4, "ia"))

    def test_baixa_confianca_ou_neutro_mantem_regras(self):
        self.assertEqual(combinar("neutro", 0.0, {"negativo": 0.2, "neutro": 0.2, "positivo": 0.6})[2], "regras")
        self.assertEqual(combinar("neutro", 0.0, {"negativo": 0.05, "neutro": 0.9, "positivo": 0.05})[2], "regras")

    def test_sem_previsao_mantem_regras(self):
        self.assertEqual(combinar("neutro", 0.0, None), ("neutro", 0.0, "regras"))
