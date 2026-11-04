"""Caso de uso: reunir os dados que o dashboard exibe."""
from datetime import datetime

from santos_rpa.aplicacao.avaliar_sentimento import avaliar_sentimento
from santos_rpa.dominio.analise import gerar_conclusoes, sentimento_por_jogo
from santos_rpa.dominio.modelo import BRT
from santos_rpa.dominio.portas import ClassificadorDeSentimento, RepositorioDeNoticias


def _dia(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(BRT).strftime("%Y-%m-%d")


def montar_painel(repo: RepositorioDeNoticias, classificador: ClassificadorDeSentimento,
                  rotulados: list[tuple[str, str]], agora: datetime) -> dict:
    noticias = repo.listar_por_relevancia()
    primeira = repo.inicio_da_primeira_execucao()
    primeira_dia = _dia(primeira) if primeira else None
    return {
        "gerado_em": agora.astimezone(BRT).strftime("%d/%m/%Y às %H:%M"),
        "hoje": agora.astimezone(BRT).strftime("%Y-%m-%d"),
        "primeira_coleta": primeira_dia,
        "execucoes": repo.contar_execucoes_concluidas(),
        "descartes": repo.contar_descartes(),
        "conclusoes": gerar_conclusoes(noticias, agora, primeira_dia),
        "fontes": repo.saude_das_fontes(),
        "jogos": sentimento_por_jogo(noticias),
        "avaliacao": avaliar_sentimento(rotulados, classificador),
        "decididas_por_ia": sum(n.sentimento_origem == "ia" for n in noticias),
        "noticias": [
            {
                "id": n.id, "t": n.titulo, "u": n.url, "f": n.fonte, "d": n.dia,
                "tm": n.tema, "s": n.sentimento, "sc": n.sentimento_score, "st": n.termos,
                "r": n.relevancia,
                "c": [n.foco, n.tema_pts, n.repercussao_pts, n.recencia_pts],
                "h": n.historia_id, "n": n.veiculos_historia, "nm": n.nomes,
                "e": n.data_origem == "coleta",
            }
            for n in noticias
        ],
    }
