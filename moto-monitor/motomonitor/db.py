"""Banco SQLite: anúncios, histórico de preço, alertas, cache da FIPE e coletas."""
import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

ESQUEMA = """
CREATE TABLE IF NOT EXISTS anuncios (
    id TEXT PRIMARY KEY,
    fonte TEXT, url TEXT, titulo TEXT, imagem TEXT,
    preco INTEGER, ano INTEGER, km INTEGER, cidade TEXT,
    modelo_chave TEXT, modelo_nome TEXT, estilo TEXT,
    fipe REAL, fipe_ref TEXT, desconto REAL,
    motivos TEXT, alerta INTEGER DEFAULT 0, oculto INTEGER DEFAULT 0,
    primeira_vez TEXT, ultima_vez TEXT
);
CREATE TABLE IF NOT EXISTS precos (
    anuncio_id TEXT, preco INTEGER, quando TEXT
);
CREATE TABLE IF NOT EXISTS alertas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    anuncio_id TEXT, preco INTEGER, motivos TEXT, quando TEXT, lido INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS fipe_cache (
    chave TEXT PRIMARY KEY, valor TEXT, quando TEXT
);
CREATE TABLE IF NOT EXISTS coletas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inicio TEXT, fim TEXT, vistos INTEGER, novos INTEGER, alertas INTEGER, erros TEXT
);
CREATE INDEX IF NOT EXISTS idx_precos ON precos(anuncio_id);
"""


def agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Banco:
    def __init__(self, caminho: str):
        if caminho != ":memory:":
            Path(caminho).parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(caminho, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.trava = threading.RLock()
        with self.trava:
            self.con.executescript(ESQUEMA)

    # ------------------------------------------------------------ anúncios
    def salvar_anuncio(self, a: dict) -> tuple[bool, int | None]:
        """Insere/atualiza. Devolve (é_novo, preço_anterior)."""
        with self.trava, self.con:
            atual = self.con.execute("SELECT preco FROM anuncios WHERE id=?", (a["id"],)).fetchone()
            momento = agora()
            campos = ["fonte", "url", "titulo", "imagem", "preco", "ano", "km", "cidade",
                      "modelo_chave", "modelo_nome", "estilo", "fipe", "fipe_ref",
                      "desconto", "motivos", "alerta"]
            valores = [a.get(c) for c in campos]
            if atual is None:
                self.con.execute(
                    f"INSERT INTO anuncios (id, {', '.join(campos)}, primeira_vez, ultima_vez) "
                    f"VALUES (?, {', '.join('?' * len(campos))}, ?, ?)",
                    [a["id"], *valores, momento, momento])
                self.con.execute("INSERT INTO precos VALUES (?, ?, ?)", (a["id"], a["preco"], momento))
                return True, None
            self.con.execute(
                f"UPDATE anuncios SET {', '.join(c + '=?' for c in campos)}, ultima_vez=? WHERE id=?",
                [*valores, momento, a["id"]])
            if atual["preco"] != a["preco"]:
                self.con.execute("INSERT INTO precos VALUES (?, ?, ?)", (a["id"], a["preco"], momento))
            return False, atual["preco"]

    def anuncios(self, apenas_alertas=False, estilo=None, fonte=None, preco_max=None,
                 incluir_ocultos=False, dias=None, ordem="desconto") -> list[dict]:
        sql = "SELECT * FROM anuncios WHERE 1=1"
        args = []
        if apenas_alertas:
            sql += " AND alerta=1"
        if not incluir_ocultos:
            sql += " AND oculto=0"
        if estilo:
            sql += " AND estilo=?"; args.append(estilo)
        if fonte:
            sql += " AND fonte=?"; args.append(fonte)
        if preco_max:
            sql += " AND preco<=?"; args.append(int(preco_max))
        if dias:
            sql += " AND ultima_vez >= datetime('now', 'localtime', ?)"; args.append(f"-{int(dias)} days")
        ordens = {
            "desconto": "COALESCE(desconto, -99) DESC, preco ASC",
            "preco": "preco ASC",
            "recentes": "primeira_vez DESC",
        }
        sql += " ORDER BY " + ordens.get(ordem, ordens["desconto"])
        with self.trava:
            linhas = self.con.execute(sql, args).fetchall()
        return [self._linha(l) for l in linhas]

    def anuncio(self, anuncio_id: str) -> dict | None:
        with self.trava:
            l = self.con.execute("SELECT * FROM anuncios WHERE id=?", (anuncio_id,)).fetchone()
        return self._linha(l) if l else None

    def historico(self, anuncio_id: str) -> list[dict]:
        with self.trava:
            linhas = self.con.execute(
                "SELECT preco, quando FROM precos WHERE anuncio_id=? ORDER BY quando", (anuncio_id,)).fetchall()
        return [dict(l) for l in linhas]

    def ocultar(self, anuncio_id: str, oculto=True):
        with self.trava, self.con:
            self.con.execute("UPDATE anuncios SET oculto=? WHERE id=?", (int(oculto), anuncio_id))

    @staticmethod
    def _linha(l) -> dict:
        d = dict(l)
        d["motivos"] = json.loads(d["motivos"]) if d.get("motivos") else []
        return d

    # ------------------------------------------------------------ alertas
    def registrar_alerta(self, anuncio_id: str, preco: int, motivos: list[str]) -> int:
        with self.trava, self.con:
            cur = self.con.execute(
                "INSERT INTO alertas (anuncio_id, preco, motivos, quando) VALUES (?, ?, ?, ?)",
                (anuncio_id, preco, json.dumps(motivos, ensure_ascii=False), agora()))
            return cur.lastrowid

    def ja_alertado(self, anuncio_id: str) -> int | None:
        """Menor preço já alertado para o anúncio (None se nunca)."""
        with self.trava:
            l = self.con.execute("SELECT MIN(preco) p FROM alertas WHERE anuncio_id=?", (anuncio_id,)).fetchone()
        return l["p"] if l and l["p"] is not None else None

    def alertas(self, desde_id: int = 0, limite: int = 100) -> list[dict]:
        with self.trava:
            linhas = self.con.execute(
                "SELECT al.id alerta_id, al.preco preco_alerta, al.motivos motivos_alerta, al.quando, al.lido, a.* "
                "FROM alertas al JOIN anuncios a ON a.id = al.anuncio_id "
                "WHERE al.id > ? ORDER BY al.id DESC LIMIT ?", (desde_id, limite)).fetchall()
        saida = []
        for l in linhas:
            d = self._linha(l)
            d["motivos_alerta"] = json.loads(d["motivos_alerta"]) if d.get("motivos_alerta") else []
            saida.append(d)
        return saida

    def marcar_alertas_lidos(self):
        with self.trava, self.con:
            self.con.execute("UPDATE alertas SET lido=1 WHERE lido=0")

    def nao_lidos(self) -> int:
        with self.trava:
            return self.con.execute("SELECT COUNT(*) FROM alertas WHERE lido=0").fetchone()[0]

    # ------------------------------------------------------------ cache FIPE
    def cache_ler(self, chave: str, max_dias: float):
        with self.trava:
            l = self.con.execute(
                "SELECT valor FROM fipe_cache WHERE chave=? AND quando >= datetime('now', 'localtime', ?)",
                (chave, f"-{max_dias} days")).fetchone()
        return json.loads(l["valor"]) if l else None

    def cache_gravar(self, chave: str, valor):
        with self.trava, self.con:
            self.con.execute("INSERT OR REPLACE INTO fipe_cache VALUES (?, ?, ?)",
                             (chave, json.dumps(valor, ensure_ascii=False), agora()))

    # ------------------------------------------------------------ coletas
    def registrar_coleta(self, inicio, fim, vistos, novos, alertas, erros):
        with self.trava, self.con:
            self.con.execute(
                "INSERT INTO coletas (inicio, fim, vistos, novos, alertas, erros) VALUES (?, ?, ?, ?, ?, ?)",
                (inicio, fim, vistos, novos, alertas, json.dumps(erros, ensure_ascii=False)))

    def ultima_coleta(self) -> dict | None:
        with self.trava:
            l = self.con.execute("SELECT * FROM coletas ORDER BY id DESC LIMIT 1").fetchone()
        if not l:
            return None
        d = dict(l)
        d["erros"] = json.loads(d["erros"]) if d["erros"] else []
        return d

    def estatisticas(self) -> dict:
        with self.trava:
            l = self.con.execute(
                "SELECT COUNT(*) total, SUM(alerta) alertas FROM anuncios WHERE oculto=0").fetchone()
        return {"total": l["total"] or 0, "alertas": l["alertas"] or 0, "nao_lidos": self.nao_lidos()}
