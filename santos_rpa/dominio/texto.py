"""Normalização de texto e identidade de uma notícia."""
import hashlib
import re
import unicodedata


def norm(texto: str) -> str:
    """Minúsculas e sem acentos, para comparar textos."""
    t = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


def chave(titulo: str, fonte: str) -> str:
    """Identidade da notícia: o mesmo título no mesmo veículo é a mesma notícia."""
    base = re.sub(r"[^a-z0-9 ]", "", norm(titulo)) + "|" + norm(fonte)
    return hashlib.sha1(base.encode()).hexdigest()
