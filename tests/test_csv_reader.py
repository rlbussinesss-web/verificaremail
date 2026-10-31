"""Testes de detecção automática de CSV."""

from pathlib import Path

import pytest

from src.csv_reader import (
    carregar_csv,
    detectar_coluna_nome,
    detectar_delimitador,
    detectar_encoding,
    detectar_linha_cabecalho,
)

RAIZ = Path(__file__).resolve().parent.parent

CSV_PONTO_VIRGULA = (
    "Remuneração\r\n"
    "\r\n"
    "Matrícula  ;Nome Completo  ;Cargo e/ou função desempenhada  ;Lotação  \r\n"
    '"1000128/4";"JOELMA MARIA DE ALMEIDA SILVA";"PROFESSOR";"SECRETARIA DE EDUCACAO";\r\n'
    '"1000349/1";"JOSÉ CÉSAR MENDONÇA";"PROFESSOR";"SECRETARIA DE EDUCACAO";\r\n'
    '"1001477/1";"MARCELO SEBASTIAO DE MOURA";"ASSISTENTE";"SECRETARIA DE EDUCACAO";\r\n'
)

CSV_VIRGULA = (
    "nome,idade,cidade\r\n"
    "MARIA JOSE DA SILVA LIMA,40,Recife\r\n"
    "JOAO PAULO DE SOUZA,35,Olinda\r\n"
)


def test_detectar_encoding_utf8_sem_bom():
    assert detectar_encoding(CSV_PONTO_VIRGULA.encode("utf-8")) == "utf-8"


def test_detectar_encoding_utf8_com_bom():
    dados = b"\xef\xbb\xbf" + CSV_PONTO_VIRGULA.encode("utf-8")
    assert detectar_encoding(dados) == "utf-8-sig"


def test_detectar_encoding_cp1252():
    dados = "Nome;Cargo\r\nJOSE ANTONIO;PROFESSOR\r\nMARIA DA CONCEICAO;PROFESSOR\r\n".encode(
        "cp1252"
    )
    # bytes com acento que quebram UTF-8
    dados += "JOAO PÊSSEGO;PROFESSOR\r\n".encode("cp1252")
    enc = detectar_encoding(dados)
    assert enc != "utf-8"
    # o encoding detectado precisa conseguir decodificar sem erro
    texto = dados.decode(enc)
    assert "PROFESSOR" in texto


def test_detectar_delimitador_ponto_e_virgula():
    assert detectar_delimitador(CSV_PONTO_VIRGULA) == ";"


def test_detectar_delimitador_virgula():
    assert detectar_delimitador(CSV_VIRGULA) == ","


def test_detectar_linha_cabecalho_pula_titulo():
    assert detectar_linha_cabecalho(CSV_PONTO_VIRGULA, ";") == 2


def test_detectar_linha_cabecalho_primeira_linha():
    assert detectar_linha_cabecalho(CSV_VIRGULA, ",") == 0


def test_carregar_csv_ponto_e_virgula_completo():
    r = carregar_csv(CSV_PONTO_VIRGULA.encode("utf-8"))
    assert r.delimitador == ";"
    assert r.linha_cabecalho == 2
    assert r.encoding == "utf-8"
    assert r.coluna_nome == "Nome Completo"
    assert r.coluna_cargo == "Cargo e/ou função desempenhada"
    assert r.coluna_matricula == "Matrícula"
    assert r.n_linhas == 3
    # coluna final vazia (por causa do ; final) foi descartada
    assert "" not in r.colunas
    assert list(r.df["Nome Completo"]) == [
        "JOELMA MARIA DE ALMEIDA SILVA",
        "JOSÉ CÉSAR MENDONÇA",
        "MARCELO SEBASTIAO DE MOURA",
    ]


def test_carregar_csv_com_bom_e_virgula():
    dados = b"\xef\xbb\xbf" + CSV_VIRGULA.encode("utf-8")
    r = carregar_csv(dados)
    assert r.delimitador == ","
    assert r.coluna_nome == "nome"
    assert r.n_linhas == 2


def test_detectar_coluna_nome_prefere_nome_completo():
    r = carregar_csv(CSV_PONTO_VIRGULA.encode("utf-8"))
    melhor, scores = detectar_coluna_nome(r.df)
    assert melhor == "Nome Completo"
    assert scores["Nome Completo"] >= scores["Lotação"]


def test_forcar_coluna_nome():
    r = carregar_csv(CSV_PONTO_VIRGULA.encode("utf-8"), coluna_nome_forcada="Lotação")
    assert r.coluna_nome == "Lotação"


@pytest.mark.skipif(
    not (RAIZ / "Remuneração_01092026.csv").exists(),
    reason="CSV real não encontrado",
)
def test_csv_real_da_pasta():
    r = carregar_csv(RAIZ / "Remuneração_01092026.csv")
    assert r.delimitador == ";"
    assert r.coluna_nome == "Nome Completo"
    assert r.n_linhas > 50
