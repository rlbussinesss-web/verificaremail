"""Funções utilitárias de baixo nível, sem dependência de pandas/streamlit."""

from __future__ import annotations

import re
import time
import unicodedata
from contextlib import contextmanager
from typing import Iterator

# Mapa explícito exigido pela especificação. O unicodedata já resolveria a maior
# parte, mas manter o mapa deixa o comportamento previsível e testável.
_MAPA_ACENTOS = str.maketrans(
    {
        "á": "a", "à": "a", "ã": "a", "â": "a", "ä": "a",
        "é": "e", "è": "e", "ê": "e", "ë": "e",
        "í": "i", "ì": "i", "î": "i", "ï": "i",
        "ó": "o", "ò": "o", "õ": "o", "ô": "o", "ö": "o",
        "ú": "u", "ù": "u", "û": "u", "ü": "u",
        "ç": "c", "ñ": "n", "ý": "y", "ÿ": "y",
        "Á": "A", "À": "A", "Ã": "A", "Â": "A", "Ä": "A",
        "É": "E", "È": "E", "Ê": "E", "Ë": "E",
        "Í": "I", "Ì": "I", "Î": "I", "Ï": "I",
        "Ó": "O", "Ò": "O", "Õ": "O", "Ô": "O", "Ö": "O",
        "Ú": "U", "Ù": "U", "Û": "U", "Ü": "U",
        "Ç": "C", "Ñ": "N", "Ý": "Y",
    }
)

_RE_ESPACOS = re.compile(r"\s+")


def remover_acentos(texto: str) -> str:
    """Remove acentuação preservando a letra base (inclui ç → c).

    Primeiro aplica o mapa explícito e em seguida um passe genérico via NFKD
    para cobrir qualquer diacrítico não listado.
    """
    if not texto:
        return ""
    texto = texto.translate(_MAPA_ACENTOS)
    decomposto = unicodedata.normalize("NFKD", texto)
    sem_diacritico = "".join(c for c in decomposto if not unicodedata.combining(c))
    return unicodedata.normalize("NFC", sem_diacritico)


def colapsar_espacos(texto: str) -> str:
    """Troca sequências de espaços/brancos por um único espaço e faz strip."""
    if not texto:
        return ""
    return _RE_ESPACOS.sub(" ", texto).strip()


def is_vazio(valor) -> bool:
    """True para None, NaN, string vazia ou só com espaços."""
    if valor is None:
        return True
    try:
        # captura float('nan') sem importar math/pandas
        if valor != valor:  # noqa: PLR0124
            return True
    except TypeError:
        pass
    return str(valor).strip() == ""


@contextmanager
def cronometro() -> Iterator["_Tempo"]:
    """Mede o tempo decorrido de um bloco: `with cronometro() as t: ...; t.segundos`."""
    marcador = _Tempo()
    inicio = time.perf_counter()
    try:
        yield marcador
    finally:
        marcador.segundos = time.perf_counter() - inicio


class _Tempo:
    segundos: float = 0.0
