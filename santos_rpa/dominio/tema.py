"""De que assunto a notícia trata e quanto esse assunto pesa para o clube."""
import re

from santos_rpa.dominio.modelo import Tema
from santos_rpa.dominio.texto import norm

SERVICO = "Serviço de jogo"

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
TEMA_PADRAO = Tema("Outros", 5)


def classificar_tema(titulo: str, resumo: str) -> Tema:
    t, r = norm(titulo), norm(resumo)
    for texto in (t, r):  # o título tem prioridade sobre o resumo
        for nome, pts, rx in TEMAS:
            if rx.search(texto):
                return Tema(nome, pts)
    return TEMA_PADRAO
