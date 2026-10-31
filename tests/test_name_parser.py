"""Testes de normalização e classificação de nomes."""

import pytest

from src.config import SUFIXOS_REVISAO_PADRAO
from src.name_parser import classificar_nome, normalizar_nome, tokenizar

SUFIXOS = set(SUFIXOS_REVISAO_PADRAO)


@pytest.mark.parametrize(
    "entrada, esperado",
    [
        ("JOSE ALESSANDRO CAETANO DA SILVA", "jose alessandro caetano da silva"),
        ("  MARIA   JOSE  DA   SILVA LIMA ", "maria jose da silva lima"),
        ("JOSÉ CÉSAR MENDONÇA", "jose cesar mendonca"),
        ("JOÃO PÃO ÂNGELO ÊNIO ÍRIS ÓRION ÕÔ ÚRSULA", "joao pao angelo enio iris orion oo ursula"),
        ("MARIA-CLARA D'ARC", "mariaclara darc"),
        ("ANTÔNIO   \t  DA   CONCEIÇÃO", "antonio da conceicao"),
        ("", ""),
        (None, ""),
        ("JOSÉ@#$ DA %SILVA%", "jose da silva"),
    ],
)
def test_normalizacao(entrada, esperado):
    assert normalizar_nome(entrada) == esperado


def test_normalizacao_remove_cedilha():
    assert normalizar_nome("CONCEIÇÃO") == "conceicao"
    assert normalizar_nome("MOÇA") == "moca"


def test_tokenizar():
    assert tokenizar("jose alessandro caetano da silva") == [
        "jose", "alessandro", "caetano", "da", "silva",
    ]
    assert tokenizar("") == []
    assert tokenizar("   ") == []


def _classificar(nome):
    norm = normalizar_nome(nome)
    return classificar_nome(nome, norm, tokenizar(norm), sufixos_revisao=SUFIXOS)


def test_um_nome_marca_revisar():
    c = _classificar("MADONNA")
    assert c.revisar
    assert "Apenas um nome" in c.motivo_texto


def test_dois_nomes_marca_revisar():
    c = _classificar("NUBIA VERAS")
    assert c.revisar
    assert "Apenas dois nomes" in c.motivo_texto


def test_nome_completo_normal_ok():
    c = _classificar("JOSE ALESSANDRO CAETANO DA SILVA")
    assert not c.revisar
    assert c.motivo_texto == ""


def test_sufixo_filho_marca_revisar():
    c = _classificar("JOSE MARINHO DE LIMA FILHO")
    assert c.revisar
    assert 'sufixo "FILHO"' in c.motivo_texto


def test_sufixo_junior_com_acento():
    c = _classificar("MARIA ESTER DE PAULA JÚNIOR")
    assert c.revisar
    assert 'sufixo "JUNIOR"' in c.motivo_texto


def test_hifen_e_apostrofo():
    c = _classificar("ANA-MARIA DE SOUZA D'AVILA")
    assert c.revisar
    assert "hífen" in c.motivo_texto
    assert "apóstrofo" in c.motivo_texto


def test_numeros_no_nome():
    c = _classificar("JOSE 123 DA SILVA")
    assert c.revisar
    assert "números" in c.motivo_texto


def test_registro_sem_nome():
    c = _classificar("   ")
    assert c.revisar
    assert "sem nome" in c.motivo_texto.lower()


def test_inicial_isolada():
    c = _classificar("JOSE A DA SILVA")
    assert c.revisar
    assert "inicial isolada" in c.motivo_texto


def test_particula_e_nao_e_inicial_isolada():
    from src.config import PARTICULAS_PADRAO

    nome = "LEDA CERIS ALVES E SILVA"
    norm = normalizar_nome(nome)
    c = classificar_nome(
        nome, norm, tokenizar(norm),
        sufixos_revisao=SUFIXOS, particulas=set(PARTICULAS_PADRAO),
    )
    assert not c.revisar, c.motivo_texto
