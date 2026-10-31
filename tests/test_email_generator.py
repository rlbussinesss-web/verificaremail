"""Testes da regra de geração de e-mail e do pipeline sobre DataFrame."""

import pandas as pd
import pytest

from src.config import AppConfig
from src.email_generator import gerar_email, processar, resumir

DOM = "@professor.educacao.pe.gov.br"


@pytest.mark.parametrize(
    "nome, esperado",
    [
        ("JOSE ALESSANDRO CAETANO DA SILVA", "jose.acsilva" + DOM),
        ("KATIA JEANNE ALMEIDA TENORIO", "katia.jatenorio" + DOM),
        ("MARIA JOSE DA SILVA LIMA", "maria.jslima" + DOM),
        ("JOAO PAULO DE SOUZA", "joao.psouza" + DOM),
        ("CARLOS EDUARDO ALMEIDA DOS SANTOS", "carlos.easantos" + DOM),
        ("JOSE CESAR MENDONCA", "jose.cmendonca" + DOM),
        ("JOSÉ CÉSAR MENDONÇA", "jose.cmendonca" + DOM),
    ],
)
def test_casos_obrigatorios(nome, esperado):
    assert gerar_email(nome) == esperado


def test_particula_e_no_meio():
    # LEDA CERIS ALVES E SILVA -> primeiro=leda, ultimo=silva, meio=ceris,alves,(e ignorado)
    assert gerar_email("LEDA CERIS ALVES E SILVA") == "leda.casilva" + DOM


def test_espacos_duplos_e_caixa():
    assert gerar_email("  maria   JOSE   da  SILVA   lima ") == "maria.jslima" + DOM


def test_um_nome_nao_gera_email():
    assert gerar_email("MADONNA") == ""


def test_dois_nomes_gera_primeiro_ponto_ultimo():
    assert gerar_email("NUBIA VERAS") == "nubia.veras" + DOM


def test_dominio_customizado():
    cfg = AppConfig(dominio="escola.exemplo.gov.br")
    assert gerar_email("JOAO PAULO DE SOUZA", cfg) == "joao.psouza@escola.exemplo.gov.br"


def test_todas_particulas_no_meio():
    # primeiro + ultimo, sem iniciais
    assert gerar_email("MARIA DA DE SILVA") == "maria.silva" + DOM


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #
def _df(nomes, cargos=None, matriculas=None):
    d = {"Nome Completo": nomes}
    if cargos is not None:
        d["Cargo"] = cargos
    if matriculas is not None:
        d["Matrícula"] = matriculas
    return pd.DataFrame(d)


CFG_VER_CONFLITOS = AppConfig(descartar_conflitos=False)


def test_pipeline_duplicado_mesmo_nome():
    df = _df(
        ["JOSE EDUARDO GOMES DA SILVA", "JOSE EDUARDO GOMES DA SILVA"],
        matriculas=["1/1", "1/2"],
    )
    res, _ = processar(df, "Nome Completo", coluna_matricula="Matrícula")
    assert len(res) == 1  # colapsado
    linha = res.iloc[0]
    assert linha["Status"] == "DUPLICADO"
    assert linha["Qtd Registros"] == 2
    assert linha["Email Gerado"] == "jose.egsilva" + DOM
    assert set(linha["Matrículas"].split(", ")) == {"1/1", "1/2"}


def test_pipeline_conflito_visivel_quando_desligado():
    # dois nomes diferentes que geram o MESMO e-mail
    df = _df(["ANA BEATRIZ COSTA LIMA", "ANA B CRUZ LIMA"])
    res, removidos = processar(df, "Nome Completo", config=CFG_VER_CONFLITOS)
    conflitos = res[res["Status"] == "CONFLITO"]
    assert len(conflitos) == 2
    assert len(removidos) == 0
    assert all(conflitos["Email Gerado"] == "ana.bclima" + DOM)
    assert all(conflitos["Revisão"] == "REVISAR")
    assert all("CONFLITO DE EMAIL" in m for m in conflitos["Motivo"])


def test_pipeline_conflito_descartado_por_padrao():
    # ordem do CSV: ANA BEATRIZ fica com o e-mail, ANA B CRUZ é removida
    df = _df(["ANA BEATRIZ COSTA LIMA", "ANA B CRUZ LIMA", "PEDRO ALVES SOUZA"])
    res, removidos = processar(df, "Nome Completo")  # descartar_conflitos=True (padrão)

    assert "CONFLITO" not in set(res["Status"])
    assert (res["Email Gerado"] == "ana.bclima" + DOM).sum() == 1
    kept = res[res["Email Gerado"] == "ana.bclima" + DOM].iloc[0]
    assert kept["Nome Original"] == "ANA BEATRIZ COSTA LIMA"

    assert len(removidos) == 1
    rem = removidos.iloc[0]
    assert rem["Nome Original"] == "ANA B CRUZ LIMA"
    assert rem["Status"] == "REMOVIDO (conflito)"
    assert rem["Mantido Para"] == "ANA BEATRIZ COSTA LIMA"
    assert "ANA BEATRIZ COSTA LIMA" in rem["Motivo"]

    # e-mails únicos preservados; nenhuma duplicata no painel
    assert res["Email Gerado"].replace("", pd.NA).dropna().is_unique


def test_pipeline_linha_vazia_vira_invalido():
    df = _df(["MARIA DAS DORES DA SILVA", "", "   "])
    res, _ = processar(df, "Nome Completo")
    invalidos = res[res["Status"] == "INVÁLIDO"]
    assert len(invalidos) >= 1
    assert all(invalidos["Email Gerado"] == "")


def test_pipeline_cargo_nao_docente_so_marca_se_configurado():
    from src.config import AppConfig

    df = _df(
        ["MARCELO SEBASTIAO DE MOURA", "JOELMA MARIA DE ALMEIDA SILVA"],
        cargos=["ASSISTENTE ADMINISTRATIVO EDUCACIONAL", "PROFESSOR"],
    )

    # padrão: cargo não-docente NÃO marca revisão
    res, _ = processar(df, "Nome Completo", coluna_cargo="Cargo")
    m = res.set_index("Nome Original")
    assert m.loc["MARCELO SEBASTIAO DE MOURA", "Revisão"] == "OK"
    assert "Cargo não é PROFESSOR" not in m.loc["MARCELO SEBASTIAO DE MOURA", "Motivo"]

    # com a flag ligada: volta a marcar
    cfg = AppConfig(revisar_nao_docente=True)
    res2, _ = processar(df, "Nome Completo", coluna_cargo="Cargo", config=cfg)
    m2 = res2.set_index("Nome Original")
    assert m2.loc["MARCELO SEBASTIAO DE MOURA", "Revisão"] == "REVISAR"
    assert "Cargo não é PROFESSOR" in m2.loc["MARCELO SEBASTIAO DE MOURA", "Motivo"]
    assert m2.loc["JOELMA MARIA DE ALMEIDA SILVA", "Revisão"] == "OK"


def test_pipeline_valores_invalidos_nao_quebram():
    df = _df(["123456", "!!!", "A", "JOSE DA SILVA SANTOS"])
    res, _ = processar(df, "Nome Completo")
    assert len(res) == 4
    assert (res["Email Gerado"] == "jose.ssantos" + DOM).any()


def test_resumir_bate_contagens():
    df = _df(
        ["JOSE ALESSANDRO CAETANO DA SILVA", "JOSE ALESSANDRO CAETANO DA SILVA",
         "MARIA JOSE DA SILVA LIMA", "", "MADONNA"],
    )
    res, removidos = processar(df, "Nome Completo")
    stats = resumir(res, None, removidos)
    assert stats["duplicados"] == 1
    assert stats["invalidos"] == 1
    assert stats["emails_unicos"] >= 2
    assert stats["descartados_conflito"] == 0
