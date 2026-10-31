"""Leitura robusta de CSV com detecção automática.

Descobre, sem depender de configuração do usuário:
  * encoding (UTF-8 com/sem BOM, cp1252, latin-1);
  * delimitador (`;`, `,`, tab, `|`);
  * a linha real do cabeçalho (o arquivo pode ter linhas de título antes);
  * qual coluna contém o nome completo.

Nada aqui altera o arquivo de origem — ele é aberto somente para leitura.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Dict, List, Optional

import pandas as pd

_DELIMITADORES = [";", ",", "\t", "|"]
_RE_CABECALHO_NOME = re.compile(r"nome|servidor|professor|docente|completo|servidora")
_RE_TOKEN_ALFA = re.compile(r"^[A-Za-zÀ-ÿ.]+$")


@dataclass
class ResultadoLeitura:
    df: pd.DataFrame
    encoding: str
    delimitador: str
    linha_cabecalho: int  # 0-based, dentro do arquivo bruto
    coluna_nome: Optional[str]
    coluna_cargo: Optional[str] = None
    coluna_matricula: Optional[str] = None
    scores_colunas: Dict[str, float] = field(default_factory=dict)

    @property
    def n_linhas(self) -> int:
        return int(len(self.df))

    @property
    def colunas(self) -> List[str]:
        return [str(c) for c in self.df.columns]

    @property
    def delimitador_legivel(self) -> str:
        return {";": "ponto e vírgula (;)", ",": "vírgula (,)", "\t": "tabulação",
                "|": "barra vertical (|)"}.get(self.delimitador, repr(self.delimitador))


# --------------------------------------------------------------------------- #
# Entrada bruta
# --------------------------------------------------------------------------- #
def _ler_bytes(fonte) -> bytes:
    if isinstance(fonte, (bytes, bytearray)):
        return bytes(fonte)
    if hasattr(fonte, "read"):
        dados = fonte.read()
        return dados.encode("utf-8") if isinstance(dados, str) else bytes(dados)
    return Path(fonte).read_bytes()


# --------------------------------------------------------------------------- #
# Detecção de encoding
# --------------------------------------------------------------------------- #
def detectar_encoding(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass
    try:
        from charset_normalizer import from_bytes  # type: ignore

        melhor = from_bytes(raw).best()
        if melhor and melhor.encoding:
            enc = melhor.encoding.lower().replace("_", "-")
            if enc in ("ascii", "utf-8"):
                return "utf-8"
            return enc
    except Exception:
        pass
    for enc in ("cp1252", "latin-1"):
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "latin-1"


# --------------------------------------------------------------------------- #
# Detecção de delimitador
# --------------------------------------------------------------------------- #
def detectar_delimitador(amostra: str) -> str:
    linhas = [l for l in amostra.splitlines() if l.strip()][:40]
    if not linhas:
        return ";"

    try:
        dialeto = csv.Sniffer().sniff("\n".join(linhas), delimiters=";,\t|")
        if dialeto.delimiter in _DELIMITADORES:
            return dialeto.delimiter
    except csv.Error:
        pass

    melhor, melhor_score = ",", -1.0
    for d in _DELIMITADORES:
        contagens = [l.count(d) for l in linhas]
        if max(contagens, default=0) == 0:
            continue
        med = median(contagens)
        consistencia = sum(1 for c in contagens if c == med) / len(contagens)
        score = med * (0.5 + consistencia)
        if score > melhor_score:
            melhor, melhor_score = d, score
    return melhor


# --------------------------------------------------------------------------- #
# Detecção da linha de cabeçalho
# --------------------------------------------------------------------------- #
def detectar_linha_cabecalho(texto: str, delimitador: str, limite: int = 20) -> int:
    linhas = texto.splitlines()[:limite]
    melhor_fallback = None
    for i, linha in enumerate(linhas):
        if not linha.strip():
            continue
        try:
            campos = next(csv.reader([linha], delimiter=delimitador))
        except csv.Error:
            campos = linha.split(delimitador)
        campos = [c.strip().lower() for c in campos]
        if len(campos) >= 2 and any(_RE_CABECALHO_NOME.search(c) for c in campos if c):
            return i
        if melhor_fallback is None and linha.count(delimitador) >= 1:
            melhor_fallback = i
    return melhor_fallback or 0


# --------------------------------------------------------------------------- #
# Detecção da coluna de nome
# --------------------------------------------------------------------------- #
def _pontuar_cabecalho(nome_col: str) -> float:
    n = nome_col.strip().lower()
    if n in ("nome completo", "nome_completo", "nomecompleto"):
        return 100.0
    if "nome completo" in n:
        return 90.0
    if n in ("nome", "nome do servidor", "nome servidor"):
        return 75.0
    if "nome" in n:
        return 55.0
    if any(t in n for t in ("servidor", "professor", "docente", "funcionario")):
        return 40.0
    return 0.0


def _pontuar_conteudo(serie: pd.Series) -> float:
    amostra = serie.astype(str).map(str.strip)
    amostra = amostra[amostra != ""].head(300)
    if amostra.empty:
        return 0.0
    tokens = amostra.str.split().map(len)
    media = float(tokens.mean())
    frac_multi = float((tokens >= 2).mean())
    base = amostra.str.replace(r"[ .'\-]", "", regex=True)
    frac_alfa = float(base.map(lambda x: bool(_RE_TOKEN_ALFA.match(x)) if x else False).mean())

    s = 0.0
    if 2.0 <= media <= 6.0:
        s += 25.0
    elif media > 1.0:
        s += 8.0
    s += 15.0 * frac_multi
    s += 20.0 * frac_alfa
    return s


def detectar_coluna_nome(df: pd.DataFrame) -> tuple[Optional[str], Dict[str, float]]:
    scores: Dict[str, float] = {}
    for col in df.columns:
        scores[str(col)] = round(
            _pontuar_cabecalho(str(col)) + _pontuar_conteudo(df[col]), 2
        )
    if not scores:
        return None, {}
    melhor = max(scores, key=lambda k: scores[k])
    if scores[melhor] <= 0:
        return None, scores
    return melhor, scores


def _achar_coluna(df: pd.DataFrame, termos: List[str]) -> Optional[str]:
    for col in df.columns:
        cl = str(col).strip().lower()
        if any(t in cl for t in termos):
            return str(col)
    return None


def _campos(linha: str, delimitador: str) -> List[str]:
    try:
        return next(csv.reader([linha], delimiter=delimitador))
    except (csv.Error, StopIteration):
        return linha.split(delimitador)


def _dedupe(nomes: List[str]) -> List[str]:
    vistos: Dict[str, int] = {}
    saida: List[str] = []
    for i, n in enumerate(nomes):
        n = n.strip() or f"coluna_{i + 1}"
        if n in vistos:
            vistos[n] += 1
            saida.append(f"{n}.{vistos[n]}")
        else:
            vistos[n] = 0
            saida.append(n)
    return saida


# --------------------------------------------------------------------------- #
# Função principal
# --------------------------------------------------------------------------- #
def carregar_csv(fonte, *, coluna_nome_forcada: Optional[str] = None) -> ResultadoLeitura:
    """Lê `fonte` (caminho, bytes ou file-like) e devolve `ResultadoLeitura`."""
    raw = _ler_bytes(fonte)
    if not raw.strip():
        raise ValueError("Arquivo CSV vazio.")

    encoding = detectar_encoding(raw)
    texto = raw.decode(encoding, errors="replace")

    linhas_texto = texto.splitlines()
    amostra = "\n".join(linhas_texto[:60])
    delimitador = detectar_delimitador(amostra)
    linha_cabecalho = detectar_linha_cabecalho(texto, delimitador)

    # Nomes de coluna vêm do cabeçalho; contamos também os campos de uma linha de
    # dados para tratar o caso comum de delimitador sobrando no fim (1 campo extra).
    cabecalho = [c.strip() for c in _campos(linhas_texto[linha_cabecalho], delimitador)]
    n_dados = len(cabecalho)
    for l in linhas_texto[linha_cabecalho + 1 : linha_cabecalho + 30]:
        if l.strip():
            n_dados = len(_campos(l, delimitador))
            break
    if n_dados > len(cabecalho):
        cabecalho += [f"_extra_{i + 1}" for i in range(n_dados - len(cabecalho))]
    nomes = _dedupe(cabecalho)

    df = pd.read_csv(
        io.BytesIO(raw),
        sep=delimitador,
        dtype=str,
        keep_default_na=False,
        skiprows=linha_cabecalho + 1,
        header=None,
        names=nomes,
        encoding=encoding,
        engine="python",
        quotechar='"',
        skip_blank_lines=True,
        on_bad_lines="skip",
    )

    # limpa nomes de coluna e descarta colunas sem nome / totalmente vazias
    df.columns = [str(c).strip() for c in df.columns]
    manter = []
    for c in df.columns:
        nome_generico = (
            c == ""
            or c.lower().startswith("unnamed")
            or c.startswith("_extra_")
            or c.startswith("coluna_")
        )
        vazia_dados = (df[c].astype(str).str.strip() == "").all()
        if nome_generico and vazia_dados:
            continue
        manter.append(c)
    df = df[manter]
    df = df.reset_index(drop=True)

    coluna_nome, scores = detectar_coluna_nome(df)
    if coluna_nome_forcada and coluna_nome_forcada in df.columns:
        coluna_nome = coluna_nome_forcada

    return ResultadoLeitura(
        df=df,
        encoding=encoding,
        delimitador=delimitador,
        linha_cabecalho=linha_cabecalho,
        coluna_nome=coluna_nome,
        coluna_cargo=_achar_coluna(df, ["cargo", "função", "funcao", "func"]),
        coluna_matricula=_achar_coluna(df, ["matríc", "matric", "matrÃ", "registro", "cpf"]),
        scores_colunas=scores,
    )
