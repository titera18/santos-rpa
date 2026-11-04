"""Caso de uso: medir o classificador em títulos rotulados à mão, que não foram usados para criar as regras."""
from santos_rpa.dominio.portas import ClassificadorDeSentimento
from santos_rpa.dominio.sentimento import analisar_sentimento, combinar


def _taxa(acertos: int, total: int) -> int:
    return round(100 * acertos / total) if total else 0


def avaliar_sentimento(rotulados: list[tuple[str, str]], classificador: ClassificadorDeSentimento | None = None) -> dict | None:
    """Recebe pares (rótulo, título). Com um classificador, avalia regras + modelo de IA; sem ele, só as regras."""
    if not rotulados:
        return None
    regras = {titulo: analisar_sentimento(titulo) for _, titulo in rotulados}
    probs = {}
    if classificador:
        probs = classificador.probabilidades([t for t, r in regras.items() if r.rotulo == "neutro"])
    pares = [(rotulo, combinar(regras[t].rotulo, regras[t].nota, probs.get(t))[0]) for rotulo, t in rotulados]
    medidas = {"total": len(pares), "acerto": _taxa(sum(r == p for r, p in pares), len(pares)),
               "com_ia": bool(probs) and not classificador.indisponivel}
    for k in ("positivo", "negativo"):
        acertos = sum(r == p == k for r, p in pares)
        medidas[k] = {"precisao": _taxa(acertos, sum(p == k for _, p in pares)),
                      "cobertura": _taxa(acertos, sum(r == k for r, _ in pares))}
    return medidas
