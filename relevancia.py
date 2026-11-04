"""Regras de negócio: é do Santos FC? qual tema e tom? qual a relevância?

Tudo é baseado em regras explícitas, para que cada nota possa ser explicada.
A relevância (0-100) é a soma de quatro componentes:

    foco         0-30  o clube é o assunto principal ou só é citado?
    tema         0-25  o assunto afeta o clube (SAF, mercado) ou é serviço (onde assistir)?
    repercussão  0-25  quantos veículos diferentes cobriram a mesma história?
    recência     0-20  cai pela metade a cada 3 dias
"""
import hashlib
import json
import math
import re
import unicodedata
from datetime import datetime

import sentimento_ia

MEIA_VIDA_DIAS = 3
JANELA_HISTORIA_DIAS = 3
SIMILARIDADE_MIN = 0.45


def norm(texto: str) -> str:
    """Minúsculas e sem acentos, para comparar textos."""
    t = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


def chave(titulo: str, fonte: str) -> str:
    base = re.sub(r"[^a-z0-9 ]", "", norm(titulo)) + "|" + norm(fonte)
    return hashlib.sha1(base.encode()).hexdigest()


# ---------------------------------------------------------------- filtro do clube

CLUBE_EXPLICITO = re.compile(
    r"santos fc|santos futebol clube|alvinegro praiano|sereias da vila"
    r"|meninos da vila|ct rei pele|\btorcida santista|\bsantistas?\b(?<!baixada santista)"
)
# O estádio também recebe jogos de outros clubes: é ligado ao Santos, mas não é o assunto principal.
ESTADIO = re.compile(r"vila belmiro|gramado da vila")
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


def avaliar_foco(titulo: str, resumo: str, url: str, fonte: str = "") -> tuple[float, str]:
    """Retorna (pontos de foco, motivo). Zero pontos significa descartar."""
    t, r = norm(titulo), norm(resumo)
    junto = f"{t} {r}"
    url_clube = bool(URL_DO_CLUBE.search(url))
    if FORA_DE_ESPORTE.search(t):
        return 0, "fora de esporte"
    if OUTRO_SANTOS.search(t) and not CLUBE_EXPLICITO.search(t):
        return 0, "outro Santos (cidade, porto, etc.)"
    if EX_ATLETA.search(t):
        return 8, "ex-atleta citado"
    if CLUBE_EXPLICITO.search(t) or "santosfc.com.br" in url:
        return 30, "clube explícito no título"
    tem_futebol = FUTEBOL.search(junto) is not None
    if _cita_clube(titulo):
        if tem_futebol or url_clube or norm(fonte) in VEICULOS_ESPORTIVOS or USO_DE_CLUBE.search(titulo):
            return 25, "clube no título"
        return 0, "'Santos' sem contexto de futebol"
    if url_clube:
        return 18, "matéria da editoria do clube"
    if re.search(r"\bpeixe\b", t) and tem_futebol:
        return 25, "apelido do clube no título"
    if ESTADIO.search(t):
        return 15, "estádio do clube"
    if PESSOAS_DO_CLUBE.search(t):
        return 18, "pessoa do clube no título"
    if (CLUBE_EXPLICITO.search(r) or _cita_clube(resumo)) and tem_futebol:
        return 12, "citado apenas no resumo"
    return 0, "não trata do clube"


# ---------------------------------------------------------------- tema

# Ordem importa: o primeiro que casar vence. Serviço e arbitragem vêm antes de Jogo.
TEMAS = [
    ("Serviço de jogo", 5, r"onde assistir|que horas|como assistir|ingressos?\b|transmissao|prov[aá]veis escalac"),
    ("Arbitragem", 18, r"arbitr|\bvar\b|\bpenalti\b.*(ignorad|nao marcad)|\bjuiz\b|\bjuizes\b|\bedina\b|prejudicad"),
    ("Lesões e suspensões", 20, r"lesao|lesoes|lesionad|desfalc|desfalque|departamento medico|\bdm\b|transicao|cirurgia|machuc|suspens|terceiro amarelo|cartao|\bamarelo\b|stjd|gancho|punicao|expuls|voltar a jogar"),
    ("Diretoria e SAF", 25, r"\bsaf\b|presidente|presidencial|teixeira|diretoria|financ|divida|deve\b|conselho|eleicao|eleicoes|estatuto|assembleia|investidor|maruca|balanco|patrocin|transfer ban|multa e advertencia"),
    ("Mercado", 22, r"contrat|reforc|negocia|transfer|renov|mercado da bola|sondad|proposta|emprestim|emprestad|salario|multa rescis|acerta com|deixa o santos"),
    ("Seleção", 10, r"convoca|selecao"),
    ("Base e feminino", 12, r"sub-?\d+|\bbase\b|feminino|sereias|meninos da vila"),
    ("Estádio e estrutura", 12, r"gramado|pacaembu|\bobras?\b|reforma|\bct\b|\bteto\b|forro|cobertura|interdi|capacidade|novo estadio"),
    ("Jogo e resultado", 20, r"\bx\b|vence|venceu|perde|perdeu|empata|empatou|derrota|vitoria|goleada|\bgols?\b|empate|\bfaz \d a \d|atuacoes|analise:|rodada|brasileirao|tabela|classificacao|rebaixamento|z-4|classico|duelo|confronto|encara|enfrenta|libertadores|invencib|mandante|visitante|campanha|\bcontra o\b"),
    ("Elenco e comissão", 15, r"treino|treina|elenco|tecnico|cuca|titular|reserva|escalac|entrevista|neymar|gabigol|jogador|zagueiro|atacante|goleiro|meia\b|volante"),
    ("História e institucional", 8, r"historia|memoria|aniversario|idolo|pele\b|homenag|museu|centro de documentacao"),
    ("Estádio e estrutura", 12, r"vila belmiro|estadio|morumbis"),  # citar o estádio não supera o assunto do jogo
]
TEMAS = [(nome, pts, re.compile(rx)) for nome, pts, rx in TEMAS]
TEMA_PADRAO = ("Outros", 5)


def classificar_tema(titulo: str, resumo: str) -> tuple[str, float]:
    t, r = norm(titulo), norm(resumo)
    for texto in (t, r):  # o título tem prioridade sobre o resumo
        for nome, pts, rx in TEMAS:
            if rx.search(texto):
                return nome, pts
    return TEMA_PADRAO


# ---------------------------------------------------------------- sentimento

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


def analisar_sentimento(titulo: str) -> tuple[str, float, list[str]]:
    """Retorna (rótulo, nota de -1 a 1, termos que pesaram na nota)."""
    t = norm(titulo)
    if EX_ATLETA.search(t):
        return "neutro", 0.0, []  # o feito de um ex-atleta não diz nada sobre o clube
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
    return rotulo, round(max(-1.0, min(1.0, pontos / 4)), 2), termos


def classificar_sentimento(titulo: str, resumo: str = "") -> tuple[str, float]:
    rotulo, nota, _ = analisar_sentimento(titulo)
    return rotulo, nota


# ---------------------------------------------------------------- somente esporte

# Notícia que cita o clube, mas não é sobre esporte: moda, vida pessoal, ações sociais, polícia.
# Diretoria, finanças e estádio ficam, pois afetam o time e o jogo.
FORA_DE_ESPORTE = re.compile(
    r"colecao (de roupas|de camisas|de moda|urbana)|universo da moda|desfile\b|camisas? (especial|de edicao limitada|em homenagem)"
    r"|lanca camisa|nucleo .*saude da mulher|saude da mulher|acao de limpeza|acoes sociais|dia das criancas"
    r"|visita de \d+ criancas|instituto leao do mar|obra de artista|museu pele|busto de pele"
    r"|presenca em show|brinco|ferrari|churrascaria|feriado na praia|com filhas|ao cinema|personagem"
    r"|condenad\w+ a \d+ anos|por morte de|justica condena|delegacia|dublador|jogos abertos do interior"
)


# ---------------------------------------------------------------- nomes do título

NOME = re.compile(
    r"\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]{2,}(?:\s+(?:de\s+|da\s+|do\s+)?[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]{2,})?"
)
NAO_NOMES = set(norm(x) for x in """
Santos Peixe Análise Atuações Brasileirão Copa Série Veja Saiba Confira Vila Belmiro Como Por Para Com
Sem Após Antes Onde Quando Quem Qual Mais Não Sim Ele Ela Isso Este Esta Esse Essa Uma Dos Das Nos Nas
Ainda Segundo Assim Agora Hoje Ontem Amanhã Melhores Momentos Bastidores Vídeo Vídeos Foto Fotos
Gol Gols Técnico Clube Futebol Time Jogo Jogos Rodada Sul-Americana Libertadores Data Fifa Seleção
Mercado Bola Base Feminino Torcida Diretoria Presidente Lateral Atacante Zagueiro Goleiro Volante
Meia Santista Santistas Alvinegro Ex Ao Vivo Paulistão Campeonato Liga Brasil Sub Sobre Entre Até
Desde Durante Contra Pelo Pela Nova Novo Novos Novas Ídolo Jogador Jogadores Saiba Escalação
Palpite Palpites Prováveis Provável Horário Assistir Transmissão Salário Especialista Entrevista
Brasileiro Brasileira Brasileiros Paulista Foi Jornalista Venda Nota Entenda Mar Gramado Treino Ásia
Sereias Rei Instituto Umbro Bicampeãs Conmebol Maracanã Morumbis Sobre Marca Dia Ano Cidade Governo
Lei Justiça Evento Projeto Programa Festival Semana Domingo Sábado Segunda Terça Quarta Quinta Sexta
Janeiro Fevereiro Março Abril Maio Junho Julho Agosto Setembro Outubro Novembro Dezembro
Cuiabá Bragança Leão Jovem Torcedores Torcedor Regra Assista Embalado Agibank Mundial Falhou
Inacreditável Lamentável Opinião Suspenso Feminina Pampas Topo Núcleo Vini Série Atuação Massa
Empate Reveladas Revelado Comunicado Novidade Crise Absurdo Colunista Federação Museu Estatuto
""".split())
LUGARES = {"sao vicente", "santo andre", "praia grande", "sao paulo"}
CLUBES = set(norm(x) for x in """
Palmeiras Corinthians Flamengo Fluminense Vasco Botafogo Grêmio Cruzeiro Internacional Bragantino
Mirassol Bahia Atlético Vitória Coritiba Remo Fortaleza Ceará Sport Juventude Chapecoense Ponte Preta
Athletico Ajax Guarani Portuguesa
""".split()) | {"sao paulo", "red bull", "ponte preta", "santo andre", "atletico-mg", "rb bragantino"}
APELIDOS = {"Philippe Coutinho": "Coutinho", "Willian Arão": "Arão", "Pelé Rei": "Pelé",
            "João Schmidt": "Schmidt", "Álvaro Barreal": "Barreal", "Lucas Veríssimo": "Veríssimo",
            "Rodrigo Nestor": "Nestor", "Arthur Melo": "Arthur", "Vinicius Lira": "Vinícius Lira"}


def extrair_nomes(titulo: str) -> list[str]:
    """Pessoas citadas no título. Clubes e palavras comuns em maiúscula ficam de fora."""
    nomes = []
    for m in NOME.finditer(titulo or ""):
        nome = m.group(0)
        partes = norm(nome).split()
        if norm(nome) in CLUBES or norm(nome) in LUGARES:
            continue
        if partes[0] in NAO_NOMES or partes[0] in CLUBES:
            if len(partes) == 2 and partes[1] not in NAO_NOMES and partes[1] not in CLUBES:
                nome = nome.split()[-1]  # "Santos Barreal" -> "Barreal"
            else:
                continue
        if partes[-1] in NAO_NOMES or partes[-1] in CLUBES:
            nome = nome.split()[0]  # "Cuca Santos" -> "Cuca"
            if norm(nome) in NAO_NOMES or norm(nome) in CLUBES:
                continue
        nome = APELIDOS.get(nome, nome)
        if nome not in nomes:
            nomes.append(nome)
    return nomes


# ---------------------------------------------------------------- histórias (agrupamento)

PALAVRAS_VAZIAS = set("""
a o as os um uma de da do das dos em no na nos nas e ou para por pelo pela com sem que se ao aos
apos sobre x vs santos peixe contra diz ve tem foi sera como mais nao seu sua the
onde assistir vivo horario escalacoes escalacao provaveis veja saiba tudo jogo brasileirao campeonato
brasileiro rodada pelo pela red bull
""".split())
ADVERSARIOS_TOKENS = {c for c in CLUBES if " " not in c} | {"sao", "ponte", "atletico"}


def tokens_do_titulo(titulo: str) -> frozenset:
    palavras = re.findall(r"[a-z0-9]+", norm(titulo))
    return frozenset(p for p in palavras if len(p) > 2 and p not in PALAVRAS_VAZIAS)


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _mesma_historia(a: dict, b: dict) -> bool:
    clubes_a, clubes_b = a["tokens"] & ADVERSARIOS_TOKENS, b["tokens"] & ADVERSARIOS_TOKENS
    if clubes_a and clubes_b and not clubes_a & clubes_b:
        return False  # adversários diferentes nunca são o mesmo fato
    if a["tema"] == b["tema"] == "Serviço de jogo":
        return bool(clubes_a and clubes_a == clubes_b)  # "onde assistir" do mesmo jogo
    return min(len(a["tokens"]), len(b["tokens"])) >= 3 and _jaccard(a["tokens"], b["tokens"]) >= SIMILARIDADE_MIN


def agrupar_historias(linhas: list[dict]) -> dict[int, int]:
    """Cada notícia entra na primeira história cuja notícia inicial (até 3 dias antes) seja parecida.

    Comparar só com a inicial evita o encadeamento A~B~C, que juntaria assuntos diferentes.
    Retorna {id da notícia: id da história}.
    """
    lideres: list[dict] = []
    historias = {}
    for l in sorted(linhas, key=lambda x: x["quando"]):
        historia = None
        for lider in reversed(lideres):
            if (l["quando"] - lider["quando"]).total_seconds() > JANELA_HISTORIA_DIAS * 86400:
                break
            if _mesma_historia(lider, l):
                historia = lider["id"]
                break
        if historia is None:
            lideres.append(l)
            historia = l["id"]
        historias[l["id"]] = historia
    return historias


# ---------------------------------------------------------------- pontuação

def pontos_repercussao(veiculos: int) -> float:
    """1 veículo = 0; 2 = 8,3; 4 = 16,7; 8 ou mais = 25."""
    return 25 * min(1.0, math.log2(max(veiculos, 1)) / 3)


def pontos_recencia(idade_dias: float) -> float:
    return 20 * 0.5 ** (max(idade_dias, 0) / MEIA_VIDA_DIAS)


def recalcular(con, agora: datetime) -> int:
    """Reclassifica toda a base: a recência e a repercussão mudam a cada execução."""
    linhas = []
    for r in con.execute("SELECT id, titulo, resumo, url, fonte, publicado_em FROM noticias"):
        l = dict(r)
        l["foco"], motivo = avaliar_foco(l["titulo"], l["resumo"] or "", l["url"], l["fonte"])
        if l["foco"] == 0:  # regras mudaram: sai da base e fica auditável em descartes
            con.execute("INSERT OR REPLACE INTO descartes (url, titulo, fonte, motivo, visto_em) VALUES (?,?,?,?,?)",
                        (l["url"], l["titulo"], l["fonte"], motivo, agora.isoformat()))
            con.execute("DELETE FROM noticias WHERE id=?", (l["id"],))
            continue
        l["quando"] = datetime.fromisoformat(l["publicado_em"])
        l["tokens"] = tokens_do_titulo(l["titulo"])
        l["tema"], l["tema_pts"] = classificar_tema(l["titulo"], l["resumo"] or "")
        linhas.append(l)

    con.execute("DELETE FROM descartes WHERE url IN (SELECT url FROM noticias)")  # hoje aceitos pelas regras
    for l in linhas:
        l["sentimento"] = ("neutro", 0.0, []) if l["tema"] == "Serviço de jogo" else analisar_sentimento(l["titulo"])
    # O modelo só é consultado onde as regras não decidiram; textos de serviço continuam neutros.
    probs = sentimento_ia.probabilidades(
        con, [l["titulo"] for l in linhas if l["tema"] != "Serviço de jogo" and l["sentimento"][0] == "neutro"])

    historias = agrupar_historias(linhas)
    veiculos: dict[int, set] = {}
    for l in linhas:
        veiculos.setdefault(historias[l["id"]], set()).add(l["fonte"])

    for l in linhas:
        foco, tema, tema_pts = l["foco"], l["tema"], l["tema_pts"]
        sent, sent_score, termos = l["sentimento"]
        sent, sent_score, origem = sentimento_ia.combinar(sent, sent_score, probs.get(l["titulo"]))
        hid = historias[l["id"]]
        n = len(veiculos[hid])
        # Serviço ("onde assistir") sai em todo veículo por padrão: não é repercussão de um fato.
        rep = 0.0 if tema == "Serviço de jogo" else pontos_repercussao(n)
        rec = pontos_recencia((agora - l["quando"]).total_seconds() / 86400)
        con.execute(
            """UPDATE noticias SET foco=?, tema=?, tema_pts=?, repercussao_pts=?, recencia_pts=?,
                   relevancia=?, sentimento=?, sentimento_score=?, sentimento_termos=?, sentimento_origem=?,
                   historia_id=?, veiculos_historia=?, nomes=?
               WHERE id=?""",
            (foco, tema, tema_pts, round(rep, 1), round(rec, 1), round(foco + tema_pts + rep + rec, 1),
             sent, sent_score, json.dumps(termos, ensure_ascii=False), origem, hid, n,
             json.dumps(extrair_nomes(l["titulo"]), ensure_ascii=False), l["id"]),
        )
    return len(linhas)
