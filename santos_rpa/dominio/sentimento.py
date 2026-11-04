"""A notícia é boa ou ruim para o Santos? Regras próprias, complementadas por um modelo de IA."""
import re

from santos_rpa.dominio.foco import EX_ATLETA
from santos_rpa.dominio.modelo import Sentimento
from santos_rpa.dominio.texto import norm

CONFIANCA_MINIMA = 0.70  # abaixo disso, a opinião do modelo de IA é ignorada

# O sentimento responde: "esta notícia é boa ou ruim para o Santos?". Por isso "Palmeiras vence o
# Santos" é negativo, embora a frase em si seja positiva. Pesos: 3 = resultado de jogo, 2 = fato
# claro, 1 = indício. Só o título é lido, pois a maioria das notícias do agregador não tem resumo.
DERROTA_DO_SANTOS = re.compile(
    r"\b(vence|venceu|derrota|derrotou|goleia|goleou|bate|bateu|supera|superou|ultrapassa|vira sobre)\s+(?:o\s+)?santos\b"
    r"|\b(vitoria|triunfo|virada)\b.*\b(sobre|contra)\s+o\s+santos\b"
    r"|\bsantos\b[^,;]{0,30}\b(perde|perdeu)\s+(para|do|de|jogo|o jogo)\b"
    r"|\bderrota (do santos|para)\b|\b(apos|na|em) derrota\b|\bleva virada\b|\be superado\b|\bso uma vitoria\b"
)
VITORIA_DO_SANTOS = re.compile(
    r"\b(perde|perdeu|derrotado)\s+(?:para|pelo|do)\s+(?:o\s+)?santos\b"
    r"|\bsantos\b[^;]{0,40}\b(vence|venceu|goleia|goleou|vira contra|vira sobre|vira o jogo)\b"
    r"|\bvitoria do santos\b"
)
PLACAR = [
    (re.compile(r"\bsantos(?: fc)? (\d+) x (\d+)\b"), False),   # Santos 2 x 1 Bahia
    (re.compile(r"\b(\d+) x (\d+) santos\b"), True),            # Bahia 1 x 2 Santos
    (re.compile(r"\bfaz (\d+) a (\d+) no santos\b"), True),     # Bahia faz 2 a 1 no Santos
]

# Ordem importa: expressões longas vêm antes e consomem o trecho, para que "se recupera de lesão"
# não conte também como "lesão".
_REGRAS_SENTIMENTO = [
    # o que parece ruim, mas é bom
    (2, r"se recupera de lesao|se recupera\b|volta aos treinos|volta a treinar|retorno de lesionados|sem restricoes|se aproxima de retorno|avanca em transicao"),
    (2, r"(ganha|recebe|pode ganhar|tem) (\w+ ){0,2}reforco( \w+)?|reforco (importante|de peso)"),
    (1, r"tera retornos|pode voltar|deve voltar|evolui"),
    # o que parece bom, mas é ruim
    (-2, r"perde invencibilidade|ganha (\w+ ){0,2}desfalque|nao e convocado|fica mais longe|mais distante|se distancia|se afasta|perde forca|cai para|perde \w+ jogador"),
    (-2, r"nada boa|alerta preocupante|liga alerta|crise de caixa|impedido de contratar|queda de rendimento"),
    # fatos negativos
    (-2, r"gol contra|transfer bans?|punicao|punid\w+|multa e advertencia|calote|crise|rebaixamento|expuls\w+|suspens\w+|suspenso"),
    (-2, r"lesao|lesoes|lesionad\w+|desfalc\w+|desfalques?|baixas?\b|interdi\w+|\bcede\b|dividas?|atrasad\w+"),
    (-2, r"detona\w*|destroi|lamentavel|inacreditavel|desabafa|arrasa|revoltad\w+|prejudica\w*|vitima|safado|repudia|ataca\b"),
    (-1, r"critica\w*|reclama\w*|questiona\w*|contesta\w*|irrita\w*|polemica?|erros?\b|falhas?\b|grotesc\w+|esquecid\w+|geladeira|de escanteio|preocupa\w*|vira duvida|duvidas?\b|revelia|ridiculo|revs|reves|tropeco|lamenta\w*|protesto|ignorado|ultrapassado"),
    # fatos positivos
    (2, r"exalta\w*|enaltece\w*|elogia\w*|brilha\w*|campanha maravilhosa|grande fase|boa fase|embalad\w+|sequencia vitoriosa|recorde de publico|poder de reacao|igual para igual|heroica|clube da minha vida|entra para a historia"),
    (2, r"novo patrocinador|patrocinio master|patrocinio maximo|recebe \d+ milhoes|convocad\w+|conquist\w+|titulos?\b|saem na frente|moderniza\w*|lidera\b|lider\b"),
    (1, r"celebra\w*|comemora\w*|destaca\w*|destaque|se aproxima de marca|persegue recordes|comprometimento|avanca\w*|invencib\w+|certeira|sonho|sonhando"),
]
_REGRAS_SENTIMENTO = [(peso, re.compile(rf"\b(?:{rx})")) for peso, rx in _REGRAS_SENTIMENTO]


def _pontos_do_placar(t: str) -> int:
    for regex, santos_depois in PLACAR:
        m = regex.search(t)
        if m:
            a, b = int(m[1]), int(m[2])
            gols_santos, gols_rival = (b, a) if santos_depois else (a, b)
            return 3 if gols_santos > gols_rival else -3 if gols_santos < gols_rival else 0
    return 0


def analisar_sentimento(titulo: str) -> Sentimento:
    """Lê o título do ponto de vista do clube e explica a nota pelos termos que pesaram."""
    t = norm(titulo)
    if EX_ATLETA.search(t):
        return Sentimento("neutro", 0.0, [])  # o feito de um ex-atleta não diz nada sobre o clube
    pontos, termos = _pontos_do_placar(t), []
    if DERROTA_DO_SANTOS.search(t):
        pontos -= 3
        termos.append("derrota do Santos")
    elif VITORIA_DO_SANTOS.search(t):
        pontos += 3
        termos.append("vitória do Santos")
    elif pontos:
        termos.append("vitória do Santos" if pontos > 0 else "derrota do Santos")
    for peso, regex in _REGRAS_SENTIMENTO:
        m = regex.search(t)
        if m:
            pontos += peso
            termos.append(m.group(0))
            t = regex.sub(" ", t)
    rotulo = "positivo" if pontos > 0 else "negativo" if pontos < 0 else "neutro"
    return Sentimento(rotulo, round(max(-1.0, min(1.0, pontos / 4)), 2), termos)


def combinar(rotulo: str, nota: float, probs: dict[str, float] | None) -> tuple[str, float, str]:
    """As regras decidem primeiro, e o modelo só opina quando elas dão neutro.

    Retorna (rótulo, nota de -1 a 1, origem). A nota do modelo vai até 0,5 em módulo: nunca supera um resultado de jogo.
    """
    if rotulo != "neutro" or not probs:
        return rotulo, nota, "regras"
    maior = max(probs, key=probs.get)
    if maior == "neutro" or probs[maior] < CONFIANCA_MINIMA:
        return rotulo, nota, "regras"
    sinal = 1 if maior == "positivo" else -1
    return maior, round(sinal * probs[maior] / 2, 2), "ia"
