from pathlib import Path

import pytest

from motomonitor import regras
from motomonitor.coletor import Coletor
from motomonitor.config import PADRAO, _mesclar
from motomonitor.db import Banco
from motomonitor.fipe import Fipe
from motomonitor.fontes import mercadolivre, olx
from motomonitor.fontes.base import Anuncio
from motomonitor.modelos import CATALOGO, catalogo, identificar
from motomonitor.textos import extrair_ano, para_inteiro

FIX = Path(__file__).parent / "fixtures"
R = PADRAO["regras"]


# ------------------------------------------------------------------ textos/modelos
def test_conversoes():
    assert para_inteiro("R$ 15.900") == 15900
    assert para_inteiro("R$ 15.900,50") == 15900
    assert extrair_ano("Shadow 750 ano 2012/2013") == 2012


@pytest.mark.parametrize("titulo,chave", [
    ("HONDA SHADOW 750 2012", "shadow750"),
    ("Honda VT 600 Shadow", "shadow600"),
    ("Yamaha Drag Star 650", "dragstar650"),
    ("Suzuki Intruder 125 ", "intruder125"),
    ("Suzuki Boulevard M800", "boulevardm800"),
    ("Harley Davidson Sportster XL 883 Iron", "sportster883"),
    ("Kawasaki Vulcan 900 Classic", "vulcan900"),
    ("Royal Enfield Classic 350", "classic350"),
    ("Yamaha Drag Star 1100 Classic", "dragstar1100"),
    ("Yamaha XVS 1100", "dragstar1100"),
    ("Honda Shadow 1100 ACE", "shadow1100"),
    ("Suzuki Boulevard M1500", "boulevardm1500"),
    ("Suzuki Boulevard C1500 T", "boulevardc1500"),
    ("Suzuki Intruder 1500 LC", "boulevardc1500"),
    ("Kawasaki Vulcan 1500 Classic", "vulcan1500"),
    ("Honda VTX 1300", "vtx1300"),
    ("Dafra Horizon 250", "horizon250"),
])
def test_identifica_modelos(titulo, chave):
    assert identificar(titulo, CATALOGO).chave == chave


@pytest.mark.parametrize("titulo", ["Honda CG 160 Titan", "Yamaha Fazer 250", "Honda Biz 125", "Kawasaki Versys 650", "Honda NC 750X", "Suzuki V-Strom 650"])
def test_ignora_motos_fora_do_estilo(titulo):
    assert identificar(titulo, CATALOGO) is None


def test_shadow_e_estradeira():
    assert identificar("Honda Shadow 750", CATALOGO).estilo == "estradeira"


def test_filtra_estilos_do_config():
    so_custom = catalogo({"estilos_ativos": ["custom"]})
    assert all(m.estilo == "custom" for m in so_custom)


# ------------------------------------------------------------------ regras
def test_regras():
    assert regras.avaliar(17900, None, R) == ["Abaixo de R$ 18.000"]
    assert regras.avaliar(18000, None, R) == ["Abaixo de R$ 18.000"]
    assert regras.avaliar(25000, 30000, R) == ["17% abaixo da FIPE (R$ 30.000)"]
    assert regras.avaliar(28000, 30000, R) == []           # só 6,7% abaixo
    assert regras.avaliar(31000, 40000, R) == []           # acima do teto de 30k
    assert regras.avaliar(30000, 34000, R) != []           # 30k com 11,7% abaixo
    assert regras.avaliar(2500, 30000, R) == []            # implausível (entrada/golpe)
    assert len(regras.avaliar(15000, 20000, R)) == 2


# ------------------------------------------------------------------ fontes
def test_olx_interpreta_next_data():
    ads = olx.interpretar((FIX / "olx.html").read_text())
    assert len(ads) == 4
    a = ads[0]
    assert (a.id_externo, a.preco, a.ano, a.km, a.cidade) == ("1234567890", 24900, 2012, 38000, "Curitiba")
    assert a.imagem.endswith("a.jpg")
    assert ads[1].cidade == "Colombo"


def test_mercadolivre_interpreta_cards():
    ads = mercadolivre.interpretar((FIX / "mercadolivre.html").read_text())
    assert [a.id_externo for a in ads] == ["MLB5555555555", "MLB6666666666"]
    v = ads[0]
    assert (v.preco, v.ano, v.km, v.cidade) == (29000, 2011, 41000, "São José dos Pinhais")


# ------------------------------------------------------------------ FIPE simulada
class RespostaFalsa:
    def __init__(self, dados): self.dados = dados
    def raise_for_status(self): pass
    def json(self): return self.dados


class SessaoFipeFalsa:
    headers = {}
    VALORES = {("1", "10", "2012-1"): "R$ 32.000,00", ("1", "10", "2003-1"): "R$ 19.000,00",
               ("2", "20", "2011-1"): "R$ 33.000,00", ("2", "21", "2011-1"): "R$ 35.000,00",
               ("3", "30", "2015-1"): "R$ 8.900,00"}

    def __init__(self): self.chamadas = 0

    def get(self, url, timeout=None):
        self.chamadas += 1
        p = url.split("/motos/")[1].split("/")
        if p == ["marcas"]:
            return RespostaFalsa([{"codigo": "1", "nome": "HONDA"}, {"codigo": "2", "nome": "KAWASAKI"},
                                  {"codigo": "3", "nome": "SUZUKI"}])
        if len(p) == 3:
            return RespostaFalsa({"modelos": {
                "1": [{"codigo": "10", "nome": "SHADOW 750"}, {"codigo": "11", "nome": "VT 600C SHADOW"}],
                "2": [{"codigo": "20", "nome": "VULCAN 900 CLASSIC"}, {"codigo": "21", "nome": "VULCAN 900 CLASSIC LT"}],
                "3": [{"codigo": "30", "nome": "INTRUDER 125"}]}[p[1]]})
        if len(p) == 5:
            anos = {"10": ["2012-1"], "11": ["2003-1"], "20": ["2011-1"], "21": ["2011-1"], "30": ["2015-1"]}[p[3]]
            return RespostaFalsa([{"codigo": c, "nome": c[:4]} for c in anos])
        valor = self.VALORES.get((p[1], p[3], p[5]))
        if (p[1], p[3]) == ("1", "11"):
            valor = self.VALORES[("1", "10", "2003-1")]
        return RespostaFalsa({"Valor": valor})


@pytest.fixture
def banco():
    return Banco(":memory:")


def test_fipe_mediana_e_cache(banco):
    sessao = SessaoFipeFalsa()
    fipe = Fipe(banco, "https://x/fipe/api/v1/motos", sessao=sessao)
    vulcan = next(m for m in CATALOGO if m.chave == "vulcan900")
    valor, ref = fipe.consultar(vulcan, 2011)
    assert valor == 34000 and "VULCAN 900 CLASSIC LT" in ref
    antes = sessao.chamadas
    assert fipe.consultar(vulcan, 2011)[0] == 34000
    assert sessao.chamadas == antes  # veio do cache


# ------------------------------------------------------------------ fluxo completo
class FonteFalsa:
    def __init__(self, nome, arquivo, modulo):
        self.nome, self.arquivo, self.modulo = nome, arquivo, modulo

    def buscar(self, termo):
        return self.modulo.interpretar((FIX / self.arquivo).read_text())


def test_coleta_completa(banco):
    config = _mesclar(PADRAO, {"cidades": ["Curitiba", "Colombo", "São José dos Pinhais"]})
    notificados = []
    fontes = [FonteFalsa("olx", "olx.html", olx), FonteFalsa("mercadolivre", "mercadolivre.html", mercadolivre)]
    c = Coletor(config, banco, fontes=fontes,
                fipe=Fipe(banco, "https://x/fipe/api/v1/motos", sessao=SessaoFipeFalsa()),
                notificar=lambda a, m: notificados.append((a["id"], m)))
    res = c.rodar()
    assert res["ok"] and not res["erros"]

    ids = {a["id"]: a for a in banco.anuncios(incluir_ocultos=True)}
    assert "olx:3333333333" not in ids            # CG 160 não é custom
    assert "olx:4444444444" not in ids            # R$ 2.000: entrada/golpe, descartado
    assert "mercadolivre:MLB6666666666" not in ids  # Londrina: fora da região
    shadow = ids["olx:1234567890"]
    assert shadow["fipe"] == 32000 and shadow["alerta"] == 1   # 22% abaixo da FIPE
    intruder = ids["olx:2222222222"]
    assert intruder["alerta"] == 1 and "Abaixo de R$ 18.000" in intruder["motivos"]
    vulcan = ids["mercadolivre:MLB5555555555"]
    assert vulcan["fipe"] == 34000 and vulcan["alerta"] == 1   # 29k, 14,7% abaixo
    assert len(notificados) == 3

    # segunda coleta igual não repete alertas
    c.rodar()
    assert len(notificados) == 3


def test_queda_de_preco_gera_novo_alerta(banco):
    config = _mesclar(PADRAO, {})
    avisos = []
    c = Coletor(config, banco, fontes=[], fipe=Fipe(banco, "https://x/fipe/api/v1/motos", sessao=SessaoFipeFalsa()),
                notificar=lambda a, m: avisos.append(a["preco"]))
    base = dict(fonte="olx", id_externo="9", titulo="Suzuki Intruder 125", url="u", cidade="Curitiba", ano=2015)
    c.processar(Anuncio(preco=12000, **base))
    c.processar(Anuncio(preco=12000, **base))
    c.processar(Anuncio(preco=11000, **base))
    assert avisos == [12000, 11000]
    assert [h["preco"] for h in banco.historico("olx:9")] == [12000, 11000]
