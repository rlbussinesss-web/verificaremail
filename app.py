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

# Carrega e processa automaticamente com cache em memória (sem precisar clicar no botão)
@st.cache_data(show_spinner=False)
def _obter_resultado_padrao():
    df_raw = pd.read_csv(caminho_oficial, sep=";", dtype=str, keep_default_na=False)
    res_df, _ = processar(df_raw, "Nome Completo", config=cfg, coluna_cargo="Cargo", coluna_matricula="Matrícula")
    
    # Ordenação idêntica ao site da Transparência (Matrícula)
    if "Matrículas" in res_df.columns:
        def _norm_mat(m):
            if not isinstance(m, str) or not m.strip():
                return "999999999"
            p = m.split(",")[0].strip()
            return re.sub(r"/0*(\d+)", r"/\1", p)
        chaves = res_df["Matrículas"].apply(_norm_mat)
        res_df = res_df.iloc[chaves.argsort()].reset_index(drop=True)

    # Marca repetições da 2ª em diante
    res_df["Eh_Repeticao_Posterior"] = res_df.duplicated(subset=["Email Gerado"], keep="first") & (res_df["Email Gerado"] != "")
    return res_df

res = _obter_resultado_padrao()

# Sistema de Armazenamento Persistente de E-mails Salvos
ARQUIVO_SALVOS = RAIZ / "data" / "emails_salvos.json"

def _carregar_emails_salvos() -> list[dict]:
    if ARQUIVO_SALVOS.exists():
        try:
            import json
            return json.loads(ARQUIVO_SALVOS.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def _gravar_emails_salvos(lista: list[dict]) -> None:
    import json
    ARQUIVO_SALVOS.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO_SALVOS.write_text(json.dumps(lista, ensure_ascii=False, indent=2), encoding="utf-8")

if "emails_salvos" not in st.session_state:
    st.session_state.emails_salvos = _carregar_emails_salvos()

tab_geral, tab_salvos = st.tabs(["Servidores & E-mails (65.483)", f"Meus E-mails Salvos ({len(st.session_state.emails_salvos)})"])

with tab_geral:
    # Barra de busca e filtro rápido de repetições
    b1, b2, b3 = st.columns([1.5, 1.5, 1])
    busca_nome = b1.text_input("Buscar por nome", placeholder="Digite o nome...")
    busca_email = b2.text_input("Buscar por e-mail", placeholder="Digite o e-mail...")
    ocultar_repetidos = b3.checkbox("Ocultar repetidos", value=False, help="Mostra apenas os primeiros e-mails únicos e válidos.")

    filtrado = res
    if busca_nome:
        filtrado = filtrado[filtrado["Nome Original"].str.contains(busca_nome, case=False, na=False)]
    if busca_email:
        filtrado = filtrado[filtrado["Email Gerado"].str.contains(busca_email, case=False, na=False)]
    if ocultar_repetidos:
        filtrado = filtrado[~filtrado["Eh_Repeticao_Posterior"]]

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

with tab_salvos:
    st.subheader("Gerenciador de Estoque & Vendas")
    st.caption("Controle os e-mails disponíveis para entrega e os que já foram vendidos.")

    def _extrair_valor_float(texto_preco: str) -> float:
        if not texto_preco:
            return 0.0
        # Remove "R$", espaços, e troca virgula por ponto
        limpo = re.sub(r"[^\d,\.]", "", str(texto_preco)).replace(".", "").replace(",", ".")
        try:
            return float(limpo)
        except Exception:
            return 0.0

    # Migra formato antigo se necessário
    for item in st.session_state.emails_salvos:
        if "status" not in item:
            item["status"] = "Disponível"
        if "preco" not in item:
            item["preco"] = "R$ 0,00"
        if "comprador" not in item:
            item["comprador"] = ""
        if "data_venda" not in item and item.get("status") == "Vendido":
            item["data_venda"] = item.get("data", "")

    total_estoque = len(st.session_state.emails_salvos)
    total_disponiveis = sum(1 for x in st.session_state.emails_salvos if x.get("status") == "Disponível")
    total_vendidos = sum(1 for x in st.session_state.emails_salvos if x.get("status") == "Vendido")

    # Cálculos Financeiros
    faturamento_total = sum(_extrair_valor_float(x.get("preco", "0")) for x in st.session_state.emails_salvos if x.get("status") == "Vendido")
    potencial_estoque = sum(_extrair_valor_float(x.get("preco", "0")) for x in st.session_state.emails_salvos if x.get("status") == "Disponível")
    ticket_medio = (faturamento_total / total_vendidos) if total_vendidos > 0 else 0.0

    # Linha 1: Painel Financeiro e Métricas
    m_f1, m_f2, m_f3, m_f4 = st.columns(4)
    m_f1.metric("💰 Faturamento Total", f"R$ {faturamento_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    m_f2.metric("📦 Potencial em Estoque", f"R$ {potencial_estoque:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    m_f3.metric("🎯 Vendas Realizadas", f"{total_vendidos} e-mails")
    m_f4.metric("📈 Ticket Médio", f"R$ {ticket_medio:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    # Gráfico de Vendas & Faturamento se houver vendas
    if total_vendidos > 0 or total_estoque > 0:
        with st.expander("📊 Gráficos de Desempenho Financeiro & Vendas", expanded=True):
            g_col1, g_col2 = st.columns([1.5, 1])
            
            with g_col1:
                st.caption("Faturamento Acumulado por E-mails Vendidos (R$)")
                vendidos_lista = [x for x in st.session_state.emails_salvos if x.get("status") == "Vendido"]
                if vendidos_lista:
                    dados_grafico = []
                    acumulado = 0.0
                    for i, v in enumerate(reversed(vendidos_lista), 1):
                        val = _extrair_valor_float(v.get("preco", "0"))
                        acumulado += val
                        label_item = v.get("data_venda") or f"Venda #{i}"
                        dados_grafico.append({"Venda": f"#{i}", "Faturamento (R$)": acumulado, "Valor": val})
                    df_chart = pd.DataFrame(dados_grafico)
                    st.line_chart(df_chart.set_index("Venda")[["Faturamento (R$)"]], color="#00ff88")
                else:
                    st.info("Nenhuma venda realizada ainda para gerar a curva de faturamento.")

            with g_col2:
                st.caption("Distribuição do Estoque (Disponíveis vs Vendidos)")
                df_dist = pd.DataFrame({
                    "Status": ["Disponíveis", "Vendidos"],
                    "Quantidade": [total_disponiveis, total_vendidos]
                })
                st.bar_chart(df_dist.set_index("Status"), color="#ededed")

    with st.container(border=True):
        st.markdown("**Cadastrar novo e-mail no estoque**")
        with st.form("form_novo_estoque", clear_on_submit=True):
            col_in1, col_in2, col_in3, col_in4 = st.columns([2.5, 1, 1.2, 0.9], vertical_alignment="bottom")
            novo_email = col_in1.text_input("E-mail", placeholder="exemplo.sobrenome@professor.educacao.pe.gov.br")
            novo_preco = col_in2.text_input("Preço", value="R$ 10,00")
            nova_nota = col_in3.text_input("Nota / Observação", placeholder="Ex: Conta ativada...")
            submetido = col_in4.form_submit_button("Adicionar", type="primary", use_container_width=True)
            
            if submetido:
                if novo_email.strip():
                    email_limpo = novo_email.strip().lower()
                    existe = any(x["email"] == email_limpo for x in st.session_state.emails_salvos)
                    if not existe:
                        from datetime import datetime
                        agora = datetime.now().strftime("%d/%m/%Y %H:%M")
                        st.session_state.emails_salvos.insert(0, {
                            "email": email_limpo,
                            "status": "Disponível",
                            "preco": novo_preco.strip(),
                            "nota": nova_nota.strip(),
                            "comprador": "",
                            "data": agora
                        })
                        _gravar_emails_salvos(st.session_state.emails_salvos)
                        st.success(f"E-mail {email_limpo} adicionado ao estoque!")
                        st.rerun()
                    else:
                        st.warning("Este e-mail já está no estoque.")
                else:
                    st.error("Digite um e-mail válido.")

    with st.expander("Importar múltiplos e-mails em lote para o estoque"):
        lote_txt = st.text_area("Cole os e-mails (um por linha):", height=100)
        c_lote1, c_lote2 = st.columns([1, 1], vertical_alignment="bottom")
        preco_lote = c_lote1.text_input("Preço padrão para este lote", value="R$ 10,00")
        if c_lote2.button("Cadastrar lote no estoque", use_container_width=True):
            linhas_lote = [l.strip().lower() for l in lote_txt.splitlines() if "@" in l]
            adicionados = 0
            from datetime import datetime
            agora = datetime.now().strftime("%d/%m/%Y %H:%M")
            emails_existentes = {x["email"] for x in st.session_state.emails_salvos}
            for em in linhas_lote:
                if em not in emails_existentes:
                    st.session_state.emails_salvos.insert(0, {
                        "email": em,
                        "status": "Disponível",
                        "preco": preco_lote.strip(),
                        "nota": "Lote",
                        "comprador": "",
                        "data": agora
                    })
                    emails_existentes.add(em)
                    adicionados += 1
            if adicionados > 0:
                _gravar_emails_salvos(st.session_state.emails_salvos)
                st.success(f"{adicionados} novos e-mails adicionados como Disponíveis!")
                st.rerun()

    if st.session_state.emails_salvos:
        f_st1, f_st2 = st.columns([1.5, 2])
        filtro_status_venda = f_st1.selectbox("Filtrar por Status", ["Todos", "Apenas Disponíveis", "Apenas Vendidos"])
        busca_estoque = f_st2.text_input("Filtrar estoque por texto", placeholder="Buscar e-mail ou nota...")

        itens_filtrados = st.session_state.emails_salvos
        if filtro_status_venda == "Apenas Disponíveis":
            itens_filtrados = [x for x in itens_filtrados if x.get("status") == "Disponível"]
        elif filtro_status_venda == "Apenas Vendidos":
            itens_filtrados = [x for x in itens_filtrados if x.get("status") == "Vendido"]

        if busca_estoque:
            b_low = busca_estoque.strip().lower()
            itens_filtrados = [x for x in itens_filtrados if b_low in x.get("email", "") or b_low in x.get("nota", "").lower()]

        st.write(f"Exibindo **{len(itens_filtrados)}** de **{total_estoque}** e-mails")

        # Área rápida para copiar todos os disponíveis filtrados de uma vez para mandar no WhatsApp/Telegram/Discord
        emails_disponiveis_txt = "\n".join([x["email"] for x in itens_filtrados if x.get("status") == "Disponível"])
        if emails_disponiveis_txt:
            with st.expander("📋 Copiar em Massa para Entrega (WhatsApp / Telegram)", expanded=False):
                st.caption("E-mails disponíveis prontos para copiar e colar diretamente no chat do cliente:")
                st.text_area(
                    "Selecione e copie tudo com Ctrl+A e Ctrl+C:",
                    value=emails_disponiveis_txt,
                    height=110,
                    help="Basta clicar dentro da caixa, apertar Ctrl+A e Ctrl+C para copiar tudo de uma vez."
                )

        # Cabeçalho da tabela de estoque
        col_h1, col_h2, col_h3, col_h4, col_h5 = st.columns([3.2, 0.9, 1.2, 1.4, 0.5], vertical_alignment="center")
        col_h1.caption("E-MAIL (CLIQUE PARA COPIAR)")
        col_h2.caption("PREÇO")
        col_h3.caption("STATUS")
        col_h4.caption("AÇÃO")
        col_h5.caption("")

        # Cada e-mail em sua linha com o botão de copiar no próprio texto e botão Marcar Vendido ao lado
        for idx, item in enumerate(itens_filtrados):
            col_e1, col_e2, col_e3, col_e4, col_e5 = st.columns([3.2, 0.9, 1.2, 1.4, 0.5], vertical_alignment="center")
            
            eh_disp = item.get("status") == "Disponível"
            icone_status = "🟢 DISPONÍVEL" if eh_disp else "🔴 VENDIDO"
            cor_status = "#00ff88" if eh_disp else "#ff4444"
            email_val = item["email"]
            preco_val = item.get("preco", "R$ 0,00")

            # Botão interativo que copia com 1 clique usando componente HTML inline minúsculo
            badge_html = f"""
            <div style="font-family: 'Geist Mono', monospace; font-size: 13px;">
                <span onclick="copiar('{email_val}')" title="Clique para copiar" style="cursor: pointer; background: {'#0a0a0a' if eh_disp else '#080808'}; border: 1px solid {'#222222' if eh_disp else '#1a1a1a'}; color: {'#ffffff' if eh_disp else '#666666; text-decoration: line-through'}; padding: 7px 12px; border-radius: 6px; display: inline-flex; align-items: center; gap: 8px; transition: all 0.15s ease;">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="opacity: 0.7;"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                    {email_val}
                </span>
                <span id="toast_{idx}" style="display:none; margin-left: 8px; font-size: 11px; color: #00ff88; font-weight: bold;">Copiado!</span>
            </div>
            <script>
            function copiar(texto) {{
                if (navigator.clipboard) {{
                    navigator.clipboard.writeText(texto);
                }} else {{
                    var t = document.createElement("input");
                    t.value = texto;
                    document.body.appendChild(t);
                    t.select();
                    document.execCommand("copy");
                    document.body.removeChild(t);
                }}
                var tEl = document.getElementById("toast_{idx}");
                tEl.style.display = "inline";
                setTimeout(function() {{ tEl.style.display = "none"; }}, 1500);
            }}
            </script>
            """
            with col_e1:
                st.components.v1.html(badge_html, height=44)

            col_e2.markdown(f"<div style='font-size: 13px; font-weight: 600; color: #ffffff;'>{preco_val}</div>", unsafe_allow_html=True)
            col_e3.markdown(f"<div style='font-size: 11px; font-weight: 700; color: {cor_status};'>{icone_status}</div>", unsafe_allow_html=True)

            # Botão de alternar status com 1 clique na mesma linha
            label_btn = "Marcar Vendido" if eh_disp else "Reativar"
            if col_e4.button(label_btn, key=f"btn_toggle_{item['email']}_{idx}", use_container_width=True):
                from datetime import datetime
                if eh_disp:
                    item["status"] = "Vendido"
                    item["data_venda"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                else:
                    item["status"] = "Disponível"
                    item.pop("data_venda", None)
                _gravar_emails_salvos(st.session_state.emails_salvos)
                st.rerun()

            # Excluir item
            if col_e5.button("🗑️", key=f"del_{item['email']}_{idx}", help="Excluir do estoque", use_container_width=True):
                st.session_state.emails_salvos = [x for x in st.session_state.emails_salvos if x["email"] != item["email"]]
                _gravar_emails_salvos(st.session_state.emails_salvos)
                st.rerun()

        st.divider()
        c_down1, c_down2 = st.columns([1, 1])
        df_exp = pd.DataFrame(st.session_state.emails_salvos)
        df_exp.columns = [c.capitalize() for c in df_exp.columns]
        c_down1.download_button(
            "Exportar Estoque Completo · CSV",
            data=para_csv_bytes(df_exp),
            file_name="estoque_emails_vendas.csv",
            mime="text/csv",
            use_container_width=True,
        )
        if c_down2.button("Limpar todo o estoque", type="secondary", use_container_width=True):
            st.session_state.emails_salvos = []
            _gravar_emails_salvos([])
            st.rerun()
    else:
        st.info("Nenhum e-mail no estoque. Adicione ou importe um lote acima!")