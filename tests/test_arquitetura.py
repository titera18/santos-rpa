"""Garante a regra das camadas do DDD: as dependências só apontam para dentro, em direção ao domínio."""
import ast
import importlib
import unittest
from pathlib import Path

PACOTE = Path(__file__).resolve().parents[1] / "santos_rpa"
BIBLIOTECAS_EXTERNAS = {"requests", "bs4", "feedparser", "lxml", "transformers", "torch", "urllib3"}
ACESSO_AO_MUNDO_EXTERNO = {"sqlite3", "http", "socket", "urllib", "os", "pathlib", "csv"} | BIBLIOTECAS_EXTERNAS


def importacoes(arquivo: Path) -> set[str]:
    nomes = set()
    for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
        if isinstance(no, ast.Import):
            nomes |= {a.name for a in no.names}
        elif isinstance(no, ast.ImportFrom) and no.module:
            nomes.add(no.module)
    return nomes


def modulos(camada: str):
    return list((PACOTE / camada).rglob("*.py"))


class Camadas(unittest.TestCase):
    def test_todos_os_modulos_carregam(self):
        for arquivo in PACOTE.rglob("*.py"):
            if arquivo.name != "__main__.py":
                relativo = arquivo.relative_to(PACOTE.parent).with_suffix("")
                importlib.import_module(".".join(relativo.parts).removesuffix(".__init__"))

    def test_camadas_existem(self):
        for camada in ("dominio", "aplicacao", "infraestrutura", "interfaces"):
            self.assertTrue(modulos(camada), camada)

    def test_dominio_nao_depende_de_nada_externo(self):
        for arquivo in modulos("dominio"):
            for nome in importacoes(arquivo):
                self.assertNotIn(nome.split(".")[0], ACESSO_AO_MUNDO_EXTERNO, f"{arquivo.name} importa {nome}")
                if nome.startswith("santos_rpa"):
                    self.assertTrue(nome.startswith("santos_rpa.dominio"), f"{arquivo.name} importa {nome}")

    def test_aplicacao_so_depende_do_dominio(self):
        for arquivo in modulos("aplicacao"):
            for nome in importacoes(arquivo):
                self.assertNotIn(nome.split(".")[0], BIBLIOTECAS_EXTERNAS | {"sqlite3"}, f"{arquivo.name} importa {nome}")
                if nome.startswith("santos_rpa"):
                    self.assertTrue(nome.startswith(("santos_rpa.dominio", "santos_rpa.aplicacao")),
                                    f"{arquivo.name} importa {nome}")

    def test_infraestrutura_nao_depende_da_aplicacao_nem_das_interfaces(self):
        for arquivo in modulos("infraestrutura"):
            for nome in importacoes(arquivo):
                self.assertFalse(nome.startswith(("santos_rpa.aplicacao", "santos_rpa.interfaces")),
                                 f"{arquivo.name} importa {nome}")
