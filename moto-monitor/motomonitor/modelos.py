"""Catálogo das motos que interessam: custom, clássicas e estradeiras.

Cada modelo tem:
- busca: o termo digitado nos sites;
- padrao: expressão regular aplicada ao título normalizado (sem acento, minúsculo)
  para confirmar que o anúncio é mesmo daquele modelo;
- fipe_marca / fipe_tokens: como achar o modelo na tabela FIPE (todos os tokens
  precisam aparecer no nome do modelo na FIPE); fipe_excluir descarta variantes.

Para acrescentar um modelo, basta incluir uma linha em CATALOGO (ou usar
"modelos_extras" no config.json).
"""
import re
from dataclasses import dataclass, field

from .textos import normalizar


@dataclass
class Modelo:
    chave: str
    nome: str
    estilo: str  # custom | classica | estradeira
    busca: str
    padrao: str
    fipe_marca: str
    fipe_tokens: list[str]
    fipe_excluir: list[str] = field(default_factory=list)

    def __post_init__(self):
        self._re = re.compile(self.padrao)

    def casa(self, titulo: str) -> bool:
        return bool(self._re.search(normalizar(titulo)))


def _m(chave, nome, estilo, busca, padrao, marca, tokens, excluir=None):
    return Modelo(chave, nome, estilo, busca, padrao, marca, tokens, excluir or [])


CATALOGO: list[Modelo] = [
    # ---------------- Honda ----------------
    _m("shadow600", "Honda Shadow 600", "custom", "shadow 600",
       r"(shadow|vt)\s*600|600\s*shadow", "honda", ["SHADOW", "600"]),
    _m("shadow750", "Honda Shadow 750", "custom", "shadow 750",
       r"(shadow|vt)\s*750|750\s*shadow|shadow\s*(phantom|spirit|aero)", "honda", ["SHADOW", "750"]),
    _m("rebel500", "Honda Rebel 500", "custom", "rebel 500",
       r"\brebel\b", "honda", ["REBEL"]),
    # ---------------- Yamaha ----------------
    _m("virago250", "Yamaha Virago 250", "custom", "virago 250",
       r"virago\s*250|xv\s*250", "yamaha", ["VIRAGO", "250"]),
    _m("virago535", "Yamaha Virago 535", "custom", "virago 535",
       r"virago\s*535|xv\s*535", "yamaha", ["VIRAGO", "535"]),
    _m("dragstar650", "Yamaha Drag Star 650", "custom", "drag star 650",
       r"drag\s*star|dragstar|xvs\s*650", "yamaha", ["650", "DRAG"]),
    _m("midnight950", "Yamaha Midnight Star 950", "custom", "midnight star 950",
       r"midnight|xvs\s*950", "yamaha", ["MIDNIGHT"]),
    # ---------------- Suzuki ----------------
    _m("intruder125", "Suzuki Intruder 125", "custom", "intruder 125",
       r"intruder\s*125", "suzuki", ["INTRUDER", "125"]),
    _m("intruder250", "Suzuki Intruder 250", "custom", "intruder 250",
       r"intruder\s*250", "suzuki", ["INTRUDER", "250"]),
    _m("boulevardm800", "Suzuki Boulevard M800", "custom", "boulevard m800",
       r"\bm\s*800\b|boulevard\s*m|intruder\s*m\s*800", "suzuki", ["M800"]),
    _m("boulevardc800", "Suzuki Boulevard C800", "custom", "boulevard c800",
       r"\bc\s*800\b|boulevard\s*c|intruder\s*800", "suzuki", ["C800"]),
    _m("boulevardm1500", "Suzuki Boulevard M1500", "custom", "boulevard m1500",
       r"\bm\s*1500\b|boulevard\s*1500", "suzuki", ["M1500"]),
    _m("marauder800", "Suzuki Marauder 800", "custom", "marauder 800",
       r"marauder", "suzuki", ["MARAUDER"]),
    # ---------------- Kawasaki ----------------
    _m("vulcan500", "Kawasaki Vulcan 500", "custom", "vulcan 500",
       r"vulcan\s*500|en\s*500", "kawasaki", ["VULCAN", "500"]),
    _m("vulcan800", "Kawasaki Vulcan 800", "custom", "vulcan 800",
       r"vulcan\s*800|vn\s*800", "kawasaki", ["VULCAN", "800"]),
    _m("vulcan900", "Kawasaki Vulcan 900", "custom", "vulcan 900",
       r"vulcan\s*900|vn\s*900", "kawasaki", ["VULCAN", "900"]),
    _m("vulcans650", "Kawasaki Vulcan S 650", "custom", "vulcan s 650",
       r"vulcan\s*s\b|vulcan\s*650|vulcan\s*s\s*650", "kawasaki", ["VULCAN", "650"]),
    _m("eliminator", "Kawasaki Eliminator", "custom", "kawasaki eliminator",
       r"eliminator", "kawasaki", ["ELIMINATOR"]),
    # ---------------- Harley-Davidson ----------------
    _m("sportster883", "Harley-Davidson Sportster 883", "custom", "harley 883",
       r"\b883\b|sportster\s*883|iron\s*883|xl\s*883", "harley", ["883"]),
    _m("sportster1200", "Harley-Davidson Sportster 1200", "custom", "harley sportster 1200",
       r"sportster\s*1200|xl\s*1200|forty\s*eight|\b48\b.*harley|harley.*\b48\b", "harley", ["1200"]),
    # ---------------- Dafra / Kasinski / Haojue ----------------
    _m("horizon150", "Dafra Horizon 150", "custom", "horizon 150",
       r"horizon\s*150", "dafra", ["HORIZON", "150"]),
    _m("horizon250", "Dafra Horizon 250", "custom", "horizon 250",
       r"horizon\s*250", "dafra", ["HORIZON", "250"]),
    _m("mirage150", "Kasinski Mirage 150", "custom", "mirage 150",
       r"mirage\s*150", "kasinski", ["MIRAGE", "150"]),
    _m("mirage250", "Kasinski Mirage 250", "custom", "mirage 250",
       r"mirage\s*250", "kasinski", ["MIRAGE", "250"]),
    _m("mirage650", "Kasinski Mirage 650", "custom", "mirage 650",
       r"mirage\s*650", "kasinski", ["MIRAGE", "650"]),
    _m("masterride", "Haojue Master Ride 150", "custom", "master ride 150",
       r"master\s*ride", "haojue", ["MASTER", "RIDE"]),
    # ---------------- Clássicas ----------------
    _m("classic350", "Royal Enfield Classic 350", "classica", "royal enfield classic 350",
       r"classic\s*350|royal\s*enfield\s*classic", "royal", ["CLASSIC"]),
    _m("meteor350", "Royal Enfield Meteor 350", "custom", "royal enfield meteor 350",
       r"meteor", "royal", ["METEOR"]),
    _m("bullet", "Royal Enfield Bullet", "classica", "royal enfield bullet",
       r"\bbullet\b", "royal", ["BULLET"]),
    _m("hunter350", "Royal Enfield Hunter 350", "classica", "royal enfield hunter 350",
       r"\bhunter\b", "royal", ["HUNTER"]),
    _m("interceptor650", "Royal Enfield Interceptor 650", "classica", "royal enfield interceptor 650",
       r"interceptor", "royal", ["INTERCEPTOR"]),
    _m("continentalgt", "Royal Enfield Continental GT 650", "classica", "royal enfield continental gt",
       r"continental\s*gt", "royal", ["CONTINENTAL"]),
    _m("bonneville", "Triumph Bonneville", "classica", "triumph bonneville",
       r"bonneville|\bt\s*100\b", "triumph", ["BONNEVILLE"]),
    # ---------------- Estradeiras (touring / crossover) ----------------
    _m("versys650", "Kawasaki Versys 650", "estradeira", "versys 650",
       r"versys\s*650|versys(?!\s*(x|300))", "kawasaki", ["VERSYS", "650"]),
    _m("nc750x", "Honda NC 700X / 750X", "estradeira", "honda nc 750x",
       r"\bnc\s*7[05]0\s*x?\b", "honda", ["NC"], ["NC 750 S"]),
    _m("cb500x", "Honda CB 500X", "estradeira", "cb 500x",
       r"cb\s*500\s*x", "honda", ["CB", "500X"]),
    _m("vstrom650", "Suzuki V-Strom 650", "estradeira", "v-strom 650",
       r"v\s*strom\s*650|dl\s*650", "suzuki", ["650", "STROM"]),
]


def catalogo(config: dict | None = None) -> list[Modelo]:
    """Catálogo filtrado pelos estilos/modelos ativos no config."""
    config = config or {}
    modelos = list(CATALOGO)
    for extra in config.get("modelos_extras", []):
        modelos.append(Modelo(**extra))
    estilos = set(config.get("estilos_ativos", ["custom", "classica", "estradeira"]))
    desativados = set(config.get("modelos_desativados", []))
    return [m for m in modelos if m.estilo in estilos and m.chave not in desativados]


def identificar(titulo: str, modelos: list[Modelo]) -> Modelo | None:
    for modelo in modelos:
        if modelo.casa(titulo):
            return modelo
    return None
