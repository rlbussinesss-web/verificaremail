"""Validações técnicas do e-mail — sem envio de mensagens.

Quatro níveis, conscientemente distintos e honestos:

    EMAIL GERADO ........... a parte local pôde ser montada pela regra
    FORMATO VÁLIDO ......... sintaxe compatível com e-mail (regex + limites)
    DOMÍNIO VÁLIDO ........ hostname bem formado; opcionalmente com registro MX
    CAIXA POSTAL CONFIRMADA  NUNCA marcada aqui — exigiria diretório/API autorizado

Nada neste módulo faz enumeração SMTP ou envio. Se `verificar_mx=True`, apenas o
NOME DO DOMÍNIO é consultado via DNS — a lista de nomes jamais trafega.
"""

from __future__ import annotations

import re
from functools import lru_cache

# Local-part: rótulos alfanuméricos separados por ponto (sem ponto no início/fim
# e sem ponto duplo). Suficiente para os e-mails que esta ferramenta gera.
_RE_EMAIL = re.compile(
    r"^(?=.{1,64}@)[a-z0-9]+(?:[._-][a-z0-9]+)*"
    r"@(?=.{1,255}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$"
)

_RE_HOSTNAME = re.compile(
    r"^(?=.{1,255}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$"
)


def validar_formato(email: str) -> bool:
    """True se a sintaxe do e-mail é válida (limites 64 no local, 254 no total)."""
    if not email or not isinstance(email, str):
        return False
    email = email.strip()
    if len(email) > 254 or email.count("@") != 1:
        return False
    return bool(_RE_EMAIL.match(email.lower()))


def dominio_bem_formado(dominio: str) -> bool:
    """True se o domínio é um hostname sintaticamente válido (com ponto)."""
    if not dominio:
        return False
    return bool(_RE_HOSTNAME.match(dominio.strip().lower()))


@lru_cache(maxsize=64)
def _tem_mx(dominio: str) -> str:
    """Consulta MX/A do domínio. Retorna 'mx', 'sem-mx' ou 'erro-dns'.

    O resultado é cacheado por domínio para não repetir a consulta.
    """
    try:
        import dns.resolver  # type: ignore
    except Exception:
        return "sem-dnspython"

    try:
        respostas = dns.resolver.resolve(dominio, "MX")
        if len(respostas) > 0:
            return "mx"
        return "sem-mx"
    except Exception:
        pass

    # fallback: domínio pode aceitar e-mail no próprio A/AAAA
    try:
        dns.resolver.resolve(dominio, "A")
        return "mx"
    except Exception:
        return "erro-dns"


def validar_dominio(dominio: str, *, verificar_mx: bool = False) -> str:
    """Rótulo curto para a coluna 'Domínio Válido'.

    Valores possíveis:
        'Não'                       -> hostname mal formado
        'Sim (formato)'             -> bem formado, DNS não consultado
        'Sim (MX encontrado)'       -> possui registro MX/A
        'Formato ok, sem MX'        -> resolve mas sem MX
        'Formato ok, DNS falhou'    -> não foi possível resolver
        'Formato ok (dnspython ausente)'
    """
    dominio = (dominio or "").strip().lower().lstrip("@")
    if not dominio_bem_formado(dominio):
        return "Não"
    if not verificar_mx:
        return "Sim (formato)"

    estado = _tem_mx(dominio)
    return {
        "mx": "Sim (MX encontrado)",
        "sem-mx": "Formato ok, sem MX",
        "erro-dns": "Formato ok, DNS falhou",
        "sem-dnspython": "Formato ok (dnspython ausente)",
    }.get(estado, "Sim (formato)")
