"""Análise dos dados: conclusões em texto, sentimento e o conjunto de dados do dashboard."""
import csv
import json
import re
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

import sentimento_ia
from coletores import BRT
from relevancia import ADVERSARIOS_TOKENS, analisar_sentimento, norm

DIAS_COMPARACAO = 7
SERVICO = "Serviço de jogo"
PASTA_TESTES = Path(__file__).resolve().parent / "tests"
ROTULOS_DE_AVALIACAO = [PASTA_TESTES / "sentimento_teste.csv", PASTA_TESTES / "sentimento_validacao.csv"]
DIAS_APOS_JOGO = 2
PLACAR_ANTES = re.compile(r"\bsantos(?: fc)? (\d+) x (\d+) ([a-z-]+(?: [a-z-]+){0,2})")
PLACAR_DEPOIS = re.compile(r"([a-z-]+(?: [a-z-]+){0,2}) (\d+) x (\d+) santos\b")
NOME_ADVERSARIO = {"sao": "São Paulo", "ponte": "Ponte Preta", "atletico": "Atlético-MG", "gremio": "Grêmio"}


def indice_sentimento(linhas: list[dict]) -> int | None:
    """De -100 (só notícias ruins para o clube) a +100 (só boas). Serviço de jogo fica de fora."""
    validas = [l for l in linhas if l["tema"] != SERVICO]
    if not validas:
        return None
    pos = sum(l["sentimento"] == "positivo" for l in validas)
    neg = sum(l["sentimento"] == "negativo" for l in validas)
    return round(100 * (pos - neg) / len(validas))


def sentimento_por_jogo(linhas: list[dict]) -> list[dict]:
    """Encontra jogos pelos placares nos títulos e mede o sentimento no dia e nos 2 dias seguintes."""
    jogos: dict[tuple, list[str]] = {}
    for l in linhas:
        t = norm(l["titulo"])
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
            jogos.setdefault((rival, gols_santos, gols_rival), []).append(l["dia"])

    resultado = []
    for (rival, gs, gr), dias in jogos.items():
        if len(dias) < 2:  # um único título pode ser placar antigo ou erro
            continue
        inicio = date.fromisoformat(min(dias))
        fim = (inicio + timedelta(days=DIAS_APOS_JOGO)).isoformat()
        janela = [l for l in _periodo(linhas, inicio.isoformat(), fim) if l["tema"] != SERVICO]
        resultado.append({
            "dia": inicio.isoformat(),
            "rival": NOME_ADVERSARIO.get(rival, rival.capitalize()),
            "placar": f"Santos {gs} x {gr}",
            "resultado": "Vitória" if gs > gr else "Derrota" if gs < gr else "Empate",
            "noticias": len(janela),
            "indice": indice_sentimento(janela),
        })
    return sorted(resultado, key=lambda j: j["dia"], reverse=True)


def avaliar_sentimento(con=None) -> dict | None:
    """Compara o classificador com títulos rotulados à mão, que não foram usados para criar as regras.

    Com uma conexão, avalia regras + modelo de IA; sem ela, só as regras.
    """
    rotulados = []
    for caminho in ROTULOS_DE_AVALIACAO:
        if caminho.exists():
            with open(caminho, encoding="utf-8", newline="") as f:
                rotulados += [(l["rotulo"], l["titulo"]) for l in csv.DictReader(f, delimiter=";")]
    if not rotulados:
        return None
    regras = {t: analisar_sentimento(t) for _, t in rotulados}
    probs = sentimento_ia.probabilidades(con, [t for t, r in regras.items() if r[0] == "neutro"]) if con else {}
    pares = [(r, sentimento_ia.combinar(regras[t][0], regras[t][1], probs.get(t))[0]) for r, t in rotulados]
    def taxa(acertos, total):
        return round(100 * acertos / total) if total else 0
    medidas = {"total": len(pares), "acerto": taxa(sum(r == p for r, p in pares), len(pares)),
               "com_ia": bool(probs) and not sentimento_ia.indisponivel}
    for k in ("positivo", "negativo"):
        acertos = sum(r == p == k for r, p in pares)
        medidas[k] = {"precisao": taxa(acertos, sum(p == k for _, p in pares)),
                      "cobertura": taxa(acertos, sum(r == k for r, _ in pares))}
    return medidas


def _dia(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(BRT).strftime("%Y-%m-%d")


def carregar_linhas(con) -> list[dict]:
    linhas = []
    for r in con.execute("SELECT * FROM noticias ORDER BY relevancia DESC"):
        l = dict(r)
        l["dia"] = _dia(l["publicado_em"])
        l["nomes"] = json.loads(l["nomes"] or "[]")
        l["termos"] = json.loads(l["sentimento_termos"] or "[]")
        linhas.append(l)
    return linhas


def _periodo(linhas, inicio, fim):
    return [l for l in linhas if inicio <= l["dia"] <= fim]


def _pct(parte, total):
    return round(100 * parte / total) if total else 0


def gerar_conclusoes(linhas: list[dict], agora: datetime, primeira_coleta: str | None) -> list[str]:
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

    temas = Counter(l["tema"] for l in atual)
    tema, qtd = temas.most_common(1)[0]
    frases.append(f"O tema mais noticiado foi {tema}, com {qtd} notícias ({_pct(qtd, len(atual))}% do total).")

    com_opiniao = [l for l in atual if l["tema"] != SERVICO]
    neg = sum(l["sentimento"] == "negativo" for l in com_opiniao)
    pos = sum(l["sentimento"] == "positivo" for l in com_opiniao)
    if com_opiniao:
        indice = indice_sentimento(com_opiniao)
        frases.append(f"O índice de sentimento é {indice:+d}, numa escala de -100 a +100: "
                      f"{_pct(neg, len(com_opiniao))}% dos títulos são ruins para o clube e "
                      f"{_pct(pos, len(com_opiniao))}% são bons.")

    negativos_tema = Counter(l["tema"] for l in com_opiniao if l["sentimento"] == "negativo")
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
    for hid, ns in {(l["historia_id"], n): None for l in atual for n in l["nomes"]}:
        nomes[ns] += 1
    if nomes:
        top = ", ".join(f"{n} ({q})" for n, q in nomes.most_common(3))
        frases.append(f"Pessoas mais citadas, em histórias distintas: {top}.")

    fatos = [l for l in atual if l["tema"] != "Serviço de jogo"]
    melhor = max(fatos, key=lambda l: (l["veiculos_historia"], l["relevancia"]), default=None)
    if melhor and melhor["veiculos_historia"] > 1:
        frases.append(f"A história de maior repercussão saiu em {melhor['veiculos_historia']} veículos: "
                      f"“{melhor['titulo']}”.")
    return frases


def saude_das_fontes(con) -> list[dict]:
    ultima = con.execute("SELECT MAX(id) FROM execucoes WHERE fim IS NOT NULL").fetchone()[0]
    if not ultima:
        return []
    return [dict(r) for r in con.execute(
        "SELECT fonte, status, brutos, aceitos, novos, erro, segundos FROM execucao_fontes "
        "WHERE execucao_id = ? ORDER BY aceitos DESC", (ultima,))]


def montar_dados(con, agora: datetime) -> dict:
    linhas = carregar_linhas(con)
    primeira = con.execute("SELECT MIN(inicio) FROM execucoes").fetchone()[0]
    primeira_dia = _dia(primeira) if primeira else None
    execucoes = con.execute("SELECT COUNT(*) FROM execucoes WHERE fim IS NOT NULL").fetchone()[0]
    descartes = con.execute("SELECT COUNT(*) FROM descartes").fetchone()[0]
    return {
        "gerado_em": agora.astimezone(BRT).strftime("%d/%m/%Y às %H:%M"),
        "hoje": agora.astimezone(BRT).strftime("%Y-%m-%d"),
        "primeira_coleta": primeira_dia,
        "execucoes": execucoes,
        "descartes": descartes,
        "conclusoes": gerar_conclusoes(linhas, agora, primeira_dia),
        "fontes": saude_das_fontes(con),
        "jogos": sentimento_por_jogo(linhas),
        "avaliacao": avaliar_sentimento(con),
        "decididas_por_ia": sum(l["sentimento_origem"] == "ia" for l in linhas),
        "noticias": [
            {
                "id": l["id"], "t": l["titulo"], "u": l["url"], "f": l["fonte"], "d": l["dia"],
                "tm": l["tema"], "s": l["sentimento"], "sc": l["sentimento_score"], "st": l["termos"],
                "r": l["relevancia"],
                "c": [l["foco"], l["tema_pts"], l["repercussao_pts"], l["recencia_pts"]],
                "h": l["historia_id"], "n": l["veiculos_historia"], "nm": l["nomes"],
                "e": l["data_origem"] == "coleta",
            }
            for l in linhas
        ],
    }
