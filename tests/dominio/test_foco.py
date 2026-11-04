import unittest

from santos_rpa.dominio.foco import avaliar_foco


class FiltroDoClube(unittest.TestCase):
    def foco(self, titulo, resumo="", url="https://exemplo.com/x"):
        return avaliar_foco(titulo, resumo, url)[0]

    def test_aceita_clube(self):
        for t in ("Santos vence o Remo no Mangueirão",
                  "Bragantino x Santos: onde assistir ao vivo",
                  "Cuca lamenta gol contra do Santos",
                  "Mattos aponta erros da arbitragem e afirma que Santos irá à CBF"):
            self.assertGreaterEqual(self.foco(t), 25, t)

    def test_rejeita_outros_santos(self):
        for t in ("Tentativa de homicídio contra PM é investigada em Santos",
                  "Túnel Santos-Guarujá avança em meio a tensão entre governos",
                  "Porto de Santos bate recorde de exportação de soja",
                  "Silvio Santos ganha homenagem em São Paulo",
                  "Maria dos Santos é a nova diretora da escola",
                  "Santos Laguna vence e lidera o Campeonato Mexicano"):
            self.assertEqual(self.foco(t), 0, t)

    def test_sobrenome_com_futebol_nao_e_clube(self):
        self.assertEqual(self.foco("Gol de Bruno Santos garante vitória do Remo"), 0)

    def test_editoria_do_clube_sem_citar_no_titulo(self):
        url = "https://ge.globo.com/sp/santos-e-regiao/futebol/times/santos/noticia/2026/11/02/x.ghtml"
        self.assertEqual(self.foco("Barreal recebe terceiro amarelo e vira desfalque", url=url), 18)

    def test_ex_atleta_vale_pouco(self):
        self.assertEqual(self.foco("Ex-Flamengo e Santos faz gol de cabeça na várzea"), 8)

    def test_noticias_reais_que_eram_rejeitadas(self):
        self.assertGreaterEqual(self.foco("Lesões já tiraram jogadores do Santos de 180 partidas em 2026"), 25)
        self.assertGreaterEqual(self.foco("Sem Arão e Veríssimo, Santos pode acelerar renovação da zaga"), 25)

    def test_clube_sem_vocabulario_de_futebol(self):
        self.assertGreaterEqual(self.foco("Agibank é o novo patrocinador master do Santos"), 25)
        self.assertGreaterEqual(self.foco("Por que Ramón Sosa está fora de Santos x Palmeiras?"), 25)
        self.assertEqual(self.foco("Santos tem novo hospital municipal"), 0)

    def test_jogo_de_outros_na_vila_e_descartado(self):
        for t in ("São Paulo x Corinthians: clássico será na Vila Belmiro",
                  "Corinthians se prepara para Majestoso decisivo na Vila Belmiro",
                  "São Paulo faz último treino antes do Majestoso na Vila Belmiro",
                  "São Paulo pede à CBF para jogar contra Corinthians na Vila Belmiro"):
            self.assertEqual(avaliar_foco(t, "Partida na casa do Santos pelo Brasileirão", "https://exemplo.com/x"),
                             (0, "jogo de outros clubes na Vila Belmiro"), t)

    def test_noticia_do_estadio_continua(self):
        for t in ("Abel detona gramado da Vila Belmiro e acende alerta para São Paulo x Corinthians",
                  "Parte da estrutura da Vila Belmiro cede sobre torcida do Bahia",
                  "Abel avalia clássico equilibrado do Palmeiras e detona gramado da Vila",
                  "Vila Belmiro faz 110 anos: de Pelé a Neymar, estádio foi pioneiro na TV brasileira",
                  "Palmeiras busca vitória na Vila Belmiro"):
            self.assertEqual(self.foco(t), 15, t)

    def test_jogo_do_santos_na_vila_continua(self):
        self.assertEqual(self.foco("Santos recebe o Palmeiras em clássico na Vila Belmiro"), 25)
