"""Busca a lista de servidores direto da API de Dados Abertos de PE (CKAN).

O Portal da Transparência de Pernambuco publica a folha de pagamento mensal
completa do estado como um dataset CKAN em ``dados.pe.gov.br``. Aqui a gente:

1. descobre, via API, qual é o recurso (mês) mais recente;
2. baixa o JSON/CSV desse recurso;
3. devolve só Nome / Matrícula / Cargo, filtrando por instituição
   (por padrão, a Secretaria de Educação).

Assim o app não precisa mais de um CSV baixado à mão.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import Callable, Optional

import pandas as pd
import requests
import streamlit as st

CKAN_BASE = "https://dados.pe.gov.br"
PACKAGE_ID = "remuneracao-de-servidores"
TIMEOUT = 180
FILTRO_EDUCACAO_PADRAO = "EDUCAC"

_RE_RECURSO = re.compile(r"(\d{4})_(\d{1,2})_remuneracao_(ativos|inativos)", re.I)

Progresso = Optional[Callable[[float, str], None]]


@dataclass(frozen=True)
class RecursoFolha:
    """Um arquivo mensal da folha (ativos ou inativos) publicado no CKAN."""

    ano: int
    mes: int
    tipo: str  # "ativos" | "inativos"
    formato: str  # "JSON" | "CSV"
    url: str
    nome: str

    @property
    def rotulo(self) -> str:
        mes = "13º (natalina)" if self.mes == 13 else f"{self.mes:02d}"
        return f"{mes}/{self.ano} — {self.tipo}"


# --------------------------------------------------------------------------- #
# Descoberta de recursos
# --------------------------------------------------------------------------- #
def _package_show(sessao: requests.Session) -> dict:
    resp = sessao.get(
        f"{CKAN_BASE}/api/3/action/package_show",
        params={"id": PACKAGE_ID},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    corpo = resp.json()
    if not corpo.get("success"):
        raise RuntimeError("A API de dados abertos respondeu, mas sem sucesso.")
    return corpo["result"]


def listar_recursos(
    tipo: str = "ativos",
    formato: str = "JSON",
    sessao: Optional[requests.Session] = None,
) -> list[RecursoFolha]:
    """Lista os meses disponíveis do tipo pedido, do mais novo para o mais antigo."""
    fechar = sessao is None
    sessao = sessao or requests.Session()
    try:
        resultado = _package_show(sessao)
    finally:
        if fechar:
            sessao.close()

    achados: list[RecursoFolha] = []
    for rec in resultado.get("resources", []):
        if (rec.get("format") or "").upper() != formato.upper():
            continue
        url = rec.get("url") or ""
        m = _RE_RECURSO.search(url) or _RE_RECURSO.search(rec.get("name") or "")
        if not m or m.group(3).lower() != tipo.lower():
            continue
        achados.append(
            RecursoFolha(
                ano=int(m.group(1)),
                mes=int(m.group(2)),
                tipo=m.group(3).lower(),
                formato=formato.upper(),
                url=url,
                nome=rec.get("name") or url.rsplit("/", 1)[-1],
            )
        )

    achados.sort(key=lambda r: (r.ano, r.mes), reverse=True)
    # remove meses repetidos (mantém o 1º, que é o mais recente/again)
    vistos: set[tuple[int, int]] = set()
    unicos: list[RecursoFolha] = []
    for r in achados:
        chave = (r.ano, r.mes)
        if chave in vistos:
            continue
        vistos.add(chave)
        unicos.append(r)
    return unicos


def recurso_mais_recente(
    tipo: str = "ativos", sessao: Optional[requests.Session] = None
) -> RecursoFolha:
    recursos = listar_recursos(tipo=tipo, sessao=sessao)
    if not recursos:
        raise RuntimeError("Nenhum recurso de folha encontrado na API de dados abertos.")
    return recursos[0]


# --------------------------------------------------------------------------- #
# Download + normalização
# --------------------------------------------------------------------------- #
_RENOMEAR = {
    "r_nome": "Nome Completo",
    "r_matricula": "Matrícula",
    "r_cargo": "Cargo",
    "r_categoria": "Categoria",
    "r_instituicao": "Instituição",
}


def baixar_dataframe(
    recurso: RecursoFolha,
    filtro_instituicao: Optional[str] = FILTRO_EDUCACAO_PADRAO,
    progresso: Progresso = None,
    sessao: Optional[requests.Session] = None,
) -> pd.DataFrame:
    """Baixa um recurso mensal e devolve um DataFrame com colunas de nome/cargo.

    ``filtro_instituicao`` é comparado (case-insensitive, ``contains``) contra a
    coluna de instituição. ``None`` traz o estado inteiro.
    """

    def _p(frac: float, msg: str) -> None:
        if progresso:
            progresso(max(0.0, min(1.0, frac)), msg)

    fechar = sessao is None
    sessao = sessao or requests.Session()
    try:
        _p(0.05, f"Baixando folha {recurso.rotulo} da Transparência de PE...")
        resp = sessao.get(recurso.url, timeout=TIMEOUT)
        resp.raise_for_status()

        _p(0.55, "Lendo os dados recebidos...")
        if recurso.formato == "JSON":
            corpo = resp.json()
            registros = (
                corpo.get("campos")
                or corpo.get("records")
                or corpo.get("result", {}).get("records")
                if isinstance(corpo, dict)
                else corpo
            )
            df = pd.DataFrame(registros)
        else:
            df = pd.read_csv(
                io.BytesIO(resp.content),
                sep=";",
                dtype=str,
                encoding="latin-1",
                keep_default_na=False,
            )
    finally:
        if fechar:
            sessao.close()

    df = df.rename(columns=_RENOMEAR)
    faltando = {"Nome Completo", "Instituição"} - set(df.columns)
    if faltando:
        raise RuntimeError(
            "A resposta da API não trouxe as colunas esperadas "
            f"({', '.join(sorted(faltando))}). O formato do dado pode ter mudado."
        )

    _p(0.8, "Filtrando e limpando...")
    if filtro_instituicao:
        alvo = filtro_instituicao.strip().upper()
        df = df[df["Instituição"].astype(str).str.upper().str.contains(alvo, na=False)]

    colunas = [
        c
        for c in ["Nome Completo", "Matrícula", "Cargo", "Categoria", "Instituição"]
        if c in df.columns
    ]
    df = df[colunas].copy()
    for c in colunas:
        df[c] = df[c].astype(str).str.strip()
    df = df[df["Nome Completo"] != ""].reset_index(drop=True)

    _p(1.0, f"{len(df):,} servidores carregados.".replace(",", "."))
    return df


def para_csv_bytes(df: pd.DataFrame) -> bytes:
    """Serializa o DataFrame como CSV (``;``, UTF-8 com BOM) para reentrar no pipeline."""
    buf = io.StringIO()
    df.to_csv(buf, sep=";", index=False)
    return buf.getvalue().encode("utf-8-sig")


PENTAHO_BASE = "https://api.pentaho.transparencia.pe.gov.br"
PENTAHO_DASH_URL = (
    f"{PENTAHO_BASE}/pentaho/api/repos/%3Apublic%3AOpenReports%3APortal_Producao"
    "%3APainel_cadastro_servidores%3APainel_cadastro_servidores.wcdf/generatedContent"
)
PENTAHO_CDA_PATH = "/public/OpenReports/Portal_Producao/Painel_cadastro_servidores/Painel_cadastro_servidores.cda"


@st.cache_data(show_spinner=False, ttl=3600)
def consultar_painel_cadastro(
    lotacao: str = "SECRETARIA DE EDUCACAO",
    ano: str = "0",
    mes: str = "0",
    matricula: str = "",
    nome_servidor: str = "",
) -> pd.DataFrame:
    """Consulta diretamente o backend do Painel de Cadastro dos Servidores da Transparência de PE.
    
    Retorna o DataFrame completo com todos os servidores cadastrados (ex: 65.483 servidores da Educação).
    """
    sessao = requests.Session()
    sessao.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": PENTAHO_BASE,
        "Referer": PENTAHO_DASH_URL,
    })

    try:
        # 1. Obtém sessão/cookie do dashboard com timeout de 30s
        try:
            sessao.get(PENTAHO_DASH_URL, timeout=30, verify=False)
        except Exception:
            pass

        payload = {
            "parampara_ano": ano if ano != "Todos" else "0",
            "paramoffset_": "0",
            "paramlimit_": "100000",
            "paramoutros": "1",
            "parampara_mes": mes if mes != "Todos" else "0",
            "parampara_lotacao": lotacao.strip(),
            "parampara_matricula": matricula.strip(),
            "parampara_nome_completo": nome_servidor.strip(),
            "path": PENTAHO_CDA_PATH,
            "dataAccessId": "sql_jndi",
            "outputIndexId": "1",
            "pageSize": "0",
            "pageStart": "0",
            "sortBy": "",
            "paramsearchBox": "",
        }

        url_query = f"{PENTAHO_BASE}/pentaho/plugin/cda/api/doQuery?"
        resp = sessao.post(url_query, data=payload, timeout=45, verify=False)
        resp.raise_for_status()

        dados = resp.json()
        colunas_meta = [c["colName"] for c in dados.get("metadata", [])]
        linhas = dados.get("resultset", [])

        mapa_colunas = {
            "matricula": "Matrícula",
            "nome_servidor": "Nome Completo",
            "cargo": "Cargo",
            "nome_setor": "Instituição",
            "data_contratacao": "Data de Admissão",
            "data_exoneracao": "Data de Exoneração",
            "data_aposentadoria": "Data de Inativação",
            "carga_horaria_semanal": "Carga Horária",
        }

        df = pd.DataFrame(linhas, columns=colunas_meta)
        df.rename(columns=mapa_colunas, inplace=True)

        for col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace("None", "").replace("nan", "")

        _p(1.0, f"{len(df):,} servidores carregados com sucesso!".replace(",", "."))
        return df

    finally:
        if fechar:
            sessao.close()
