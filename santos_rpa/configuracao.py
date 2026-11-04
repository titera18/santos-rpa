"""Onde ficam os arquivos do projeto."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PASTA_DADOS = RAIZ / "dados"
CAMINHO_BANCO = PASTA_DADOS / "santos_noticias.db"
CAMINHO_DASHBOARD = PASTA_DADOS / "dashboard.html"
PASTA_MODELOS = PASTA_DADOS / "modelos"
PASTA_LOGS = RAIZ / "logs"
PASTA_AVALIACAO = RAIZ / "avaliacao"
ROTULOS_DE_AVALIACAO = [PASTA_AVALIACAO / "sentimento_teste.csv", PASTA_AVALIACAO / "sentimento_validacao.csv"]
HOST_PAINEL = "127.0.0.1"
PORTA_PAINEL = 8765
