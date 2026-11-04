"""Clubes adversários, usados para separar notícias do Santos das de outros times."""
import re

from santos_rpa.dominio.texto import norm

CLUBES = set(norm(x) for x in """
Palmeiras Corinthians Flamengo Fluminense Vasco Botafogo Grêmio Cruzeiro Internacional Bragantino
Mirassol Bahia Atlético Vitória Coritiba Remo Fortaleza Ceará Sport Juventude Chapecoense Ponte Preta
Athletico Ajax Guarani Portuguesa
""".split()) | {"sao paulo", "red bull", "ponte preta", "santo andre", "atletico-mg", "rb bragantino"}
ADVERSARIOS_TOKENS = {c for c in CLUBES if " " not in c} | {"sao", "ponte", "atletico"}
# "vitória" e "sport" também são palavras comuns: não servem para concluir que um título cita outro clube.
OUTROS_CLUBES = re.compile(r"\b(" + "|".join(sorted(map(re.escape, CLUBES - {"vitoria", "sport"}), key=len, reverse=True)) + r")\b")
