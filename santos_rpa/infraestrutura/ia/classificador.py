"""Adaptador da porta ClassificadorDeSentimento: guarda as previsões e tolera a falha do modelo."""
import logging

log = logging.getLogger("rpa.ia")


class ClassificadorComCache:
    def __init__(self, modelo, repo):
        self.modelo = modelo
        self.repo = repo
        self.indisponivel = False

    def probabilidades(self, titulos: list[str]) -> dict[str, dict[str, float]]:
        """Previsões dos títulos, usando o que já está no banco. Sem o modelo, devolve só o que há no banco."""
        titulos = sorted(set(titulos))
        guardadas = self.repo.previsoes_guardadas(self.modelo.nome)
        faltando = [t for t in titulos if t not in guardadas]
        if faltando:
            try:
                novas = self.modelo.prever(faltando)
            except Exception as e:  # uma falha do modelo não pode derrubar o robô
                log.warning("Modelo de IA indisponível; %d títulos ficam só com as regras: %s", len(faltando), e)
                self.indisponivel = True
                novas = {}
            self.repo.guardar_previsoes(self.modelo.nome, novas)
            guardadas.update(novas)
        return {t: guardadas[t] for t in titulos if t in guardadas}
