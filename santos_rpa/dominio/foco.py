"""A notícia é sobre o Santos FC? Quanto o clube é o assunto principal dela?"""
import re

from santos_rpa.dominio.clubes import OUTROS_CLUBES
from santos_rpa.dominio.modelo import Foco
from santos_rpa.dominio.texto import norm

# Notícia que cita o clube, mas não é sobre esporte: moda, vida pessoal, ações sociais, polícia.
# Diretoria, finanças e estádio ficam, pois afetam o time e o jogo.
FORA_DE_ESPORTE = re.compile(
    r"colecao (de roupas|de camisas|de moda|urbana)|universo da moda|desfile\b|camisas? (especial|de edicao limitada|em homenagem)"
    r"|lanca camisa|nucleo .*saude da mulher|saude da mulher|acao de limpeza|acoes sociais|dia das criancas"
    r"|visita de \d+ criancas|instituto leao do mar|obra de artista|museu pele|busto de pele"
    r"|presenca em show|brinco|ferrari|churrascaria|feriado na praia|com filhas|ao cinema|personagem"
    r"|condenad\w+ a \d+ anos|por morte de|justica condena|delegacia|dublador|jogos abertos do interior"
)
CLUBE_EXPLICITO = re.compile(
    r"santos fc|santos futebol clube|alvinegro praiano|sereias da vila"
    r"|meninos da vila|ct rei pele|\btorcida santista|\bsantistas?\b(?<!baixada santista)"
)
# O estádio também recebe jogos de outros clubes: é ligado ao Santos, mas não é o assunto principal.
ESTADIO = re.compile(r"vila belmiro|gramado da vila")
CONDICAO_DO_ESTADIO = re.compile(r"gramado|relvado|\bcampo\b|\bteto\b|forro|cobertura|estrutura|reforma|\bobras?\b|interdi|capacidade|desaba|\bcede\b")
CLASSICO = re.compile(r"\b(classico|majestoso)\b")
# Atualize esta lista quando o elenco ou a comissão mudarem.
PESSOAS_DO_CLUBE = re.compile(r"\b(neymar|gabigol|cuca)\b")
VEICULOS_ESPORTIVOS = {"ge", "lance", "gazeta esportiva", "espn brasil", "bolavip brasil", "onefootball", "r7 esportes"}
OUTRO_SANTOS = re.compile(
    r"porto de santos|prefeitura de santos|santos[- ]guaruja|tunel santos|santos[- ]dumont"
    r"|santos laguna|todos os santos|baixada santista|silvio santos|santos[- /]ap\b"
    r"|prefeito de santos|cidade de santos|camara de santos|santos e regiao|santa casa de santos"
)
FUTEBOL = re.compile(
    r"\b(futebol|brasileirao|campeonato|paulistao|libertadores|sul-americana|copa|titulo|"
    r"gols?|tecnico|treinador|rodada|partidas?|jogos?|jogador(es)?|atacante|zagueiros?|zaga|goleiro|"
    r"volante|lateral|meia|meio-campo|elenco|escalacao|torcida|torcedor(es)?|arbitragem|var|penalti|"
    r"clube|saf|contrato|reforcos?|mercado da bola|vence|venceu|empata|empatou|perde|derrota|"
    r"neymar|gabigol|cuca|classico|duelo|mandante|campanha|reapresenta|comissao tecnica|gramado|"
    r"palmeiras|corinthians|sao paulo|flamengo|fluminense|vasco|botafogo|gremio|cruzeiro|"
    r"internacional|bragantino|mirassol|bahia|atletico|sub-\d+|feminino|sereias|peixe|"
    r"lesao|lesoes|lesionados?|desfalques?|convocado|treinos?|titular|reserva|fifa|transfer bans?|"
    r"cbf|stjd|atletas?|estadio|patrocinador|minutagem|contratar|contratacao|contratacoes|camisas?|vila)\b"
)
URL_DO_CLUBE = re.compile(
    r"/times/santos/|lance\.com\.br/santos/|/esportes/santos/|/futebol/santos/|santistas\.net|santosfc\.com\.br"
)
# "dos Santos" e "Bruno Santos" são sobrenomes; "de/em Santos" costuma ser a cidade.
NAO_E_CLUBE = re.compile(
    r"\b(?:dos|das|de|em)\s+Santos\b(?!\s+x\b)|\b[A-ZÀ-Ý][a-zà-ÿ]+\s+Santos\b"
)
# "do Santos", "pelo Santos", "x Santos": a cidade não aparece com essas construções.
USO_DE_CLUBE = re.compile(
    r"\b(?:do|no|ao|pelo|para o|contra o|sobre o|o|x|vs\.?)\s+Santos\b|\bSantos\s+x\b", re.IGNORECASE
)
EX_ATLETA = re.compile(r"\bex-[\w-]*\s*(?:e\s+|do\s+)?santos\b|\bex-santos\b")


def _cita_clube(texto: str) -> bool:
    """Há "Santos" que não seja sobrenome nem a cidade?"""
    limpo = NAO_E_CLUBE.sub(" ", texto or "")
    return re.search(r"\bSantos\b|\bSANTOS\b", limpo) is not None


def _jogo_de_outros_clubes(titulo_norm: str) -> bool:
    """Título que cita o estádio, sem citar o Santos, e trata de uma partida de outros clubes.

    A condição do estádio continua na base mesmo nesses casos, porque o estádio é do clube.
    """
    if CONDICAO_DO_ESTADIO.search(titulo_norm):
        return False
    clubes = set(OUTROS_CLUBES.findall(titulo_norm))
    return len(clubes) >= 2 or bool(clubes and CLASSICO.search(titulo_norm))


def avaliar_foco(titulo: str, resumo: str, url: str, fonte: str = "") -> Foco:
    """Zero pontos significa descartar."""
    t, r = norm(titulo), norm(resumo)
    junto = f"{t} {r}"
    url_clube = bool(URL_DO_CLUBE.search(url))
    if FORA_DE_ESPORTE.search(t):
        return Foco(0, "fora de esporte")
    if OUTRO_SANTOS.search(t) and not CLUBE_EXPLICITO.search(t):
        return Foco(0, "outro Santos (cidade, porto, etc.)")
    if EX_ATLETA.search(t):
        return Foco(8, "ex-atleta citado")
    if CLUBE_EXPLICITO.search(t) or "santosfc.com.br" in url:
        return Foco(30, "clube explícito no título")
    tem_futebol = FUTEBOL.search(junto) is not None
    if _cita_clube(titulo):
        if tem_futebol or url_clube or norm(fonte) in VEICULOS_ESPORTIVOS or USO_DE_CLUBE.search(titulo):
            return Foco(25, "clube no título")
        return Foco(0, "'Santos' sem contexto de futebol")
    if url_clube:
        return Foco(18, "matéria da editoria do clube")
    if re.search(r"\bpeixe\b", t) and tem_futebol:
        return Foco(25, "apelido do clube no título")
    if ESTADIO.search(t):
        if _jogo_de_outros_clubes(t):
            return Foco(0, "jogo de outros clubes na Vila Belmiro")
        return Foco(15, "estádio do clube")
    if PESSOAS_DO_CLUBE.search(t):
        return Foco(18, "pessoa do clube no título")
    if (CLUBE_EXPLICITO.search(r) or _cita_clube(resumo)) and tem_futebol:
        return Foco(12, "citado apenas no resumo")
    return Foco(0, "não trata do clube")
