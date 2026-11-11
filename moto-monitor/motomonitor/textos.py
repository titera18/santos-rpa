"""Funções pequenas de texto: normalização, preço, ano e km."""
import re
import unicodedata


def normalizar(texto: str) -> str:
    """Minúsculas, sem acento e com espaços simples."""
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-z0-9]+", " ", texto.lower())
    return texto.strip()


def para_inteiro(valor) -> int | None:
    """'R$ 15.900' -> 15900; 'R$ 15.900,50' -> 15900; 15900.0 -> 15900."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return int(valor)
    texto = str(valor)
    texto = texto.split(",")[0]  # descarta centavos
    digitos = re.sub(r"\D", "", texto)
    return int(digitos) if digitos else None


def extrair_ano(*textos) -> int | None:
    for texto in textos:
        if texto is None:
            continue
        if isinstance(texto, int) and 1970 <= texto <= 2100:
            return texto
        for achado in re.findall(r"\b(19[7-9]\d|20[0-4]\d)\b", str(texto)):
            return int(achado)
    return None


def extrair_km(texto) -> int | None:
    if texto is None:
        return None
    if isinstance(texto, (int, float)):
        return int(texto)
    m = re.search(r"([\d\.]+)\s*km", str(texto).lower())
    if m:
        return para_inteiro(m.group(1))
    return para_inteiro(texto)


def moeda(valor) -> str:
    if valor is None:
        return "—"
    return "R$ " + f"{int(round(valor)):,}".replace(",", ".")
