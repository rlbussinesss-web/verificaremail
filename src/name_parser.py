"""Normalização e análise de nomes completos.

Este módulo NÃO monta o e-mail (isso é do `email_generator`); ele apenas:
  * normaliza o nome para uma forma segura para e-mail;
  * quebra em tokens;
  * classifica o registro em OK / REVISAR com um ou mais motivos.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Sequence

from .utils import colapsar_espacos, remover_acentos

# Depois de remover acentos, mantém apenas letras, dígitos e espaço.
# Apóstrofos e hífens são removidos "juntando" as letras (D'ARC -> darc).
_RE_JUNTAR = re.compile(r"[’'`\-]")
_RE_NAO_PERMITIDO = re.compile(r"[^a-z0-9 ]+")
_RE_TEM_DIGITO = re.compile(r"\d")
_RE_CARACTERE_INCOMUM = re.compile(r"[^A-Za-zÀ-ÿ0-9 .'’`\-]")


def normalizar_nome(nome: str) -> str:
    """Converte o nome para minúsculas, sem acentos e sem caracteres inválidos.

    Passos: strip → minúsculas → remove acentos (á→a, ç→c, ...) → junta letras
    separadas por apóstrofo/hífen → remove o que não for [a-z0-9 ] → colapsa
    espaços duplos.
    """
    if nome is None:
        return ""
    texto = str(nome).strip().lower()
    texto = remover_acentos(texto)
    texto = _RE_JUNTAR.sub("", texto)
    texto = _RE_NAO_PERMITIDO.sub(" ", texto)
    return colapsar_espacos(texto)


def tokenizar(nome_normalizado: str) -> List[str]:
    """Lista de tokens não vazios do nome já normalizado."""
    if not nome_normalizado:
        return []
    return [t for t in nome_normalizado.split(" ") if t]


@dataclass
class ClassificacaoNome:
    """Resultado da checagem de qualidade de um nome."""

    revisar: bool = False
    motivos: List[str] = field(default_factory=list)

    def marcar(self, motivo: str) -> None:
        self.revisar = True
        if motivo not in self.motivos:
            self.motivos.append(motivo)

    @property
    def status_revisao(self) -> str:
        return "REVISAR" if self.revisar else "OK"

    @property
    def motivo_texto(self) -> str:
        return "; ".join(self.motivos)


def classificar_nome(
    nome_original: str,
    nome_normalizado: str,
    tokens: Sequence[str],
    *,
    sufixos_revisao: set[str],
    particulas: set[str] | None = None,
    min_len_nome: int = 6,
    max_tokens_nome: int = 6,
) -> ClassificacaoNome:
    """Aplica todas as heurísticas de "precisa de conferência humana".

    Nunca inventa regra de negócio para JUNIOR/FILHO/etc.: apenas sinaliza.
    """
    c = ClassificacaoNome()
    particulas = particulas or set()
    original = "" if nome_original is None else str(nome_original)
    original_strip = original.strip()

    if not original_strip:
        c.marcar("Registro sem nome")
        return c

    if not nome_normalizado:
        c.marcar("Nome sem caracteres aproveitáveis após normalização")
        return c

    n_tokens = len(tokens)
    tokens_reais = [t for t in tokens if t not in particulas]

    if n_tokens == 1:
        c.marcar("Apenas um nome")
    elif n_tokens == 2:
        c.marcar("Apenas dois nomes")

    if len(tokens_reais) > max_tokens_nome:
        c.marcar(
            f"Nome muito longo ({len(tokens_reais)} nomes) — possível dado corrompido"
        )

    if len(nome_normalizado.replace(" ", "")) < min_len_nome:
        c.marcar("Nome muito curto")

    # token de uma única letra que NÃO é partícula (inicial abreviada na origem)
    if any(len(t) == 1 for t in tokens if t not in particulas):
        c.marcar("Contém inicial isolada")

    if _RE_TEM_DIGITO.search(original_strip):
        c.marcar("Nome contém números")

    if "-" in original_strip:
        c.marcar("Nome contém hífen")

    if "'" in original_strip or "’" in original_strip or "`" in original_strip:
        c.marcar("Nome contém apóstrofo")

    if _RE_CARACTERE_INCOMUM.search(original_strip):
        c.marcar("Nome contém caracteres incomuns")

    for t in tokens:
        if t in sufixos_revisao:
            c.marcar(f'Nome contém sufixo "{t.upper()}"')

    return c
