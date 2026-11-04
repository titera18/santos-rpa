import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import datetime, timezone

from unittest import mock

import banco
import sentimento_ia
from analise import avaliar_sentimento
from sentimento_ia import combinar
from relevancia import (agrupar_historias, analisar_sentimento, avaliar_foco, classificar_sentimento, classificar_tema,
                        extrair_nomes, pontos_recencia, pontos_repercussao, tokens_do_titulo)


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

    def test_jogo_de_outros_na_vila_nao_e_foco_maximo(self):
        self.assertEqual(self.foco("São Paulo x Corinthians: clássico será na Vila Belmiro"), 15)


class Classificacao(unittest.TestCase):
    def test_servico_vence_jogo(self):
        self.assertEqual(classificar_tema("Bragantino x Santos: onde assistir", "")[0], "Serviço de jogo")

    def test_arbitragem_vence_jogo(self):
        self.assertEqual(classificar_tema("Santos reclama da arbitragem contra o Bragantino", "")[0], "Arbitragem")

    def test_jogo_na_vila_e_jogo_mas_gramado_e_estrutura(self):
        self.assertEqual(classificar_tema("Santos e Palmeiras empatam na Vila Belmiro", "")[0], "Jogo e resultado")
        self.assertEqual(classificar_tema("Abel detona gramado da Vila Belmiro no clássico", "")[0], "Estádio e estrutura")

    def test_sentimento(self):
        self.assertEqual(classificar_sentimento("Santos vence o Remo")[0], "positivo")
        self.assertEqual(classificar_sentimento("Palmeiras vence o Santos")[0], "negativo")
        self.assertEqual(classificar_sentimento("Rodinei assume erro por gol contra")[0], "negativo")
        self.assertEqual(classificar_sentimento("Santos joga contra o Remo no domingo")[0], "neutro")

    def test_sentimento_de_placar_alheio(self):
        self.assertEqual(classificar_sentimento("Veja os gols da vitória do RB Bragantino sobre o Santos")[0], "negativo")
        self.assertEqual(classificar_sentimento("Fluminense perde para o Santos pelo Brasileiro")[0], "positivo")

    def test_derrota_do_santos_nao_e_vitoria(self):
        self.assertEqual(classificar_sentimento("Gabigol critica arbitragem após derrota do Santos")[0], "negativo")
        self.assertEqual(classificar_sentimento("Barreal toma amarelo e sai em derrota do Santos")[0], "negativo")

    def test_placar_define_o_sentimento(self):
        self.assertEqual(classificar_sentimento("Fluminense 1 x 2 Santos: melhores momentos")[0], "positivo")
        self.assertEqual(classificar_sentimento("Bragantino 2 x 1 Santos: melhores momentos")[0], "negativo")
        self.assertEqual(classificar_sentimento("Santos 0 x 0 Palmeiras: melhores momentos")[0], "neutro")

    def test_nota_fica_entre_menos_um_e_um(self):
        _, nota, termos = analisar_sentimento("Santos perde, tem lesão, crise, transfer ban e punição")
        self.assertEqual(nota, -1)
        self.assertTrue(termos)

    def test_acerto_nao_piora_nos_titulos_rotulados(self):
        # Referência medida às cegas em 219 títulos: 74%. Se cair, alguma regra nova piorou o resultado.
        self.assertGreaterEqual(avaliar_sentimento()["acerto"], 74)

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

    def test_historias_de_jogos_diferentes_nao_se_juntam(self):
        agora = datetime(2026, 11, 1, tzinfo=timezone.utc)
        def linha(i, titulo):
            return {"id": i, "quando": agora, "tokens": tokens_do_titulo(titulo),
                    "tema": classificar_tema(titulo, "")[0]}
        h = agrupar_historias([linha(1, "Santos x Bahia: onde assistir ao vivo"),
                               linha(2, "Santos x Palmeiras: onde assistir ao vivo"),
                               linha(3, "Red Bull Bragantino x Santos: onde assistir"),
                               linha(4, "Bragantino x Santos: onde assistir, horário")])
        self.assertNotEqual(h[1], h[2])
        self.assertEqual(h[3], h[4])


class ModeloDeIA(unittest.TestCase):
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

    def test_falha_do_modelo_nao_derruba_e_nao_grava(self):
        con = banco.conectar(":memory:")
        with mock.patch.object(sentimento_ia, "_carregar", side_effect=RuntimeError("sem modelo")):
            self.assertEqual(sentimento_ia.probabilidades(con, ["Santos treina"]), {})
        self.assertEqual(con.execute("SELECT COUNT(*) FROM ia_previsoes").fetchone()[0], 0)
        self.assertTrue(sentimento_ia.indisponivel)
        sentimento_ia.indisponivel = False

    def test_previsao_guardada_nao_recalcula(self):
        con = banco.conectar(":memory:")
        p = {"negativo": 0.1, "neutro": 0.1, "positivo": 0.8}
        with mock.patch.object(sentimento_ia, "_prever", return_value={"Santos treina": p}) as prever:
            sentimento_ia.probabilidades(con, ["Santos treina"])
            self.assertEqual(sentimento_ia.probabilidades(con, ["Santos treina"]), {"Santos treina": p})
        prever.assert_called_once()


class Pontos(unittest.TestCase):
    def test_repercussao(self):
        self.assertEqual(pontos_repercussao(1), 0)
        self.assertEqual(pontos_repercussao(8), 25)
        self.assertEqual(pontos_repercussao(50), 25)

    def test_recencia_cai_pela_metade_em_3_dias(self):
        self.assertEqual(pontos_recencia(0), 20)
        self.assertAlmostEqual(pontos_recencia(3), 10)


if __name__ == "__main__":
    unittest.main()
