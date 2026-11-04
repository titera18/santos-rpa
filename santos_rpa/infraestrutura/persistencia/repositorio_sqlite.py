"""Adaptador da porta RepositorioDeNoticias em SQLite, mais o guarda das previsões do modelo de IA."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from santos_rpa.dominio.modelo import ItemColetado, Noticia, ResultadoDaFonte
from santos_rpa.infraestrutura.persistencia.esquema import ESQUEMA


def conectar(caminho: Path | str) -> sqlite3.Connection:
    con = sqlite3.connect(caminho)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(ESQUEMA)
    colunas = {r["name"] for r in con.execute("PRAGMA table_info(noticias)")}
    if "sentimento_termos" not in colunas:  # bancos criados antes da análise de sentimento
        con.execute("ALTER TABLE noticias ADD COLUMN sentimento_termos TEXT DEFAULT '[]'")
    if "sentimento_origem" not in colunas:  # bancos criados antes do modelo de IA
        con.execute("ALTER TABLE noticias ADD COLUMN sentimento_origem TEXT DEFAULT 'regras'")
    return con


def _noticia(r: sqlite3.Row) -> Noticia:
    return Noticia(
        id=r["id"], titulo=r["titulo"], url=r["url"], fonte=r["fonte"],
        publicado_em=datetime.fromisoformat(r["publicado_em"]), resumo=r["resumo"] or "",
        data_origem=r["data_origem"], foco=r["foco"], tema=r["tema"], tema_pts=r["tema_pts"],
        repercussao_pts=r["repercussao_pts"], recencia_pts=r["recencia_pts"], relevancia=r["relevancia"],
        sentimento=r["sentimento"], sentimento_score=r["sentimento_score"],
        termos=json.loads(r["sentimento_termos"] or "[]"), sentimento_origem=r["sentimento_origem"],
        historia_id=r["historia_id"], veiculos_historia=r["veiculos_historia"], nomes=json.loads(r["nomes"] or "[]"),
    )


class RepositorioSqlite:
    def __init__(self, con: sqlite3.Connection):
        self.con = con

    def confirmar(self) -> None:
        self.con.commit()

    def fechar(self) -> None:
        self.con.close()

    # ------------------------------------------------------------ execuções

    def iniciar_execucao(self, agora: datetime) -> int:
        return self.con.execute("INSERT INTO execucoes (inicio) VALUES (?)", (agora.isoformat(),)).lastrowid

    def registrar_fonte(self, execucao_id: int, r: ResultadoDaFonte) -> None:
        self.con.execute(
            "INSERT INTO execucao_fontes (execucao_id, fonte, status, brutos, aceitos, novos, erro, segundos) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (execucao_id, r.fonte, r.status, r.brutos, r.aceitos, r.novos, r.erro, r.segundos),
        )

    def concluir_execucao(self, execucao_id: int, novas: int, status: str) -> None:
        self.con.execute("UPDATE execucoes SET fim=?, novas=?, status=? WHERE id=?",
                         (datetime.now(timezone.utc).isoformat(), novas, status, execucao_id))

    def inicio_da_primeira_execucao(self) -> str | None:
        return self.con.execute("SELECT MIN(inicio) FROM execucoes").fetchone()[0]

    def contar_execucoes_concluidas(self) -> int:
        return self.con.execute("SELECT COUNT(*) FROM execucoes WHERE fim IS NOT NULL").fetchone()[0]

    def saude_das_fontes(self) -> list[dict]:
        ultima = self.con.execute("SELECT MAX(id) FROM execucoes WHERE fim IS NOT NULL").fetchone()[0]
        if not ultima:
            return []
        return [dict(r) for r in self.con.execute(
            "SELECT fonte, status, brutos, aceitos, novos, erro, segundos FROM execucao_fontes "
            "WHERE execucao_id = ? ORDER BY aceitos DESC", (ultima,))]

    # ------------------------------------------------------------ notícias

    def identificadores_conhecidos(self) -> set[str]:
        conhecidos = {r[0] for r in self.con.execute("SELECT chave FROM noticias")}
        return conhecidos | {r[0] for r in self.con.execute("SELECT url FROM descartes")}

    def existe(self, chave: str) -> bool:
        return self.con.execute("SELECT 1 FROM noticias WHERE chave = ?", (chave,)).fetchone() is not None

    def inserir(self, item: ItemColetado, chave: str, publicado_em: datetime, data_origem: str,
                foco: float, agora: datetime) -> bool:
        """Insere a notícia; se já existe, só atualiza visto_em. Retorna True se for nova.

        Um link direto do veículo substitui o redirecionamento do Google News.
        """
        n = {"chave": chave, "titulo": item.titulo, "resumo": item.resumo, "url": item.url, "fonte": item.fonte,
             "coletor": item.coletor, "publicado_em": publicado_em.isoformat(), "data_origem": data_origem,
             "agora": agora.isoformat(), "foco": foco}
        cur = self.con.execute(
            """INSERT INTO noticias (chave, titulo, resumo, url, fonte, coletor, publicado_em,
                                     data_origem, coletado_em, visto_em, foco)
               VALUES (:chave, :titulo, :resumo, :url, :fonte, :coletor, :publicado_em,
                       :data_origem, :agora, :agora, :foco)
               ON CONFLICT(chave) DO NOTHING""",
            n,
        )
        if cur.rowcount:
            return True
        self.con.execute(
            """UPDATE noticias
                  SET visto_em = :agora,
                      url = CASE WHEN coletor = 'google_news' AND :coletor <> 'google_news'
                                 THEN :url ELSE url END,
                      coletor = CASE WHEN coletor = 'google_news' AND :coletor <> 'google_news'
                                     THEN :coletor ELSE coletor END
                WHERE chave = :chave""",
            n,
        )
        return False

    def listar_para_reclassificar(self) -> list[Noticia]:
        return [_noticia(r) for r in self.con.execute("SELECT * FROM noticias ORDER BY id")]

    def listar_por_relevancia(self) -> list[Noticia]:
        return [_noticia(r) for r in self.con.execute("SELECT * FROM noticias ORDER BY relevancia DESC")]

    def salvar_classificacao(self, n: Noticia) -> None:
        self.con.execute(
            """UPDATE noticias SET foco=?, tema=?, tema_pts=?, repercussao_pts=?, recencia_pts=?,
                   relevancia=?, sentimento=?, sentimento_score=?, sentimento_termos=?, sentimento_origem=?,
                   historia_id=?, veiculos_historia=?, nomes=?
               WHERE id=?""",
            (n.foco, n.tema, n.tema_pts, n.repercussao_pts, n.recencia_pts, n.relevancia,
             n.sentimento, n.sentimento_score, json.dumps(n.termos, ensure_ascii=False), n.sentimento_origem,
             n.historia_id, n.veiculos_historia, json.dumps(n.nomes, ensure_ascii=False), n.id),
        )

    # ------------------------------------------------------------ descartes

    def registrar_descarte(self, url: str, titulo: str, fonte: str, motivo: str, agora: datetime) -> None:
        self.con.execute(
            """INSERT INTO descartes (url, titulo, fonte, motivo, visto_em) VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(url) DO UPDATE SET visto_em = excluded.visto_em, motivo = excluded.motivo""",
            (url, titulo, fonte, motivo, agora.isoformat()),
        )

    def retirar(self, n: Noticia, motivo: str, agora: datetime) -> None:
        self.con.execute("INSERT OR REPLACE INTO descartes (url, titulo, fonte, motivo, visto_em) VALUES (?,?,?,?,?)",
                         (n.url, n.titulo, n.fonte, motivo, agora.isoformat()))
        self.con.execute("DELETE FROM noticias WHERE id=?", (n.id,))

    def esquecer_descartes_aceitos(self) -> None:
        self.con.execute("DELETE FROM descartes WHERE url IN (SELECT url FROM noticias)")

    def contar_descartes(self) -> int:
        return self.con.execute("SELECT COUNT(*) FROM descartes").fetchone()[0]

    # ------------------------------------------------------------ previsões do modelo de IA

    def previsoes_guardadas(self, modelo: str) -> dict[str, dict[str, float]]:
        return {
            r["titulo"]: {"negativo": r["negativo"], "neutro": r["neutro"], "positivo": r["positivo"]}
            for r in self.con.execute(
                "SELECT titulo, negativo, neutro, positivo FROM ia_previsoes WHERE modelo = ?", (modelo,))
        }

    def guardar_previsoes(self, modelo: str, previsoes: dict[str, dict[str, float]]) -> None:
        self.con.executemany(
            "INSERT OR REPLACE INTO ia_previsoes (titulo, modelo, negativo, neutro, positivo) VALUES (?,?,?,?,?)",
            [(t, modelo, p["negativo"], p["neutro"], p["positivo"]) for t, p in previsoes.items()],
        )
