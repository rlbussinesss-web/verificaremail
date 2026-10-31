"""Testes da busca de servidores na API de Dados Abertos de PE (sem rede)."""

import json

import pytest

from src import fonte_transparencia as ft


class _RespFake:
    def __init__(self, *, js=None, content=b"", status=200):
        self._js = js
        self.content = content
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._js


class _SessaoFake:
    def __init__(self, mapa):
        self._mapa = mapa

    def get(self, url, **kw):
        for chave, resp in self._mapa.items():
            if chave in url:
                return resp
        raise AssertionError(f"URL inesperada: {url}")

    def close(self):
        pass


_PACKAGE = {
    "success": True,
    "result": {
        "resources": [
            {
                "format": "JSON",
                "name": "Remuneração ativos 07/2026",
                "url": "https://x/download/2026_7_remuneracao_ativos.json",
            },
            {
                "format": "JSON",
                "name": "Remuneração ativos 06/2026",
                "url": "https://x/download/2026_6_remuneracao_ativos.json",
            },
            {
                "format": "CSV",
                "name": "Remuneração ativos 07/2026",
                "url": "https://x/download/2026_7_remuneracao_ativos.csv",
            },
            {
                "format": "JSON",
                "name": "Remuneração inativos 07/2026",
                "url": "https://x/download/2026_7_remuneracao_inativos.json",
            },
        ]
    },
}

_FOLHA = {
    "campos": [
        {
            "r_nome": "MARIA JOSE DA SILVA LIMA",
            "r_matricula": "111/01",
            "r_cargo": "PROFESSOR",
            "r_instituicao": "SECRETARIA DE EDUCACAO",
        },
        {
            "r_nome": "JOAO PAULO DE SOUZA",
            "r_matricula": "222/01",
            "r_cargo": "ASSISTENTE",
            "r_instituicao": "FUNAFIN SECRETARIA DE EDUCACAO",
        },
        {
            "r_nome": "CARLOS EDUARDO ALMEIDA",
            "r_matricula": "333/01",
            "r_cargo": "MEDICO",
            "r_instituicao": "SEC DE SAUDE",
        },
        {
            "r_nome": "   ",
            "r_matricula": "444/01",
            "r_cargo": "",
            "r_instituicao": "SECRETARIA DE EDUCACAO",
        },
    ]
}


def test_listar_recursos_ordena_e_filtra_por_tipo():
    sess = _SessaoFake({"package_show": _RespFake(js=_PACKAGE)})
    recs = ft.listar_recursos(tipo="ativos", formato="JSON", sessao=sess)
    assert [(r.ano, r.mes) for r in recs] == [(2026, 7), (2026, 6)]
    assert all(r.tipo == "ativos" for r in recs)
    assert recs[0].rotulo.startswith("07/2026")


def test_recurso_mais_recente():
    sess = _SessaoFake({"package_show": _RespFake(js=_PACKAGE)})
    r = ft.recurso_mais_recente(tipo="ativos", sessao=sess)
    assert (r.ano, r.mes) == (2026, 7)


def test_baixar_dataframe_filtra_educacao_e_remove_vazios():
    sess = _SessaoFake(
        {
            "package_show": _RespFake(js=_PACKAGE),
            "2026_7_remuneracao_ativos.json": _RespFake(js=_FOLHA),
        }
    )
    rec = ft.recurso_mais_recente(tipo="ativos", sessao=sess)
    df = ft.baixar_dataframe(rec, filtro_instituicao="EDUCAC", sessao=sess)

    assert list(df.columns[:4]) == ["Nome Completo", "Matrícula", "Cargo", "Instituição"]
    nomes = set(df["Nome Completo"])
    assert nomes == {"MARIA JOSE DA SILVA LIMA", "JOAO PAULO DE SOUZA"}  # saúde e vazio fora


def test_baixar_dataframe_sem_filtro_traz_todos():
    sess = _SessaoFake(
        {
            "package_show": _RespFake(js=_PACKAGE),
            "2026_7_remuneracao_ativos.json": _RespFake(js=_FOLHA),
        }
    )
    rec = ft.recurso_mais_recente(tipo="ativos", sessao=sess)
    df = ft.baixar_dataframe(rec, filtro_instituicao=None, sessao=sess)
    assert len(df) == 3  # 4 registros - 1 nome vazio


def test_baixar_dataframe_colunas_faltando():
    sess = _SessaoFake(
        {
            "package_show": _RespFake(js=_PACKAGE),
            "2026_7_remuneracao_ativos.json": _RespFake(js={"campos": [{"x": 1}]}),
        }
    )
    rec = ft.recurso_mais_recente(tipo="ativos", sessao=sess)
    with pytest.raises(RuntimeError, match="colunas esperadas"):
        ft.baixar_dataframe(rec, sessao=sess)


def test_para_csv_bytes_roundtrip():
    sess = _SessaoFake(
        {
            "package_show": _RespFake(js=_PACKAGE),
            "2026_7_remuneracao_ativos.json": _RespFake(js=_FOLHA),
        }
    )
    rec = ft.recurso_mais_recente(tipo="ativos", sessao=sess)
    df = ft.baixar_dataframe(rec, sessao=sess)
    b = ft.para_csv_bytes(df)
    assert b.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM
    assert b"Nome Completo;" in b
    assert "MARIA JOSE DA SILVA LIMA".encode() in b
