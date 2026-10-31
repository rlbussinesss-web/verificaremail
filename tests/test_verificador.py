"""Testes da confirmação de caixa postal por fonte autorizada."""

import pandas as pd

from src.email_generator import aplicar_confirmacao, processar, resumir
from src.verificador_autorizado import (
    CONFIRMADA,
    NAO_CONSTA,
    NAO_VERIFICAVEL,
    VerificadorIndisponivel,
    VerificadorListaLocal,
    extrair_emails,
    obter_verificador,
)

DOM = "@professor.educacao.pe.gov.br"


def test_extrair_emails_de_texto_colado():
    texto = """
    Segue a lista:
      wagney.aalmeida@professor.educacao.pe.gov.br
      elizabete.msilva@professor.educacao.pe.gov.br ;  MARLI.MSLIMA@PROFESSOR.EDUCACAO.PE.GOV.BR
    (sem e-mail nesta linha)
    """
    achados = extrair_emails(texto)
    assert achados == [
        "wagney.aalmeida" + DOM,
        "elizabete.msilva" + DOM,
        "marli.mslima" + DOM,
    ]


def test_extrair_emails_remove_duplicados():
    texto = "a.bc@x.com\na.bc@x.com\nA.BC@X.COM"
    assert extrair_emails(texto) == ["a.bc@x.com"]


def test_extrair_emails_vazio():
    assert extrair_emails("") == []
    assert extrair_emails("nenhum endereco aqui") == []


def test_verificador_indisponivel_nunca_confirma():
    v = VerificadorIndisponivel()
    assert v.disponivel() is False
    r = v.confirmar(["qualquer.coisa" + DOM])
    assert r["qualquer.coisa" + DOM]["existe"] is None


def test_obter_verificador_sem_lista():
    assert obter_verificador().disponivel() is False
    assert obter_verificador([]).disponivel() is False
    assert obter_verificador(["x.y" + DOM]).disponivel() is True


def test_lista_local_confere_ignorando_caixa():
    v = VerificadorListaLocal(["  MARLI.MSLIMA" + DOM.upper() + "  "])
    assert v.disponivel() is True
    assert len(v) == 1
    assert v.contem("marli.mslima" + DOM) is True
    assert v.contem("outra.pessoa" + DOM) is False


def _df(nomes):
    return pd.DataFrame({"Nome Completo": nomes})


def test_aplicar_confirmacao_marca_apenas_a_lista():
    df = _df(["JOSE ALESSANDRO CAETANO DA SILVA", "MARIA JOSE DA SILVA LIMA", ""])
    res, _ = processar(df, "Nome Completo")

    v = VerificadorListaLocal(["jose.acsilva" + DOM])
    n = aplicar_confirmacao(res, v)

    assert n == 1
    m = res.set_index("Nome Original")["Caixa Postal"]
    assert m["JOSE ALESSANDRO CAETANO DA SILVA"] == CONFIRMADA
    assert m["MARIA JOSE DA SILVA LIMA"] == NAO_CONSTA
    # registro sem e-mail não pode ser nem confirmado nem "não consta"
    assert m[""] == NAO_VERIFICAVEL

    assert resumir(res)["confirmados"] == 1


def test_aplicar_confirmacao_sem_lista_volta_para_nao_verificavel():
    df = _df(["JOSE ALESSANDRO CAETANO DA SILVA"])
    res, _ = processar(df, "Nome Completo")
    n = aplicar_confirmacao(res, VerificadorIndisponivel())
    assert n == 0
    assert res.iloc[0]["Caixa Postal"] == NAO_VERIFICAVEL
    assert resumir(res)["confirmados"] == 0


def test_confirmacao_nao_inventa_para_email_parecido():
    """Um e-mail quase igual NÃO pode ser dado como confirmado."""
    df = _df(["FERNANDO ANTONIO GALDINO DA SILVA"])  # -> fernando.agsilva
    res, _ = processar(df, "Nome Completo")
    v = VerificadorListaLocal(["fernando.asilva" + DOM])  # parecido, mas outro
    assert aplicar_confirmacao(res, v) == 0
    assert res.iloc[0]["Caixa Postal"] == NAO_CONSTA
