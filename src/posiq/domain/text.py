"""Normalización de texto compartida por el cargador y la detección. Sin I/O."""

import re
import unicodedata


def fold(text: str) -> str:
    """Quita acentos y pasa a minúsculas: «Clínica» → «clinica»."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def fold_with_map(text: str) -> tuple[str, list[int]]:
    """Como `fold`, pero devuelve también, por cada carácter normalizado, su índice en `text`.

    Se normaliza carácter a carácter para poder traducir un span del texto normalizado a un span
    del texto original aunque un carácter cambie de longitud al normalizarse.
    """
    out: list[str] = []
    index: list[int] = []
    for i, char in enumerate(text):
        folded = fold(char)
        out.append(folded)
        index.extend([i] * len(folded))
    return "".join(out), index


def slugify(text: str) -> str:
    """Identificador estable: «Clínica Alborada Visión» → «clinica-alborada-vision»."""
    return re.sub(r"[^a-z0-9]+", "-", fold(text)).strip("-")
