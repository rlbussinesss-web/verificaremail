"""Testes de exportação CSV (Excel BR) e XLSX formatado."""

import io

import pandas as pd
import pytest

from src.exporter import csv_bytes, xlsx_bytes

DF = pd.DataFrame(
    {
        "Nome Original": ["JOSÉ CÉSAR MENDONÇA", "ANA BEATRIZ COSTA LIMA"],
        "Email Gerado": [
            "jose.cmendonca@professor.educacao.pe.gov.br",
            "ana.bclima@professor.educacao.pe.gov.br",
        ],
        "Status": ["OK", "CONFLITO"],
        "Revisão": ["OK", "REVISAR"],
        "Motivo": ["", "CONFLITO DE EMAIL com: ana b cruz lima"],
    }
)


def test_csv_tem_bom_e_ponto_e_virgula():
    dados = csv_bytes(DF)
    assert dados.startswith(b"\xef\xbb\xbf")
    texto = dados.decode("utf-8-sig")
    assert texto.splitlines()[0] == "Nome Original;Email Gerado;Status;Revisão;Motivo"


def test_csv_preserva_acentos():
    dados = csv_bytes(DF)
    texto = dados.decode("utf-8-sig")
    assert "JOSÉ CÉSAR MENDONÇA" in texto
    assert "Revisão" in texto


def test_csv_reabre_no_pandas():
    dados = csv_bytes(DF)
    df2 = pd.read_csv(io.BytesIO(dados), sep=";", dtype=str, keep_default_na=False,
                      encoding="utf-8-sig")
    assert list(df2.columns) == list(DF.columns)
    assert df2.loc[0, "Nome Original"] == "JOSÉ CÉSAR MENDONÇA"


def test_xlsx_estrutura():
    openpyxl = pytest.importorskip("openpyxl")
    dados = xlsx_bytes(DF)
    wb = openpyxl.load_workbook(io.BytesIO(dados))
    ws = wb.active

    # cabeçalho na primeira linha, em negrito
    assert [c.value for c in ws[1]] == list(DF.columns)
    assert ws["A1"].font.bold is True

    # painel congelado abaixo do cabeçalho
    assert ws.freeze_panes == "A2"

    # autofiltro presente
    assert ws.auto_filter.ref is not None

    # conteúdo
    assert ws["A2"].value == "JOSÉ CÉSAR MENDONÇA"
