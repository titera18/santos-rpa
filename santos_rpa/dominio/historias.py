"""Agrupa notícias sobre o mesmo fato, para medir a repercussão."""
import re
from dataclasses import dataclass
from datetime import datetime

from santos_rpa.dominio.clubes import ADVERSARIOS_TOKENS
from santos_rpa.dominio.modelo import Noticia
from santos_rpa.dominio.tema import SERVICO
from santos_rpa.dominio.texto import norm

JANELA_HISTORIA_DIAS = 3
SIMILARIDADE_MIN = 0.45
PALAVRAS_VAZIAS = set("""
a o as os um uma de da do das dos em no na nos nas e ou para por pelo pela com sem que se ao aos
apos sobre x vs santos peixe contra diz ve tem foi sera como mais nao seu sua the
onde assistir vivo horario escalacoes escalacao provaveis veja saiba tudo jogo brasileirao campeonato
brasileiro rodada pelo pela red bull
""".split())


@dataclass(frozen=True)
class _Candidata:
    id: int
    quando: datetime
    tokens: frozenset
    tema: str


def tokens_do_titulo(titulo: str) -> frozenset:
    palavras = re.findall(r"[a-z0-9]+", norm(titulo))
    return frozenset(p for p in palavras if len(p) > 2 and p not in PALAVRAS_VAZIAS)


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _mesma_historia(a: _Candidata, b: _Candidata) -> bool:
    clubes_a, clubes_b = a.tokens & ADVERSARIOS_TOKENS, b.tokens & ADVERSARIOS_TOKENS
    if clubes_a and clubes_b and not clubes_a & clubes_b:
        return False  # adversários diferentes nunca são o mesmo fato
    if a.tema == b.tema == SERVICO:
        return bool(clubes_a and clubes_a == clubes_b)  # "onde assistir" do mesmo jogo
    return min(len(a.tokens), len(b.tokens)) >= 3 and _jaccard(a.tokens, b.tokens) >= SIMILARIDADE_MIN


def agrupar_historias(noticias: list[Noticia]) -> dict[int, int]:
    """Cada notícia entra na primeira história cuja notícia inicial (até 3 dias antes) seja parecida.

    Comparar só com a inicial evita o encadeamento A~B~C, que juntaria assuntos diferentes.
    Retorna {id da notícia: id da história}.
    """
    candidatas = [_Candidata(n.id, n.publicado_em, tokens_do_titulo(n.titulo), n.tema) for n in noticias]
    lideres: list[_Candidata] = []
    historias = {}
    for atual in sorted(candidatas, key=lambda c: c.quando):
        historia = None
        for lider in reversed(lideres):
            if (atual.quando - lider.quando).total_seconds() > JANELA_HISTORIA_DIAS * 86400:
                break
            if _mesma_historia(lider, atual):
                historia = lider.id
                break
        if historia is None:
            lideres.append(atual)
            historia = atual.id
        historias[atual.id] = historia
    return historias
