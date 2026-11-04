"""Relevância de 0 a 100, a soma de quatro componentes que podem ser explicados:

    foco         0-30  o clube é o assunto principal ou só é citado?
    tema         0-25  o assunto afeta o clube (SAF, mercado) ou é serviço (onde assistir)?
    repercussão  0-25  quantos veículos diferentes cobriram a mesma história?
    recência     0-20  cai pela metade a cada 3 dias
"""
import math

MEIA_VIDA_DIAS = 3

def pontos_repercussao(veiculos: int) -> float:
    """1 veículo = 0; 2 = 8,3; 4 = 16,7; 8 ou mais = 25."""
    return 25 * min(1.0, math.log2(max(veiculos, 1)) / 3)


def pontos_recencia(idade_dias: float) -> float:
    return 20 * 0.5 ** (max(idade_dias, 0) / MEIA_VIDA_DIAS)
