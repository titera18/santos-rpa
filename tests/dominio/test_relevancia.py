import unittest

from santos_rpa.dominio.relevancia import pontos_recencia, pontos_repercussao


class Pontos(unittest.TestCase):
    def test_repercussao(self):
        self.assertEqual(pontos_repercussao(1), 0)
        self.assertEqual(pontos_repercussao(8), 25)
        self.assertEqual(pontos_repercussao(50), 25)

    def test_recencia_cai_pela_metade_em_3_dias(self):
        self.assertEqual(pontos_recencia(0), 20)
        self.assertAlmostEqual(pontos_recencia(3), 10)
