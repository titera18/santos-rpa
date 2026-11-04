"""Linguagem do domínio: a notícia e os valores que a descrevem."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

BRT = timezone(timedelta(hours=-3))


class Foco(NamedTuple):
    """Quanto o clube é o assunto da notícia. Zero pontos significa descartar."""
    pontos: float
    motivo: str


class Tema(NamedTuple):
    nome: str
    pontos: float


class Sentimento(NamedTuple):
    """Do ponto de vista do clube, com nota de -1 a 1 e os termos que pesaram nela."""
    rotulo: str
    nota: float
    termos: list[str]


@dataclass
class ItemColetado:
    """O que uma fonte trouxe, antes de passar pelo filtro."""
    titulo: str
    url: str
    fonte: str
    coletor: str
    resumo: str = ""
    publicado_em: datetime | None = None
    data_origem: str = "coleta"


@dataclass
class ResultadoDaFonte:
    """O que aconteceu com uma fonte em uma execução."""
    fonte: str
    status: str
    brutos: int
    aceitos: int
    novos: int
    erro: str | None
    segundos: float


@dataclass
class Noticia:
    """Entidade central: uma notícia aceita e tudo o que se concluiu sobre ela."""
    id: int
    titulo: str
    url: str
    fonte: str
    publicado_em: datetime
    resumo: str = ""
    data_origem: str = "feed"
    foco: float = 0.0
    tema: str = ""
    tema_pts: float = 0.0
    repercussao_pts: float = 0.0
    recencia_pts: float = 0.0
    relevancia: float = 0.0
    sentimento: str = "neutro"
    sentimento_score: float = 0.0
    termos: list[str] = field(default_factory=list)
    sentimento_origem: str = "regras"
    historia_id: int | None = None
    veiculos_historia: int = 1
    nomes: list[str] = field(default_factory=list)

    @property
    def dia(self) -> str:
        """Dia da publicação no horário de Brasília (AAAA-MM-DD)."""
        return self.publicado_em.astimezone(BRT).strftime("%Y-%m-%d")
