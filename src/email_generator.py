"""Geração dos e-mails institucionais e montagem da tabela de resultados.

Regra da parte local (tudo minúsculo):

    PRIMEIRO_NOME + "." + INICIAIS_DOS_INTERMEDIARIOS_VALIDOS + ULTIMO_SOBRENOME

Partículas (da, de, do, das, dos, e) não geram inicial.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Callable, NamedTuple, Optional

import pandas as pd

from .config import AppConfig
from .name_parser import classificar_nome, normalizar_nome, tokenizar
from .validator import validar_formato, validar_dominio
from .verificador_autorizado import (
    CONFIRMADA,
    NAO_CONSTA,
    NAO_VERIFICAVEL,
    VerificadorContas,
)

CAIXA_POSTAL_TEXTO = NAO_VERIFICAVEL

COLUNAS_SAIDA = [
    "Nome Original",
    "Nome Normalizado",
    "Email Gerado",
    "Status",
    "Revisão",
    "Motivo",
    "Qtd Registros",
    "Matrículas",
    "Cargo",
    "Formato Válido",
    "Domínio Válido",
    "Caixa Postal",
    "Conflito Com",
]


class ResultadoEmail(NamedTuple):
    parte_local: str
    gerado: bool
    motivos: tuple


@lru_cache(maxsize=200_000)
def _montar_parte_local(tokens: tuple, particulas: frozenset) -> ResultadoEmail:
    n = len(tokens)

    if n == 0:
        return ResultadoEmail("", False, ("Sem nome — e-mail não gerado",))
    if n == 1:
        return ResultadoEmail("", False, ("Apenas um nome — e-mail não gerado",))

    primeiro = tokens[0]
    ultimo = tokens[-1]
    intermediarios = tokens[1:-1]

    if n == 2:
        return ResultadoEmail(f"{primeiro}.{ultimo}", True, ())

    motivos: list[str] = []
    if ultimo in particulas:
        motivos.append("Último sobrenome é uma partícula — conferir")

    intermediarios_validos = [t for t in intermediarios if t not in particulas]
    iniciais = "".join(t[0] for t in intermediarios_validos if t)

    if not intermediarios_validos:
        parte_local = f"{primeiro}.{ultimo}"
        motivos.append("Sem nomes intermediários válidos (todos partícula)")
    else:
        parte_local = f"{primeiro}.{iniciais}{ultimo}"

    return ResultadoEmail(parte_local, True, tuple(motivos))


def gerar_email(nome: str, config: Optional[AppConfig] = None) -> str:
    """Atalho: nome completo -> e-mail institucional completo (ou "" se não der)."""
    config = config or AppConfig()
    tokens = tuple(tokenizar(normalizar_nome(nome)))
    r = _montar_parte_local(tokens, frozenset(config.particulas_set()))
    if not r.gerado:
        return ""
    return f"{r.parte_local}@{config.dominio_normalizado()}"


# --------------------------------------------------------------------------- #
# Pipeline sobre DataFrame
# --------------------------------------------------------------------------- #
def _texto(valor) -> str:
    if valor is None:
        return ""
    try:
        if valor != valor:  # NaN
            return ""
    except TypeError:
        pass
    return str(valor).strip()


def processar(
    df: pd.DataFrame,
    coluna_nome: str,
    *,
    config: Optional[AppConfig] = None,
    coluna_cargo: Optional[str] = None,
    coluna_matricula: Optional[str] = None,
    progresso: Optional[Callable[[float, str], None]] = None,
) -> pd.DataFrame:
    """Processa o DataFrame de entrada e devolve a tabela de resultados.

    `progresso` (opcional) é chamado como progresso(fracao_0a1, mensagem).
    """
    config = config or AppConfig()
    particulas = frozenset(config.particulas_set())
    particulas_set = set(particulas)
    sufixos = config.sufixos_set()
    dominio = config.dominio_normalizado()
    prefixo_cargo = (config.prefixo_cargo_docente or "").strip().upper()

    def _prog(frac: float, msg: str) -> None:
        if progresso:
            progresso(max(0.0, min(1.0, frac)), msg)

    _prog(0.02, "Lendo coluna de nomes...")
    originais = df[coluna_nome].map(_texto)
    cargos = df[coluna_cargo].map(_texto) if coluna_cargo and coluna_cargo in df.columns else None
    matriculas = (
        df[coluna_matricula].map(_texto)
        if coluna_matricula and coluna_matricula in df.columns
        else None
    )

    _prog(0.12, "Normalizando nomes...")
    # normaliza apenas os valores únicos e reaproveita (rápido p/ 100k+ linhas)
    mapa_norm = {v: normalizar_nome(v) for v in originais.unique()}
    normalizados = originais.map(mapa_norm)

    trabalho = pd.DataFrame(
        {
            "orig": originais.values,
            "norm": normalizados.values,
            "cargo": cargos.values if cargos is not None else "",
            "matricula": matriculas.values if matriculas is not None else "",
        }
    )

    _prog(0.25, "Agrupando registros...")
    com_nome = trabalho[trabalho["norm"] != ""]
    sem_nome = trabalho[trabalho["norm"] == ""]

    registros: list[dict] = []

    if config.colapsar_por_pessoa:
        agg = (
            com_nome.groupby("norm", sort=False)
            .agg(
                orig=("orig", "first"),
                qtd=("orig", "size"),
                cargos=("cargo", list),
                matriculas=("matricula", list),
            )
            .reset_index()
        )
        for row in agg.itertuples(index=False):
            registros.append(
                {
                    "orig": row.orig,
                    "norm": row.norm,
                    "qtd": int(row.qtd),
                    "cargos": sorted({c for c in row.cargos if c}),
                    "matriculas": sorted({m for m in row.matriculas if m}),
                }
            )
    else:
        contagem = com_nome["norm"].value_counts()
        for row in com_nome.itertuples(index=False):
            registros.append(
                {
                    "orig": row.orig,
                    "norm": row.norm,
                    "qtd": int(contagem.get(row.norm, 1)),
                    "cargos": [row.cargo] if row.cargo else [],
                    "matriculas": [row.matricula] if row.matricula else [],
                }
            )

    for row in sem_nome.itertuples(index=False):
        registros.append(
            {
                "orig": row.orig,
                "norm": "",
                "qtd": 1,
                "cargos": [row.cargo] if row.cargo else [],
                "matriculas": [row.matricula] if row.matricula else [],
            }
        )

    total = max(1, len(registros))
    linhas: list[dict] = []

    for i, reg in enumerate(registros):
        if i % 2000 == 0:
            _prog(0.3 + 0.5 * (i / total), f"Gerando e-mails ({i:,}/{total:,})...")

        norm = reg["norm"]
        tokens = tokenizar(norm)
        classe = classificar_nome(
            reg["orig"],
            norm,
            tokens,
            sufixos_revisao=sufixos,
            particulas=particulas_set,
            min_len_nome=config.min_len_nome,
            max_tokens_nome=config.max_tokens_nome,
        )

        res = _montar_parte_local(tuple(tokens), particulas)
        for m in res.motivos:
            classe.marcar(m)

        email = f"{res.parte_local}@{dominio}" if res.gerado else ""

        # checagem de cargo (agregada): só marca revisão se o usuário pedir.
        # Por padrão o e-mail vale mesmo para quem não é professor.
        cargos = reg["cargos"]
        if config.revisar_nao_docente and coluna_cargo and coluna_cargo in df.columns:
            if not cargos:
                classe.marcar("Cargo não informado")
            elif not any(c.upper().startswith(prefixo_cargo) for c in cargos):
                classe.marcar(f"Cargo não é PROFESSOR: {', '.join(cargos)}")

        if not norm:
            status = "INVÁLIDO"
        elif reg["qtd"] > 1:
            status = "DUPLICADO"
        else:
            status = "OK"

        fmt_ok = validar_formato(email) if email else False

        linhas.append(
            {
                "Nome Original": reg["orig"],
                "Nome Normalizado": norm,
                "Email Gerado": email,
                "Status": status,
                "Revisão": classe.status_revisao,
                "Motivo": classe.motivo_texto,
                "Qtd Registros": reg["qtd"],
                "Matrículas": ", ".join(reg["matriculas"]),
                "Cargo": " | ".join(cargos),
                "Formato Válido": "Sim" if fmt_ok else "Não",
                "Domínio Válido": "",  # preenchido abaixo (uma vez por domínio)
                "Caixa Postal": CAIXA_POSTAL_TEXTO,
                "Conflito Com": "",
            }
        )

    resultado = pd.DataFrame(linhas, columns=COLUNAS_SAIDA)

    if config.descartar_conflitos:
        _prog(0.85, "Removendo e-mails duplicados por conflito...")
        removidos = _descartar_conflitos(resultado)
    else:
        _prog(0.85, "Detectando conflitos de e-mail...")
        _marcar_conflitos(resultado)
        removidos = resultado.iloc[0:0].copy()

    _prog(0.92, "Validando domínio...")
    dom_status = validar_dominio(dominio, verificar_mx=config.verificar_mx)
    resultado.loc[resultado["Email Gerado"] != "", "Domínio Válido"] = dom_status
    resultado.loc[resultado["Email Gerado"] == "", "Domínio Válido"] = "—"

    _prog(1.0, "Concluído.")
    return resultado, removidos


def _marcar_conflitos(resultado: pd.DataFrame) -> None:
    """Marca CONFLITO quando nomes normalizados diferentes geram o mesmo e-mail.

    Totalmente vetorizado: o laço final percorre apenas as linhas em conflito.
    """
    mask = (resultado["Email Gerado"] != "").to_numpy()
    if not mask.any():
        return

    sub = resultado.loc[mask, ["Email Gerado", "Nome Normalizado"]]
    n_distintos = sub.groupby("Email Gerado")["Nome Normalizado"].transform("nunique")
    idx_conf = sub.index[n_distintos.to_numpy() > 1]
    if len(idx_conf) == 0:
        return

    emails_conf = resultado.loc[idx_conf, "Email Gerado"].unique()
    mapa = (
        sub[sub["Email Gerado"].isin(emails_conf)]
        .groupby("Email Gerado")["Nome Normalizado"]
        .agg(lambda s: sorted(set(s)))
        .to_dict()
    )

    resultado.loc[idx_conf, "Status"] = "CONFLITO"
    resultado.loc[idx_conf, "Revisão"] = "REVISAR"

    conflito_com: list[str] = []
    motivos: list[str] = []
    for i in idx_conf:
        este = resultado.at[i, "Nome Normalizado"]
        outros = [n for n in mapa[resultado.at[i, "Email Gerado"]] if n != este]
        conflito_com.append("; ".join(outros))
        aviso = f"CONFLITO DE EMAIL com: {', '.join(outros)}"
        m = resultado.at[i, "Motivo"]
        motivos.append(f"{m}; {aviso}" if m else aviso)

    resultado.loc[idx_conf, "Conflito Com"] = conflito_com
    resultado.loc[idx_conf, "Motivo"] = motivos


def _descartar_conflitos(resultado: pd.DataFrame) -> pd.DataFrame:
    """Quando um e-mail serve a 2+ nomes distintos, mantém a 1ª linha (ordem do
    CSV) e REMOVE as demais de `resultado`. Devolve as linhas removidas.
    """
    vazio = resultado.iloc[0:0].copy()
    vazio["Mantido Para"] = pd.Series(dtype="object")

    mask = (resultado["Email Gerado"] != "").to_numpy()
    if not mask.any():
        return vazio

    sub = resultado.loc[mask, ["Email Gerado", "Nome Normalizado"]]
    n_distintos = sub.groupby("Email Gerado")["Nome Normalizado"].transform("nunique")
    idx_conf = sub.index[n_distintos.to_numpy() > 1]
    if len(idx_conf) == 0:
        return vazio

    conf = resultado.loc[idx_conf]
    manter_idx = conf.groupby("Email Gerado", sort=False).head(1).index
    remover_idx = conf.index.difference(manter_idx)
    if len(remover_idx) == 0:
        return vazio

    mant = (
        resultado.loc[manter_idx, ["Email Gerado", "Nome Original"]]
        .set_index("Email Gerado")["Nome Original"]
        .to_dict()
    )
    removidos = resultado.loc[remover_idx].copy()
    removidos["Mantido Para"] = removidos["Email Gerado"].map(mant)
    removidos["Status"] = "REMOVIDO (conflito)"
    removidos["Motivo"] = [
        (m + "; " if m else "") + f"E-mail já atribuído a: {mp}"
        for m, mp in zip(removidos["Motivo"].astype(str), removidos["Mantido Para"])
    ]

    resultado.drop(index=remover_idx, inplace=True)
    resultado.reset_index(drop=True, inplace=True)
    return removidos.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Confirmação por fonte autorizada
# --------------------------------------------------------------------------- #
def aplicar_confirmacao(
    resultado: pd.DataFrame, verificador: VerificadorContas
) -> int:
    """Preenche a coluna 'Caixa Postal' usando uma fonte autorizada.

    Só marca CONFIRMADA o que a fonte afirma existir. O resto vira
    "Não consta na lista" — que NÃO é o mesmo que "não existe".
    Devolve quantos foram confirmados.
    """
    if not verificador.disponivel() or resultado.empty:
        resultado["Caixa Postal"] = NAO_VERIFICAVEL
        return 0

    emails = resultado["Email Gerado"]
    checagem = verificador.confirmar([e for e in emails if e])
    confirmados = {e for e, d in checagem.items() if d.get("existe") is True}

    resultado["Caixa Postal"] = [
        CONFIRMADA if e in confirmados else (NAO_CONSTA if e else NAO_VERIFICAVEL)
        for e in emails
    ]
    return len(confirmados)


# --------------------------------------------------------------------------- #
# Estatísticas
# --------------------------------------------------------------------------- #
def resumir(
    resultado: pd.DataFrame,
    total_linhas_arquivo: Optional[int] = None,
    removidos_conflito: Optional[pd.DataFrame] = None,
) -> dict:
    """Contagens usadas nos cartões de métrica e na seção de estatísticas."""
    emails_validos = resultado[resultado["Email Gerado"] != ""]
    n_removidos = 0 if removidos_conflito is None else int(len(removidos_conflito))
    return {
        "descartados_conflito": n_removidos,
        "confirmados": int((resultado["Caixa Postal"] == CONFIRMADA).sum()),
        "linhas_arquivo": total_linhas_arquivo
        if total_linhas_arquivo is not None
        else int(resultado["Qtd Registros"].sum()),
        "registros_processados": int(len(resultado)),
        "nomes_unicos": int(resultado["Nome Normalizado"].replace("", pd.NA).nunique()),
        "emails_gerados": int(len(emails_validos)),
        "emails_unicos": int(emails_validos["Email Gerado"].nunique()),
        "validos": int((resultado["Status"].isin(["OK", "DUPLICADO"])).sum()),
        "duplicados": int((resultado["Status"] == "DUPLICADO").sum()),
        "conflitos": int((resultado["Status"] == "CONFLITO").sum()),
        "invalidos": int((resultado["Status"] == "INVÁLIDO").sum()),
        "revisar": int((resultado["Revisão"] == "REVISAR").sum()),
        "ok": int((resultado["Revisão"] == "OK").sum()),
    }
