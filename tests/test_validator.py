"""Testes das validações técnicas (sintaxe, domínio) — sem rede por padrão."""

import pytest

from src.validator import dominio_bem_formado, validar_dominio, validar_formato


@pytest.mark.parametrize(
    "email, ok",
    [
        ("jose.acsilva@professor.educacao.pe.gov.br", True),
        ("katia.jatenorio@professor.educacao.pe.gov.br", True),
        ("a.b@x.co", True),
        ("", False),
        ("semarroba.com", False),
        ("dois@@arrobas.com", False),
        ("espaco no meio@dominio.com", False),
        ("ponto..duplo@dominio.com", False),
        (".comeca.ponto@dominio.com", False),
        ("acentuado.josé@dominio.com", False),
        ("local@dominio_sem_tld", False),
        ("x" * 65 + "@dominio.com", False),
    ],
)
def test_validar_formato(email, ok):
    assert validar_formato(email) is ok


@pytest.mark.parametrize(
    "dominio, ok",
    [
        ("professor.educacao.pe.gov.br", True),
        ("exemplo.com", True),
        ("semponto", False),
        ("-comeca-hifen.com", False),
        ("", False),
    ],
)
def test_dominio_bem_formado(dominio, ok):
    assert dominio_bem_formado(dominio) is ok


def test_validar_dominio_sem_rede():
    assert validar_dominio("professor.educacao.pe.gov.br", verificar_mx=False) == "Sim (formato)"
    assert validar_dominio("dominio_invalido", verificar_mx=False) == "Não"


def test_validar_dominio_com_mx_mockado(monkeypatch):
    import src.validator as v

    monkeypatch.setattr(v, "_tem_mx", lambda d: "mx")
    assert v.validar_dominio("professor.educacao.pe.gov.br", verificar_mx=True) == (
        "Sim (MX encontrado)"
    )

    monkeypatch.setattr(v, "_tem_mx", lambda d: "sem-mx")
    assert v.validar_dominio("exemplo.com", verificar_mx=True) == "Formato ok, sem MX"
