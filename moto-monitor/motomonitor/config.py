"""Leitura do config.json (criado a partir do config.exemplo.json na 1ª execução)."""
import json
import shutil
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO = RAIZ / "config.json"
EXEMPLO = RAIZ / "config.exemplo.json"

PADRAO = {
    "intervalo_minutos": 30,
    "porta": 8765,
    "banco": "dados/motos.db",
    "cidades": [],
    "estilos_ativos": ["custom", "classica", "estradeira"],
    "modelos_desativados": [],
    "modelos_extras": [],
    "fontes": {"olx": {"ativa": True}, "mercadolivre": {"ativa": True}},
    "regras": {
        "preco_alvo": 18000,
        "desconto_fipe": 0.10,
        "teto_fipe": 30000,
        "preco_minimo_plausivel": 4000,
        "preco_maximo_coleta": 35000,
    },
    "fipe": {"url_base": "https://parallelum.com.br/fipe/api/v1/motos", "token": ""},
    "notificacoes": {"desktop": True, "telegram": {"ativo": False, "token": "", "chat_id": ""}},
    "pausa_entre_requisicoes": [2, 5],
}


def _mesclar(base: dict, extra: dict) -> dict:
    saida = dict(base)
    for chave, valor in extra.items():
        if isinstance(valor, dict) and isinstance(saida.get(chave), dict):
            saida[chave] = _mesclar(saida[chave], valor)
        else:
            saida[chave] = valor
    return saida


def carregar(caminho: Path | None = None) -> dict:
    caminho = Path(caminho) if caminho else ARQUIVO
    if not caminho.exists() and caminho == ARQUIVO and EXEMPLO.exists():
        shutil.copy(EXEMPLO, ARQUIVO)
    dados = {}
    if caminho.exists():
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    cfg = _mesclar(PADRAO, dados)
    banco = Path(cfg["banco"])
    if not banco.is_absolute():
        banco = RAIZ / banco
    cfg["banco"] = str(banco)
    return cfg
