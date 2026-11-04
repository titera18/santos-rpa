import unittest

from santos_rpa.dominio.foco import avaliar_foco
from santos_rpa.dominio.nomes import extrair_nomes
from santos_rpa.dominio.sentimento import analisar_sentimento
from santos_rpa.dominio.tema import classificar_tema


class Classificacao(unittest.TestCase):
    def test_servico_vence_jogo(self):
        self.assertEqual(classificar_tema("Bragantino x Santos: onde assistir", "")[0], "Serviço de jogo")

    def test_arbitragem_vence_jogo(self):
        self.assertEqual(classificar_tema("Santos reclama da arbitragem contra o Bragantino", "")[0], "Arbitragem")

    def test_jogo_na_vila_e_jogo_mas_gramado_e_estrutura(self):
        self.assertEqual(classificar_tema("Santos e Palmeiras empatam na Vila Belmiro", "")[0], "Jogo e resultado")
        self.assertEqual(classificar_tema("Abel detona gramado da Vila Belmiro no clássico", "")[0], "Estádio e estrutura")

    def test_sentimento(self):
        self.assertEqual(analisar_sentimento("Santos vence o Remo")[0], "positivo")
        self.assertEqual(analisar_sentimento("Palmeiras vence o Santos")[0], "negativo")
        self.assertEqual(analisar_sentimento("Rodinei assume erro por gol contra")[0], "negativo")
        self.assertEqual(analisar_sentimento("Santos joga contra o Remo no domingo")[0], "neutro")

    def test_sentimento_de_placar_alheio(self):
        self.assertEqual(analisar_sentimento("Veja os gols da vitória do RB Bragantino sobre o Santos")[0], "negativo")
        self.assertEqual(analisar_sentimento("Fluminense perde para o Santos pelo Brasileiro")[0], "positivo")

    def test_derrota_do_santos_nao_e_vitoria(self):
        self.assertEqual(analisar_sentimento("Gabigol critica arbitragem após derrota do Santos")[0], "negativo")
        self.assertEqual(analisar_sentimento("Barreal toma amarelo e sai em derrota do Santos")[0], "negativo")

    def test_placar_define_o_sentimento(self):
        self.assertEqual(analisar_sentimento("Fluminense 1 x 2 Santos: melhores momentos")[0], "positivo")
        self.assertEqual(analisar_sentimento("Bragantino 2 x 1 Santos: melhores momentos")[0], "negativo")
        self.assertEqual(analisar_sentimento("Santos 0 x 0 Palmeiras: melhores momentos")[0], "neutro")

    def test_nota_fica_entre_menos_um_e_um(self):
        _, nota, termos = analisar_sentimento("Santos perde, tem lesão, crise, transfer ban e punição")
        self.assertEqual(nota, -1)
        self.assertTrue(termos)

    def test_fora_de_esporte(self):
        for t in ("Santos lança coleção de camisas em homenagem a Pelé",
                  "Em parceria com pai de Neymar, Santos lança coleção urbana em homenagem a Pelé",
                  "Neymar recebe brinco de ouro 18K com diamantes",
                  "Torcedores do Santos são condenados a 21 anos de prisão por morte de palmeirense"):
            self.assertEqual(avaliar_foco(t, "", "https://exemplo.com/x")[1], "fora de esporte", t)
        self.assertGreater(avaliar_foco("Santos anuncia novo patrocinador e reforça o elenco", "", "https://exemplo.com/x")[0], 0)

    def test_nomes(self):
        self.assertIn("Barreal", extrair_nomes("Barreal recebe terceiro amarelo e vira desfalque no Santos"))
        self.assertNotIn("Santos", extrair_nomes("Santos treina para o jogo"))
        self.assertEqual(extrair_nomes("Palmeiras vence o Bragantino"), [])
