"""Caso de uso: reavaliar toda a base. A recência e a repercussão mudam a cada execução, e as regras podem mudar."""
from datetime import datetime

from santos_rpa.dominio.foco import avaliar_foco
from santos_rpa.dominio.historias import agrupar_historias
from santos_rpa.dominio.modelo import Sentimento
from santos_rpa.dominio.nomes import extrair_nomes
from santos_rpa.dominio.portas import ClassificadorDeSentimento, RepositorioDeNoticias
from santos_rpa.dominio.relevancia import pontos_recencia, pontos_repercussao
from santos_rpa.dominio.sentimento import analisar_sentimento, combinar
from santos_rpa.dominio.tema import SERVICO, classificar_tema


def reclassificar_base(repo: RepositorioDeNoticias, classificador: ClassificadorDeSentimento, agora: datetime) -> int:
    """Retorna quantas notícias ficaram na base."""
    noticias = []
    for n in repo.listar_para_reclassificar():
        n.foco, motivo = avaliar_foco(n.titulo, n.resumo, n.url, n.fonte)
        if n.foco == 0:  # regras mudaram: sai da base e fica auditável em descartes
            repo.retirar(n, motivo, agora)
            continue
        n.tema, n.tema_pts = classificar_tema(n.titulo, n.resumo)
        noticias.append(n)
    repo.esquecer_descartes_aceitos()  # hoje aceitos pelas regras

    regras = {n.id: Sentimento("neutro", 0.0, []) if n.tema == SERVICO else analisar_sentimento(n.titulo)
              for n in noticias}
    # O modelo só é consultado onde as regras não decidiram; textos de serviço continuam neutros.
    probs = classificador.probabilidades(
        [n.titulo for n in noticias if n.tema != SERVICO and regras[n.id].rotulo == "neutro"])

    historias = agrupar_historias(noticias)
    veiculos: dict[int, set] = {}
    for n in noticias:
        veiculos.setdefault(historias[n.id], set()).add(n.fonte)

    for n in noticias:
        regra = regras[n.id]
        n.sentimento, n.sentimento_score, n.sentimento_origem = combinar(regra.rotulo, regra.nota, probs.get(n.titulo))
        n.termos = regra.termos
        n.historia_id = historias[n.id]
        n.veiculos_historia = len(veiculos[n.historia_id])
        # Serviço ("onde assistir") sai em todo veículo por padrão: não é repercussão de um fato.
        repercussao = 0.0 if n.tema == SERVICO else pontos_repercussao(n.veiculos_historia)
        recencia = pontos_recencia((agora - n.publicado_em).total_seconds() / 86400)
        n.repercussao_pts, n.recencia_pts = round(repercussao, 1), round(recencia, 1)
        n.relevancia = round(n.foco + n.tema_pts + repercussao + recencia, 1)
        n.nomes = extrair_nomes(n.titulo)
        repo.salvar_classificacao(n)
    return len(noticias)
