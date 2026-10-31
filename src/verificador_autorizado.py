"""Confirmação de existência de caixas postais — só com fonte autorizada.

Regra de ouro deste módulo: **nada é marcado como confirmado por dedução.**
Uma conta só vira "CONFIRMADA" se aparecer numa lista que VEIO de uma fonte
autorizada (pedido via LAI, export do diretório/AD, API da Secretaria, ou
endereços que você mesmo verificou). A confiabilidade da confirmação é
exatamente a confiabilidade da lista fornecida.

Nunca há enumeração SMTP nem envio de mensagens.

Para ligar uma API/diretório no futuro, crie uma subclasse de
`VerificadorContas` e devolva-a em `obter_verificador()`.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List

_RE_EMAIL_SOLTO = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# Rótulos usados na coluna "Caixa Postal"
CONFIRMADA = "CONFIRMADA (lista oficial)"
NAO_CONSTA = "Não consta na lista"
NAO_VERIFICAVEL = "Não verificável"


def extrair_emails(texto: str) -> List[str]:
    """Extrai e-mails de um texto livre (colado, CSV, TXT), sem duplicatas."""
    if not texto:
        return []
    achados = (m.group(0).strip().lower() for m in _RE_EMAIL_SOLTO.finditer(texto))
    return list(dict.fromkeys(achados))


class VerificadorContas:
    """Interface. A implementação padrão nunca confirma nada."""

    nome = "nenhum"
    origem = "—"

    def disponivel(self) -> bool:
        return False

    def confirmar(self, emails: Iterable[str]) -> Dict[str, dict]:
        """Retorna {email: {'existe': bool|None, 'fonte': str, 'detalhe': str}}."""
        return {
            e: {
                "existe": None,
                "fonte": self.nome,
                "detalhe": "Verificação de caixa postal não disponível",
            }
            for e in emails
        }


class VerificadorIndisponivel(VerificadorContas):
    nome = "indisponivel"


class VerificadorListaLocal(VerificadorContas):
    """Confirma comparando com uma lista de e-mails reais fornecida pelo usuário.

    Não adivinha: quem está na lista é confirmado, quem não está fica como
    "não consta" (o que NÃO significa que não exista — só que a lista não cobre).
    """

    nome = "lista-local"

    def __init__(self, emails: Iterable[str], origem: str = "lista fornecida"):
        self.emails = {
            e.strip().lower() for e in emails if e and "@" in str(e)
        }
        self.origem = origem

    def __len__(self) -> int:
        return len(self.emails)

    def disponivel(self) -> bool:
        return bool(self.emails)

    def contem(self, email: str) -> bool:
        return bool(email) and email.strip().lower() in self.emails

    def confirmar(self, emails: Iterable[str]) -> Dict[str, dict]:
        saida: Dict[str, dict] = {}
        for e in emails:
            existe = self.contem(e)
            saida[e] = {
                "existe": True if existe else None,
                "fonte": self.origem,
                "detalhe": CONFIRMADA if existe else NAO_CONSTA,
            }
        return saida


def obter_verificador(emails_conhecidos: Iterable[str] | None = None) -> VerificadorContas:
    """Fábrica única. Troque aqui quando houver um módulo autorizado (LDAP/API)."""
    if emails_conhecidos:
        return VerificadorListaLocal(emails_conhecidos)
    return VerificadorIndisponivel()
