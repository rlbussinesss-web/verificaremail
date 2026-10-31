"""Interface simplificada: carregar, processar, tabela + bloco de 50 e exportacao.

Executar: streamlit run app.py
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import streamlit as st

from src.config import AppConfig, DOMINIO_PADRAO, PARTICULAS_PADRAO, SUFIXOS_REVISAO_PADRAO
from src.csv_reader import carregar_csv
from src.email_generator import processar, resumir
from src.exporter import csv_bytes, xlsx_bytes, exportar_csv, exportar_xlsx
from src.fonte_transparencia import (
    FILTRO_EDUCACAO_PADRAO,
    baixar_dataframe,
    consultar_painel_cadastro,
    listar_recursos,
    para_csv_bytes,
)
from src.utils import cronometro

RAIZ = Path(__file__).resolve().parent

st.set_page_config(
    page_title="Gerador de E-mails",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_data(show_spinner=False)
def _ler(dados_bytes: bytes, coluna_forcada: str | None):
    return carregar_csv(dados_bytes, coluna_nome_forcada=coluna_forcada)


@st.cache_data(show_spinner=False, ttl=3600)
def _listar_recursos_transparencia(tipo: str):
    return listar_recursos(tipo=tipo)


@st.cache_data(show_spinner=False, ttl=3600)
def _baixar_transparencia(url: str, rotulo: str, filtro: str) -> bytes:
    from src.fonte_transparencia import RecursoFolha

    ano = mes = 0
    tipo = "ativos"
    m = re.search(r"(\d{4})_(\d{1,2})_remuneracao_(ativos|inativos)", url)
    if m:
        ano, mes, tipo = int(m.group(1)), int(m.group(2)), m.group(3)
    rec = RecursoFolha(ano=ano, mes=mes, tipo=tipo, formato="JSON", url=url, nome=rotulo)
    return para_csv_bytes(baixar_dataframe(rec, filtro_instituicao=filtro or None))


def _processar_com_progresso(df, coluna_nome, coluna_cargo, coluna_matricula, config):
    barra = st.progress(0.0)
    txt = st.empty()

    def _prog(frac, msg):
        barra.progress(frac)
        txt.write(f"{msg}")

    with cronometro() as t:
        res, removidos = processar(
            df,
            coluna_nome,
            config=config,
            coluna_cargo=coluna_cargo,
            coluna_matricula=coluna_matricula,
            progresso=_prog,
        )
    barra.empty()
    txt.empty()
    return res, removidos, t.segundos


if "config" not in st.session_state or not isinstance(st.session_state.config, AppConfig):
    _cfg_init = AppConfig.carregar()
    # Para o painel coincidir com o site da Transparência, desligamos o agrupamento e o descarte
    _cfg_init.colapsar_por_pessoa = False
    _cfg_init.descartar_conflitos = False
    st.session_state.config = _cfg_init
_base = AppConfig()
for _campo in _base.__dataclass_fields__:
    if not hasattr(st.session_state.config, _campo):
        setattr(st.session_state.config, _campo, getattr(_base, _campo))
cfg: AppConfig = st.session_state.config



# Estilo Vercel All-Black Minimalista
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500;600;700&family=Geist+Mono:wght@400;500;600&display=swap');

    html, body, [data-testid="stAppViewContainer"], .main {
        background-color: #000000 !important;
        color: #ededed !important;
        font-family: 'Geist', -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif !important;
    }

    [data-testid="stHeader"] {
        background-color: rgba(0, 0, 0, 0.8) !important;
        backdrop-filter: blur(12px) !important;
        border-bottom: 1px solid #1a1a1a !important;
    }

    /* Container e cards estilo Vercel */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: #080808 !important;
        border: 1px solid #1f1f1f !important;
        border-radius: 12px !important;
        transition: border-color 0.2s ease !important;
    }
    [data-testid="stVerticalBlockBorderWrapper"]:hover {
        border-color: #333333 !important;
    }

    /* Inputs estilo Vercel */
    input, select, textarea {
        background-color: #0a0a0a !important;
        color: #ffffff !important;
        border: 1px solid #222222 !important;
        border-radius: 8px !important;
        font-size: 14px !important;
        transition: all 0.2s ease !important;
    }
    input:focus, select:focus, textarea:focus {
        border-color: #ffffff !important;
        box-shadow: 0 0 0 1px #ffffff !important;
    }

    /* Botão Primário Elegante Dark Vercel */
    button[kind="primary"], button[data-testid="baseButton-primary"] {
        background-color: #111111 !important;
        color: #ffffff !important;
        border: 1px solid #333333 !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
        font-size: 14px !important;
        letter-spacing: -0.01em !important;
        padding: 8px 20px !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.4) !important;
        transition: all 0.2s ease !important;
    }
    button[kind="primary"]:hover, button[data-testid="baseButton-primary"]:hover {
        background-color: #1a1a1a !important;
        border-color: #666666 !important;
        color: #ffffff !important;
        box-shadow: 0 0 12px rgba(255,255,255,0.08) !important;
    }
    button[kind="primary"] p, button[data-testid="baseButton-primary"] p {
        color: #ffffff !important;
        font-weight: 500 !important;
        font-size: 14px !important;
    }

    /* Botão Secundário */
    button[kind="secondary"], button[data-testid="baseButton-secondary"] {
        background-color: #0a0a0a !important;
        color: #888888 !important;
        border: 1px solid #222222 !important;
        border-radius: 8px !important;
        font-size: 13.5px !important;
        transition: all 0.2s ease !important;
    }
    button[kind="secondary"]:hover, button[data-testid="baseButton-secondary"]:hover {
        background-color: #111111 !important;
        border-color: #444444 !important;
        color: #ededed !important;
    }

    /* Selectbox dropdown */
    div[data-baseweb="select"] > div {
        background-color: #0a0a0a !important;
        border-color: #222222 !important;
        border-radius: 8px !important;
        color: #ededed !important;
    }

    /* Metricas limpas */
    div[data-testid="stMetric"] {
        background: #080808 !important;
        border: 1px solid #1a1a1a !important;
        border-radius: 10px !important;
        padding: 12px 16px !important;
    }
    div[data-testid="stMetricLabel"] {
        color: #888888 !important;
        font-size: 12px !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
    }
    div[data-testid="stMetricValue"] {
        color: #ffffff !important;
        font-weight: 700 !important;
    }

    /* Títulos e subtítulos */
    h1, h2, h3 {
        color: #ffffff !important;
        font-weight: 600 !important;
        letter-spacing: -0.03em !important;
    }
    .stCaption, p {
        color: #888888 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Gerador de E-mails Institucionais")
st.caption(
    "Regra: primeiro nome + . + iniciais dos nomes do meio + "
    "ultimo sobrenome @ dominio. Particulas (da, de, do, das, dos, e) nao geram inicial."
)

caminho_oficial = RAIZ / "data" / "cadastro_servidores_pe_65483.csv"
if not caminho_oficial.exists():
    st.error("Arquivo da base oficial não encontrado em data/cadastro_servidores_pe_65483.csv.")
    st.stop()

dados_bytes = caminho_oficial.read_bytes()

try:
    leitura = _ler(dados_bytes, None)
except Exception as e:
    st.error(f"Não foi possível carregar a base oficial: {e}")
    st.stop()

coluna_nome = leitura.coluna_nome or "Nome Completo"
coluna_cargo = leitura.coluna_cargo
coluna_matricula = leitura.coluna_matricula

if st.button("GERAR EMAILS (65.483 SERVIDORES)", type="primary", width="stretch"):
    st.session_state.pop("resultado", None)
    with st.spinner("Processando..."):
        res, removidos, segundos = _processar_com_progresso(
            leitura.df, coluna_nome, coluna_cargo, coluna_matricula, cfg
        )
    st.session_state.resultado = res
    st.session_state.removidos = removidos
    st.session_state.n_arquivo = len(leitura.df)
    st.session_state.segundos = segundos

if "resultado" not in st.session_state:
    st.stop()

res: pd.DataFrame = st.session_state.resultado
removidos: pd.DataFrame = st.session_state.get("removidos", res.iloc[0:0])
stats = resumir(res, st.session_state.get("n_arquivo"), removidos)

st.subheader("3. Resultado")
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Registros processados", f"{stats['registros_processados']:,}".replace(",", "."))
m2.metric("Nomes validos", f"{stats['validos']:,}".replace(",", "."))
m3.metric("Duplicados", f"{stats['duplicados']:,}".replace(",", "."))
m4.metric("Precisam de revisao", f"{stats['revisar']:,}".replace(",", "."))
if cfg.descartar_conflitos:
    m5.metric("Descartados p/ conflito", f"{stats['descartados_conflito']:,}".replace(",", "."))
else:
    m5.metric("Conflitos", f"{stats['conflitos']:,}".replace(",", "."))

st.caption(
    f"Nomes unicos: **{stats['nomes_unicos']:,}** · "
    f"E-mails gerados: **{stats['emails_gerados']:,}** · "
    f"E-mails unicos: **{stats['emails_unicos']:,}** · "
    f"Sem nome/invalidos: **{stats['invalidos']:,}** · "
    f"Tempo: **{st.session_state.get('segundos', 0):.2f}s**".replace(",", ".")
)

f1, f2 = st.columns([1, 1])
busca_nome = f1.text_input("Buscar por nome")
busca_email = f2.text_input("Buscar por e-mail")

col_revisao = "Revisão" if "Revisão" in res.columns else "Revisao"

# Ordenação idêntica ao site do Portal da Transparência (texto da Matrícula sem zeros extras)
if "Matrículas" in res.columns:
    def _norm_mat(m):
        if not isinstance(m, str) or not m.strip():
            return "999999999"
        p = m.split(",")[0].strip()
        return re.sub(r"/0*(\d+)", r"/\1", p)

    chaves = res["Matrículas"].apply(_norm_mat)
    res = res.iloc[chaves.argsort()].reset_index(drop=True)

filtrado = res
if busca_nome:
    filtrado = filtrado[filtrado["Nome Original"].str.contains(busca_nome, case=False, na=False)]
if busca_email:
    filtrado = filtrado[filtrado["Email Gerado"].str.contains(busca_email, case=False, na=False)]

p1, p2 = st.columns([1, 2.5])
tam_pagina = p1.selectbox("Linhas por bloco", [50, 100, 200, 500, 1000], index=0)
n_paginas = max(1, (len(filtrado) + tam_pagina - 1) // tam_pagina)

saltos_50 = [i * tam_pagina for i in range(1, min(n_paginas + 1, 2001))]

limite_escolhido = p2.selectbox(
    f"Linha limite (de {tam_pagina} em {tam_pagina})",
    options=saltos_50,
    format_func=lambda v: f"{v} (linhas {v - tam_pagina + 1} a {min(v, len(filtrado))})"
)
pagina = (limite_escolhido // tam_pagina)
ini = limite_escolhido - tam_pagina
fim = limite_escolhido

st.caption(
    f"Mostrando **{ini + 1} a {min(fim, len(filtrado)):,}** de **{len(filtrado):,} linhas** · Página {pagina} de {n_paginas}".replace(",", ".")
)

# Marca booleanamente se a linha é a 2ª, 3ª repetição em diante do mesmo e-mail (a 1ª fica False/normal)
res["Eh_Repeticao_Posterior"] = res.duplicated(subset=["Email Gerado"], keep="first") & (res["Email Gerado"] != "")

colunas_uteis = [c for c in [
    "Nome Original",
    "Cargo",
    "Email Gerado",
] if c in filtrado.columns]

pagina_df = filtrado.iloc[ini:fim]

# Tabela HTML interativa com cópia direta com 1 clique (sem bloqueio de canvas)
def _renderizar_tabela_clicavel(df_sub: pd.DataFrame):
    linhas_html = []
    for _, row in df_sub.iterrows():
        eh_repeticao = bool(row.get("Eh_Repeticao_Posterior", False))
        
        bg_tr = "background-color: rgba(245, 166, 35, 0.12); color: #f5a623;" if eh_repeticao else "color: #ededed;"
        badge_style = (
            "background: rgba(245, 166, 35, 0.15); border: 1px solid rgba(245, 166, 35, 0.5); color: #f5a623;"
            if eh_repeticao
            else "background: #0a0a0a; border: 1px solid #222222; color: #ffffff;"
        )
        
        tds = []
        for col in colunas_uteis:
            val = str(row.get(col, "") or "")
            if col == "Email Gerado" and val:
                aviso_dup = " (REPETIDO)" if eh_repeticao else ""
                tds.append(
                    f'<td style="padding: 12px 16px; border-bottom: 1px solid #141414;">'
                    f'<span class="email-btn-copy" onclick="copiarEmail(this, \'{val}\')" title="Clique para copiar{aviso_dup}" style="cursor: pointer; {badge_style} padding: 6px 12px; border-radius: 6px; display: inline-flex; align-items: center; gap: 8px; font-family: \'Geist Mono\', monospace; font-size: 13px; transition: all 0.15s ease;">'
                    f'<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="opacity: 0.7;"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>'
                    f'{val}</span></td>'
                )
            elif col == "Nome Original":
                tds.append(f'<td style="padding: 12px 16px; border-bottom: 1px solid #141414; font-size: 13.5px; font-weight: 500; letter-spacing: -0.01em;">{val}</td>')
            else:
                tds.append(f'<td style="padding: 12px 16px; border-bottom: 1px solid #141414; font-size: 13px; color: #777777;">{val}</td>')
        linhas_html.append(f'<tr style="{bg_tr}" class="table-row-hover">{"".join(tds)}</tr>')
        
    ths = "".join(f'<th style="padding: 12px 16px; background: #050505; color: #666666; text-align: left; font-size: 11px; text-transform: uppercase; font-weight: 600; letter-spacing: 0.06em; border-bottom: 1px solid #1f1f1f;">{c}</th>' for c in colunas_uteis)
    
    html_code = (
        '<style>'
        '@import url("https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&display=swap");'
        '.table-row-hover:hover { background-color: #080808 !important; }'
        '.email-btn-copy:hover { border-color: #ffffff !important; background-color: #141414 !important; }'
        '</style>'
        '<div id="tabela-container" style="overflow-x: auto; max-height: 560px; border: 1px solid #1f1f1f; border-radius: 10px; background: #000000; font-family: \'Geist\', -apple-system, sans-serif;">'
        '<table style="width: 100%; border-collapse: collapse; white-space: nowrap;">'
        '<thead style="position: sticky; top: 0; z-index: 2;">'
        f'<tr>{ths}</tr>'
        '</thead>'
        f'<tbody>{"".join(linhas_html)}</tbody>'
        '</table>'
        '</div>'
        '<div id="toast-aviso" style="display:none; position: fixed; bottom: 24px; right: 24px; background: #ffffff; color: #000000; padding: 10px 18px; border-radius: 8px; font-weight: 600; font-size: 13px; box-shadow: 0 8px 30px rgba(0,0,0,0.8); z-index: 99999; font-family: \'Geist\', sans-serif;"></div>'
        """<script>
        function copiarEmail(elem, email) {
            function sucesso() {
                var toast = document.getElementById("toast-aviso");
                toast.innerHTML = "✓ Copiado: " + email;
                toast.style.display = "block";
                elem.style.background = "#1f1f1f";
                elem.style.borderColor = "#ffffff";
                setTimeout(function() {
                    toast.style.display = "none";
                    elem.style.background = "#0a0a0a";
                    elem.style.borderColor = "#222222";
                }, 1800);
            }
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(email).then(sucesso).catch(function() {
                    copiarFallback(email, sucesso);
                });
            } else {
                copiarFallback(email, sucesso);
            }
        }
        function copiarFallback(email, callback) {
            var temp = document.createElement("input");
            temp.value = email;
            document.body.appendChild(temp);
            temp.select();
            try {
                document.execCommand("copy");
                callback();
            } catch(e) {}
            document.body.removeChild(temp);
        }
        </script>"""
    )
    st.components.v1.html(html_code, height=580, scrolling=True)

_renderizar_tabela_clicavel(pagina_df)