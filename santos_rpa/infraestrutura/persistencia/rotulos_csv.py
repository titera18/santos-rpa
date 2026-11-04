"""Lê os títulos rotulados à mão usados para medir o sentimento."""
import csv
from pathlib import Path


def carregar_rotulos(caminhos: list[Path]) -> list[tuple[str, str]]:
    """Retorna pares (rótulo, título). Arquivos ausentes são ignorados."""
    rotulados = []
    for caminho in caminhos:
        if caminho.exists():
            with open(caminho, encoding="utf-8", newline="") as f:
                rotulados += [(l["rotulo"], l["titulo"]) for l in csv.DictReader(f, delimiter=";")]
    return rotulados
