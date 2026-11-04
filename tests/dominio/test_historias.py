import unittest
from datetime import datetime, timezone

from santos_rpa.dominio.historias import agrupar_historias
from santos_rpa.dominio.modelo import Noticia
from santos_rpa.dominio.tema import classificar_tema


def noticia(id_, titulo):
    return Noticia(id=id_, titulo=titulo, url=f"https://exemplo.com/{id_}", fonte="ge",
                   publicado_em=datetime(2026, 11, 1, tzinfo=timezone.utc), tema=classificar_tema(titulo, "").nome)


class Historias(unittest.TestCase):
    def test_historias_de_jogos_diferentes_nao_se_juntam(self):
        h = agrupar_historias([noticia(1, "Santos x Bahia: onde assistir ao vivo"),
                               noticia(2, "Santos x Palmeiras: onde assistir ao vivo"),
                               noticia(3, "Red Bull Bragantino x Santos: onde assistir"),
                               noticia(4, "Bragantino x Santos: onde assistir, horário")])
        self.assertNotEqual(h[1], h[2])
        self.assertEqual(h[3], h[4])
