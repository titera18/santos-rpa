"""O que os dados dizem: índice de sentimento, efeito de cada jogo e conclusões em texto."""
import re
from collections import Counter
from datetime import date, datetime, timedelta

from santos_rpa.dominio.clubes import ADVERSARIOS_TOKENS
from santos_rpa.dominio.modelo import BRT, Noticia
from santos_rpa.dominio.tema import SERVICO
from santos_rpa.dominio.texto import norm

DIAS_COMPARACAO = 7
DIAS_APOS_JOGO = 2

PLACAR_ANTES = re.compile(r"\bsantos(?: fc)? (\d+) x (\d+) ([a-z-]+(?: [a-z-]+){0,2})")
PLACAR_DEPOIS = re.compile(r"([a-z-]+(?: [a-z-]+){0,2}) (\d+) x (\d+) santos\b")
NOME_ADVERSARIO = {"sao": "São Paulo", "ponte": "Ponte Preta", "atletico": "Atlético-MG", "gremio": "Grêmio"}


def indice_sentimento(linhas: list[Noticia]) -> int | None:
    """De -100 (só notícias ruins para o clube) a +100 (só boas). Serviço de jogo fica de fora."""
    validas = [l for l in linhas if l.tema != SERVICO]
    if not validas:
        return None
    pos = sum(l.sentimento == "positivo" for l in validas)
    neg = sum(l.sentimento == "negativo" for l in validas)
    return round(100 * (pos - neg) / len(validas))


def sentimento_por_jogo(linhas: list[Noticia]) -> list[dict]:
    """Encontra jogos pelos placares nos títulos e mede o sentimento no dia e nos 2 dias seguintes."""
    jogos: dict[tuple, list[str]] = {}
    for l in linhas:
        t = norm(l.titulo)
        m = PLACAR_ANTES.search(t)
        if m:
            gols_santos, gols_rival, trecho = int(m[1]), int(m[2]), m[3]
        else:
            m = PLACAR_DEPOIS.search(t)
            if not m:
                continue
            trecho, gols_rival, gols_santos = m[1], int(m[2]), int(m[3])
        rival = next((p for p in trecho.split() if p in ADVERSARIOS_TOKENS), None)
        if rival:
            jogos.setdefault((rival, gols_santos, gols_rival), []).append(l.dia)

    resultado = []
    for (rival, gs, gr), dias in jogos.items():
        if len(dias) < 2:  # um único título pode ser placar antigo ou erro
            continue
        inicio = date.fromisoformat(min(dias))
        fim = (inicio + timedelta(days=DIAS_APOS_JOGO)).isoformat()
        janela = [l for l in _periodo(linhas, inicio.isoformat(), fim) if l.tema != SERVICO]
        resultado.append({
            "dia": inicio.isoformat(),
            "rival": NOME_ADVERSARIO.get(rival, rival.capitalize()),
            "placar": f"Santos {gs} x {gr}",
            "resultado": "Vitória" if gs > gr else "Derrota" if gs < gr else "Empate",
            "noticias": len(janela),
            "indice": indice_sentimento(janela),
        })
    return sorted(resultado, key=lambda j: j["dia"], reverse=True)
def _periodo(linhas, inicio, fim):
    return [l for l in linhas if inicio <= l.dia <= fim]


def _pct(parte, total):
    return round(100 * parte / total) if total else 0


def gerar_conclusoes(linhas: list[Noticia], agora: datetime, primeira_coleta: str | None) -> list[str]:
    """Frases sobre os últimos 7 dias, comparados aos 7 dias anteriores."""
    hoje = agora.astimezone(BRT).date()
    ini = (hoje - timedelta(days=DIAS_COMPARACAO - 1)).isoformat()
    fim_ant = (hoje - timedelta(days=DIAS_COMPARACAO)).isoformat()
    ini_ant = (hoje - timedelta(days=2 * DIAS_COMPARACAO - 1)).isoformat()
    atual = _periodo(linhas, ini, hoje.isoformat())
    anterior = _periodo(linhas, ini_ant, fim_ant)
    if not atual:
        return ["Nenhuma notícia nos últimos 7 dias."]

    frases = []
    # A comparação só é justa se o robô já estava coletando no período anterior.
    comparavel = primeira_coleta is not None and primeira_coleta <= ini_ant
    if comparavel and anterior:
        var = _pct(len(atual) - len(anterior), len(anterior))
        frases.append(f"Foram {len(atual)} notícias em 7 dias, {abs(var)}% {'a mais' if var >= 0 else 'a menos'} "
                      f"que nos 7 dias anteriores ({len(anterior)}).")
    else:
        frases.append(f"Foram {len(atual)} notícias em 7 dias. A comparação com a semana anterior só será "
                      f"confiável após 14 dias de coleta, pois o histórico inicial é parcial.")

    temas = Counter(l.tema for l in atual)
    tema, qtd = temas.most_common(1)[0]
    frases.append(f"O tema mais noticiado foi {tema}, com {qtd} notícias ({_pct(qtd, len(atual))}% do total).")

    com_opiniao = [l for l in atual if l.tema != SERVICO]
    neg = sum(l.sentimento == "negativo" for l in com_opiniao)
    pos = sum(l.sentimento == "positivo" for l in com_opiniao)
    if com_opiniao:
        indice = indice_sentimento(com_opiniao)
        frases.append(f"O índice de sentimento é {indice:+d}, numa escala de -100 a +100: "
                      f"{_pct(neg, len(com_opiniao))}% dos títulos são ruins para o clube e "
                      f"{_pct(pos, len(com_opiniao))}% são bons.")

    negativos_tema = Counter(l.tema for l in com_opiniao if l.sentimento == "negativo")
    if negativos_tema:
        t, q = negativos_tema.most_common(1)[0]
        frases.append(f"A maior parte dos títulos negativos vem de {t} ({q} de {neg}).")

    jogos = [j for j in sentimento_por_jogo(linhas) if j["indice"] is not None and j["noticias"] >= 5]
    if len(jogos) >= 2:
        pior, melhor_jogo = min(jogos, key=lambda j: j["indice"]), max(jogos, key=lambda j: j["indice"])
        frases.append(f"Entre os jogos encontrados, o pior momento veio após {pior['placar']} ({pior['rival']}), "
                      f"com índice {pior['indice']:+d}, e o melhor após {melhor_jogo['placar']} "
                      f"({melhor_jogo['rival']}), com {melhor_jogo['indice']:+d}.")

    # Cada história conta uma vez para cada nome.
    nomes = Counter()
    for hid, ns in {(l.historia_id, n): None for l in atual for n in l.nomes}:
        nomes[ns] += 1
    if nomes:
        top = ", ".join(f"{n} ({q})" for n, q in nomes.most_common(3))
        frases.append(f"Pessoas mais citadas, em histórias distintas: {top}.")

    fatos = [l for l in atual if l.tema != "Serviço de jogo"]
    melhor = max(fatos, key=lambda l: (l.veiculos_historia, l.relevancia), default=None)
    if melhor and melhor.veiculos_historia > 1:
        frases.append(f"A história de maior repercussão saiu em {melhor.veiculos_historia} veículos: "
                      f"“{melhor.titulo}”.")
    return frases
