"""Exportação dos resultados para CSV (Excel BR) e XLSX formatado."""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

PASTA_EXPORTS = Path(__file__).resolve().parent.parent / "exports"

# Colunas tratadas como texto no XLSX (não devem virar número/data).
_COLUNAS_TEXTO = {"Email Gerado", "Matrículas", "Nome Normalizado"}


def _carimbo() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# --------------------------------------------------------------------------- #
# CSV
# --------------------------------------------------------------------------- #
def csv_bytes(df: pd.DataFrame, *, sep: str = ";") -> bytes:
    """CSV em UTF-8 com BOM — abre com acentos corretos no Excel brasileiro."""
    buf = io.StringIO()
    df.to_csv(buf, sep=sep, index=False, lineterminator="\r\n")
    return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")


def exportar_csv(
    df: pd.DataFrame, nome_base: str = "emails", *, sep: str = ";",
    pasta: Optional[Path] = None,
) -> Path:
    pasta = Path(pasta or PASTA_EXPORTS)
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"{nome_base}_{_carimbo()}.csv"
    destino.write_bytes(csv_bytes(df, sep=sep))
    return destino


# --------------------------------------------------------------------------- #
# XLSX
# --------------------------------------------------------------------------- #
def xlsx_bytes(df: pd.DataFrame, *, nome_aba: str = "Emails") -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        _escrever_planilha(df, writer, nome_aba)
    return buf.getvalue()


def exportar_xlsx(
    df: pd.DataFrame, nome_base: str = "emails", *, pasta: Optional[Path] = None,
) -> Path:
    pasta = Path(pasta or PASTA_EXPORTS)
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"{nome_base}_{_carimbo()}.xlsx"
    destino.write_bytes(xlsx_bytes(df))
    return destino


def _escrever_planilha(df: pd.DataFrame, writer: pd.ExcelWriter, nome_aba: str) -> None:
    df = df.copy()
    df.to_excel(writer, sheet_name=nome_aba, index=False, startrow=1, header=False)

    livro = writer.book
    aba = writer.sheets[nome_aba]

    fmt_cabecalho = livro.add_format(
        {"bold": True, "bg_color": "#1F4E78", "font_color": "white",
         "border": 1, "align": "left", "valign": "vcenter"}
    )
    fmt_texto = livro.add_format({"num_format": "@"})
    fmt_revisar = livro.add_format({"bg_color": "#FFF2CC"})
    fmt_conflito = livro.add_format({"bg_color": "#F8CBAD"})

    n_linhas, n_colunas = df.shape

    # cabeçalho em negrito
    for c, nome in enumerate(df.columns):
        aba.write(0, c, str(nome), fmt_cabecalho)

    # largura das colunas + e-mail/afins como texto
    for c, nome in enumerate(df.columns):
        serie = df[nome].astype(str)
        largura = min(60, max(len(str(nome)), int(serie.map(len).max() or 0)) + 2)
        if nome in _COLUNAS_TEXTO:
            aba.set_column(c, c, largura, fmt_texto)
        else:
            aba.set_column(c, c, largura)

    # painel congelado + autofiltro
    aba.freeze_panes(1, 0)
    if n_linhas >= 0:
        aba.autofilter(0, 0, max(n_linhas, 1), max(n_colunas - 1, 0))

    # destaque de linhas que exigem atenção
    if n_linhas > 0 and "Revisão" in df.columns:
        col_rev = df.columns.get_loc("Revisão")
        letra = _letra_coluna(col_rev)
        aba.conditional_format(
            1, 0, n_linhas, n_colunas - 1,
            {"type": "formula",
             "criteria": f'=${letra}2="REVISAR"',
             "format": fmt_revisar},
        )
    if n_linhas > 0 and "Status" in df.columns:
        col_st = df.columns.get_loc("Status")
        letra = _letra_coluna(col_st)
        aba.conditional_format(
            1, 0, n_linhas, n_colunas - 1,
            {"type": "formula",
             "criteria": f'=${letra}2="CONFLITO"',
             "format": fmt_conflito},
        )


def _letra_coluna(idx: int) -> str:
    letras = ""
    idx += 1
    while idx:
        idx, resto = divmod(idx - 1, 26)
        letras = chr(65 + resto) + letras
    return letras
