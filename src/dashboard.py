"""Dashboard (opcional) dos emplacamentos, em Streamlit.

Como rodar (a partir da raiz do projeto):
    streamlit run src/dashboard.py

Regra do curso: o dashboard lê SÓ as VIEWs da gold (via queries.py), sem
nenhum cálculo de indicador na tela. Aqui os dados só são colocados em
tabela (pandas), formatados/renomeados para exibição e desenhados.
Se o banco ou as VIEWs não existirem (ex.: no Streamlit Community Cloud,
onde data/ não vai para o git), o dashboard roda o pipeline uma vez,
reaproveitando os main() de ingestao.py e transformacao.py.
"""

import contextlib
import io
import json
import os
import threading

import altair as alt
import pandas as pd
import streamlit as st

import ingestao
import queries
import transformacao
from database import CAMINHO_BANCO, PASTA_DATA, PASTA_SQL, conectar
from main import formatar, views_faltando
from visitas import registrar_visita

# Nomes das categorias para exibição (só troca o texto, não mexe nos números).
ROTULOS = {
    "automoveis": "Automóveis",
    "comerciais_leves": "Comerciais leves",
    "caminhoes": "Caminhões",
    "onibus": "Ônibus",
    "total": "Total",
}
# Ordem fixa das 4 categorias do mix: mesma ordem na legenda (de cima para
# baixo) e na pilha (de baixo para cima); cada uma mantém sempre a mesma cor.
ORDEM_MIX = ["Automóveis", "Comerciais leves", "Caminhões", "Ônibus"]
POSICAO_MIX = {nome: posicao for posicao, nome in enumerate(ORDEM_MIX)}

# Rótulos dos eixos no padrão brasileiro, avaliados pelo próprio Vega na hora
# de desenhar (o formatLocale via usermeta não é aplicado pelo Streamlit).
# format() gera '3,000,000' / '-0.5'; replace() troca os separadores.
EIXO_INTEIRO = "replace(format(datum.value, ',.0f'), regexp(',', 'g'), '.')"  # 3.000.000
EIXO_UMA_CASA = "replace(format(datum.value, '.1f'), '.', ',')"  # -0,5
EIXO_MESES = "['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez'][datum.value - 1]"

# Aba "Arquitetura e views": a pergunta de negócio de cada VIEW (do CLAUDE.md).
VIEWS = [
    ("vw_tendencia", "Tendência: emplacamentos mensais por categoria e acumulado de 12 meses."),
    ("vw_mix", "Mix: participação de cada categoria no total, ao longo do tempo."),
    ("vw_sazonalidade", "Sazonalidade: meses acima/abaixo da média do respectivo ano."),
    (
        "vw_juros_emplacamentos",
        "Juros × emplacamentos: relação entre a Selic e os emplacamentos, com defasagem em meses.",
    ),
]

TABELAS = pd.DataFrame(
    [
        ("bronze", "bronze_emplacamentos",
         "Um valor de uma série de emplacamentos (7384 a 7389) em um mês, exatamente como a API "
         "devolveu (data e valor em texto), mais o código da série e a data/hora da carga."),
        ("bronze", "bronze_selic",
         "A Selic acumulada de um mês (série 4390, % ao mês), exatamente como a API devolveu, "
         "mais o código da série e a data/hora da carga."),
        ("silver", "silver_emplacamentos",
         "Veículos emplacados em um mês ('AAAA-MM-01'), em uma categoria (automóveis, comerciais "
         "leves, caminhões, ônibus ou total), com a quantidade como número inteiro."),
        ("silver", "silver_selic",
         "A Selic de um mês fechado ('AAAA-MM-01'), em % ao mês (como vem) e anualizada (% ao ano)."),
    ],
    columns=["Camada", "Tabela", "O que é uma linha"],
)

DIAGRAMA = """
digraph pipeline {
    rankdir=LR;
    bgcolor="transparent";
    node [shape=box, style="rounded,filled", fillcolor="#f0f2f6", color="#808495",
          fontcolor="#31333f", fontname="sans-serif", fontsize=11];
    edge [color="#808495"];

    api [label="API do Banco Central\\n(SGS)"];

    subgraph cluster_bronze {
        label="bronze"; fontcolor="#808495"; color="#808495"; style="dashed";
        bronze_emplacamentos; bronze_selic;
    }
    subgraph cluster_silver {
        label="silver"; fontcolor="#808495"; color="#808495"; style="dashed";
        silver_emplacamentos; silver_selic;
    }
    subgraph cluster_gold {
        label="gold (VIEWs)"; fontcolor="#808495"; color="#808495"; style="dashed";
        vw_tendencia; vw_mix; vw_sazonalidade; vw_juros_emplacamentos;
    }

    consultas [label="queries.py\\n(só lê as VIEWs)"];
    painel [label="Painel no terminal\\n(src/main.py)"];
    dashboard [label="Dashboard\\n(src/dashboard.py)"];

    api -> bronze_emplacamentos;
    api -> bronze_selic;
    bronze_emplacamentos -> silver_emplacamentos;
    bronze_selic -> silver_selic;
    silver_emplacamentos -> vw_tendencia;
    silver_emplacamentos -> vw_mix;
    silver_emplacamentos -> vw_sazonalidade;
    silver_emplacamentos -> vw_juros_emplacamentos;
    silver_selic -> vw_juros_emplacamentos;
    vw_tendencia -> consultas;
    vw_mix -> consultas;
    vw_sazonalidade -> consultas;
    vw_juros_emplacamentos -> consultas;
    consultas -> painel;
    consultas -> dashboard;
}
"""


def tabela(linhas, colunas_texto=()):
    """Linhas do sqlite3 -> DataFrame, sem alterar nenhum valor.

    Para cada coluna em colunas_texto, acrescenta '<coluna>_txt' com o valor
    formatado por formatar() (3.039.871 / 13,34 / '-'), usado nos tooltips.
    A formatação usa o valor original do SQLite (int/float do Python), antes
    de virar tipo do pandas.
    """
    registros = []
    for linha in linhas:
        registro = dict(linha)
        for coluna in colunas_texto:
            registro[f"{coluna}_txt"] = formatar(registro[coluna], coluna)
        registros.append(registro)
    return pd.DataFrame(registros)


@st.cache_resource
def trava_do_contador():
    """Uma trava compartilhada por todas as sessões, para duas aberturas ao
    mesmo tempo não lerem e gravarem o arquivo do contador juntas."""
    return threading.Lock()


def caminho_visualizacoes():
    # Fora do banco do projeto, de propósito: data/ não vai para o git.
    return os.path.join(PASTA_DATA, "visualizacoes.json")


def ler_visualizacoes():
    """Total gravado no arquivo; 0 se ele não existe; None se estiver ilegível."""
    caminho = caminho_visualizacoes()
    if not os.path.exists(caminho):
        return 0
    try:
        with open(caminho, encoding="utf-8") as arquivo:
            return int(json.load(arquivo)["visualizacoes"])
    except (ValueError, KeyError, TypeError, OSError):
        return None


def registrar_visualizacao():
    """Contador LOCAL: soma 1 ao total do arquivo e devolve o novo total.
    Se o arquivo estiver ilegível, não grava nada (para não zerar um total
    que existia) e devolve None."""
    with trava_do_contador():
        total = ler_visualizacoes()
        if total is None:
            return None
        os.makedirs(PASTA_DATA, exist_ok=True)
        caminho = caminho_visualizacoes()
        temporario = caminho + ".tmp"
        with open(temporario, "w", encoding="utf-8") as arquivo:
            json.dump({"visualizacoes": total + 1}, arquivo)
        os.replace(temporario, caminho)  # troca de uma vez: o arquivo nunca fica pela metade
        return total + 1


def segredos_supabase():
    """(url, chave) dos secrets do Streamlit, ou None se não estiverem configurados."""
    try:
        return st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
    except Exception:  # sem secrets.toml, ou sem as duas chaves
        return None


def contar_acesso():
    """Registra um acesso e devolve o total (ou None). Nunca levanta exceção.

    Com secrets (nuvem): contador no Supabase, que sobrevive aos reinícios.
    Sem secrets (local): contador em data/visualizacoes.json.
    """
    try:
        segredos = segredos_supabase()
        if segredos is not None:
            return registrar_visita(*segredos)
        return registrar_visualizacao()
    except Exception:
        return None


class FalhaNoPipeline(Exception):
    """O pipeline não conseguiu montar o banco; a mensagem traz o que ele imprimiu."""


@st.cache_resource(show_spinner=False)
def montar_pipeline():
    """Roda o pipeline completo (API -> bronze -> silver -> gold) uma vez por servidor.

    Usado quando o banco não existe, como no Streamlit Community Cloud (data/ não vai
    para o git). Reaproveita os main() dos scripts, que imprimem o progresso e, em
    caso de erro, imprimem a mensagem e chamam sys.exit(1): a saída é capturada para
    ser mostrada na tela. Em caso de falha a função levanta exceção, e o
    st.cache_resource não guarda exceções: a próxima abertura tenta de novo.
    """
    saida = io.StringIO()
    try:
        with contextlib.redirect_stdout(saida):
            ingestao.main()
            transformacao.main()
    except SystemExit as erro:
        if erro.code not in (None, 0):
            raise FalhaNoPipeline(saida.getvalue()) from None
    except Exception as erro:
        raise FalhaNoPipeline(f"{saida.getvalue()}\n{type(erro).__name__}: {erro}") from erro
    return saida.getvalue()


def faltam_dados():
    """True se o banco não existe ou se falta alguma VIEW da gold."""
    if not os.path.exists(CAMINHO_BANCO):
        return True
    conexao = conectar()
    try:
        return bool(views_faltando(conexao))
    finally:
        conexao.close()


def arquivo_sql_da_view(view):
    """Caminho do .sql em sql/gold/ que cria a VIEW (ex.: 01_vw_tendencia.sql)."""
    pasta_gold = os.path.join(PASTA_SQL, "gold")
    for nome in sorted(os.listdir(pasta_gold)):
        if nome.endswith(".sql") and nome[3:-4] == view:  # 'NN_<view>.sql'
            return os.path.join(pasta_gold, nome)
    return None


st.set_page_config(page_title="Emplacamentos Brasil", page_icon=":material/directions_car:", layout="wide")
st.title("EMPLACAMENTOS NO BRASIL: PAINEL DE MERCADO")

# --- Contador: um acesso por sessão --------------------------------------------
# O session_state vive enquanto a aba do navegador estiver aberta; cliques e
# trocas de categoria rodam o script de novo, mas não contam outra vez.
# O total devolvido na abertura fica guardado e é o que aparece na tela.
if "total_acessos" not in st.session_state:
    st.session_state["total_acessos"] = contar_acesso()

# --- Sem banco ou sem VIEWs: monta o pipeline uma vez (ex.: Community Cloud) ---
if faltam_dados():
    with st.spinner("Buscando os dados no Banco Central (primeira execução)..."):
        try:
            montar_pipeline()
        except FalhaNoPipeline as erro:
            st.error(
                f"Não foi possível montar o banco de dados.\n\n```\n{erro}\n```",
                title="Falha ao buscar os dados",
            )
            st.stop()

conexao = conectar()
try:
    faltando = views_faltando(conexao)
    if faltando:
        # O pipeline já rodou neste servidor (cache), mas as VIEWs sumiram depois.
        st.error(
            f"Faltam as VIEWs da gold: {', '.join(faltando)}. Reinicie o app ou rode, "
            "a partir da raiz do projeto: `python src/main.py`",
            title="Indicadores não encontrados",
        )
        st.stop()

    carregado_em = queries.ultima_carga(conexao)  # exceção: metadado da bronze
    ultimo = queries.ultimo_mes_total(conexao)
    categorias = queries.categorias_validas(conexao)
    mix = tabela(queries.mix_anual(conexao), ["participacao_pct", "quantidade_ano"])
    sazonalidade = tabela(queries.sazonalidade_total(conexao), ["indice_medio"])
    juros = tabela(queries.juros_emplacamentos(conexao), ["correlacao"])
    colunas_views = {view: queries.colunas_da_view(conexao, view) for view, _ in VIEWS}
finally:
    conexao.close()

mes_ultimo = ultimo["mes"]  # 'AAAA-MM-01'
mes_ultimo_br = f"{mes_ultimo[5:7]}/{mes_ultimo[:4]}"  # só reordena o texto: MM/AAAA

# carregado_em 'AAAA-MM-DD HH:MM:SS' -> 'DD/MM/AAAA HH:MM'. Só reordena o texto;
# já está no horário local do computador (Brasília), então não há conversão de fuso.
if carregado_em:
    atualizacao_br = f"{carregado_em[8:10]}/{carregado_em[5:7]}/{carregado_em[:4]} {carregado_em[11:16]}"
else:
    atualizacao_br = "-"
total_acessos = st.session_state["total_acessos"]
acessos_br = "–" if total_acessos is None else formatar(total_acessos, "acessos")

st.caption(
    f"Dados: Banco Central (Fenabrave) · última atualização {atualizacao_br} (Brasília) · "
    f":material/visibility: {acessos_br} acessos"
)
st.caption(f"Último mês disponível: {mes_ultimo_br}.")

# Navegação entre as duas seções (segmented_control: parece clicável e só
# a seção escolhida é desenhada).
INDICADORES = ":material/insights: Indicadores"
ARQUITETURA = ":material/account_tree: Arquitetura"
secao = st.segmented_control(
    "Seção",
    [INDICADORES, ARQUITETURA],
    default=INDICADORES,
    required=True,
    label_visibility="collapsed",
    key="secao",
)

# =============================================================================
# Aba 1: Indicadores
# =============================================================================
if secao == INDICADORES:
    # --- Topo: 3 números do total no último mês (vw_tendencia) ---------------
    with st.container(horizontal=True):
        st.metric(f"Emplacamentos em {mes_ultimo_br}", formatar(ultimo["quantidade"], "quantidade"), border=True)
        st.metric("Acumulado 12 meses", formatar(ultimo["acumulado_12m"], "acumulado_12m"), border=True)
        st.metric(
            "Variação do acumulado 12 meses",
            formatar(ultimo["variacao_12m_pct"], "variacao_12m_pct") + "%",
            help="Acumulado dos últimos 12 meses contra o acumulado de 12 meses antes.",
            border=True,
        )

    # --- Gráfico 1: tendência --------------------------------------------------
    with st.container(border=True):
        st.subheader("Tendência: acumulado de 12 meses")
        categoria = st.segmented_control(
            "Categoria",
            categorias,
            default="total",
            required=True,
            format_func=lambda c: ROTULOS.get(c, c),
            key="categoria_tendencia",
        )
        conexao = conectar()
        try:
            tendencia = tabela(
                queries.serie_acumulado_12m(conexao, categoria),
                ["acumulado_12m", "variacao_12m_pct"],
            )
        finally:
            conexao.close()

        grafico_tendencia = (
            alt.Chart(tendencia)
            .mark_line(strokeWidth=2)
            .encode(
                x=alt.X("mes:T", title=None),
                y=alt.Y(
                    "acumulado_12m:Q",
                    title="Veículos (acumulado 12 meses)",
                    axis=alt.Axis(labelExpr=EIXO_INTEIRO),
                ),
                tooltip=[
                    alt.Tooltip("mes:T", title="Mês", format="%m/%Y"),
                    alt.Tooltip("acumulado_12m_txt:N", title="Acumulado 12 meses"),
                    alt.Tooltip("variacao_12m_pct_txt:N", title="Variação 12 meses (%)"),
                ],
            )
            .properties(height=320)
        )
        st.altair_chart(
            grafico_tendencia,
            alt=f"Acumulado de 12 meses de emplacamentos ({ROTULOS.get(categoria, categoria)}) desde 1991",
        )

    # --- Gráfico 2: mix --------------------------------------------------------
    with st.container(border=True):
        st.subheader("Mix: participação de cada categoria no total do ano")
        mix["categoria"] = mix["categoria"].map(ROTULOS)  # só o nome exibido
        mix["posicao"] = mix["categoria"].map(POSICAO_MIX)  # posição na pilha (0 = embaixo)
        grafico_mix = (
            alt.Chart(mix)
            .mark_bar()
            .encode(
                x=alt.X("ano:O", title=None),
                y=alt.Y(
                    "participacao_pct:Q",
                    title="Participação (%)",
                    scale=alt.Scale(domain=[0, 100]),
                    axis=alt.Axis(labelExpr=EIXO_INTEIRO),
                ),
                color=alt.Color("categoria:N", title="Categoria", sort=ORDEM_MIX, scale=alt.Scale(domain=ORDEM_MIX)),
                order=alt.Order("posicao:Q", sort="ascending"),
                tooltip=[
                    alt.Tooltip("ano:O", title="Ano"),
                    alt.Tooltip("categoria:N", title="Categoria"),
                    alt.Tooltip("participacao_pct_txt:N", title="Participação (%)"),
                    alt.Tooltip("quantidade_ano_txt:N", title="Veículos no ano"),
                    alt.Tooltip("meses_no_ano:Q", title="Meses no ano"),
                ],
            )
            .properties(height=360)
        )
        st.altair_chart(grafico_mix, alt="Participação anual de automóveis, comerciais leves, caminhões e ônibus no total")
        st.caption("1990 começa em fevereiro e o último ano está incompleto (veja 'Meses no ano' ao passar o mouse).")

    col_sazonalidade, col_juros = st.columns(2)

    # --- Gráfico 3: sazonalidade -----------------------------------------------
    with col_sazonalidade:
        with st.container(border=True, height="stretch"):
            st.subheader("Sazonalidade do total")
            barras = (
                alt.Chart(sazonalidade)
                .mark_bar()
                .encode(
                    x=alt.X("mes_do_ano:O", title=None, axis=alt.Axis(labelExpr=EIXO_MESES, labelAngle=0)),
                    y=alt.Y(
                        "indice_medio:Q",
                        title="Índice médio (100 = média do ano)",
                        axis=alt.Axis(labelExpr=EIXO_INTEIRO),
                    ),
                    tooltip=[
                        alt.Tooltip("mes_do_ano:O", title="Mês do ano"),
                        alt.Tooltip("indice_medio_txt:N", title="Índice médio"),
                        alt.Tooltip("anos_usados:Q", title="Anos usados"),
                    ],
                )
            )
            referencia = alt.Chart().mark_rule(strokeDash=[4, 4], strokeWidth=2).encode(y=alt.datum(100))
            st.altair_chart(
                alt.layer(barras, referencia).properties(height=320),
                alt="Índice médio de emplacamentos por mês do ano: fevereiro mais fraco, dezembro mais forte",
            )
            st.caption("Acima da linha de 100: mês acima da média do próprio ano. Só anos completos (12 meses).")

    # --- Gráfico 4: juros x emplacamentos --------------------------------------
    with col_juros:
        with st.container(border=True, height="stretch"):
            st.subheader("Juros x emplacamentos")
            grafico_juros = (
                alt.Chart(juros)
                .mark_bar()
                .encode(
                    x=alt.X("defasagem_meses:O", title="Defasagem (meses)", axis=alt.Axis(labelAngle=0)),
                    y=alt.Y(
                        "correlacao:Q",
                        title="Correlação",
                        scale=alt.Scale(domain=[-1, 1]),
                        axis=alt.Axis(labelExpr=EIXO_UMA_CASA),
                    ),
                    tooltip=[
                        alt.Tooltip("defasagem_meses:O", title="Defasagem (meses)"),
                        alt.Tooltip("correlacao_txt:N", title="Correlação"),
                        alt.Tooltip("meses_usados:Q", title="Meses usados"),
                    ],
                )
                .properties(height=320)
            )
            st.altair_chart(
                grafico_juros,
                alt="Correlação entre a Selic e os emplacamentos por defasagem de 0 a 12 meses, negativa em todas",
            )
            st.caption(
                "Correlação não é causalidade. Selic do mês X (% ao ano) contra os emplacamentos "
                "totais do mês X + defasagem, desde 2000-01."
            )

# =============================================================================
# Aba 2: Arquitetura
# =============================================================================
if secao == ARQUITETURA:
    with st.container(border=True):
        st.subheader("Fluxo dos dados")
        st.graphviz_chart(
            DIAGRAMA,
            alt="Fluxo: API do Banco Central, bronze (2 tabelas), silver (2 tabelas), "
                "gold (4 VIEWs), painel no terminal e dashboard",
        )

    st.subheader("VIEWs da gold")
    for view, pergunta in VIEWS:
        with st.container(border=True):
            st.markdown(f"**`{view}`**")
            st.markdown(f"Pergunta de negócio: {pergunta}")
            colunas = pd.DataFrame(
                [
                    {"Coluna": c["name"], "Tipo declarado": c["type"] or "calculada (sem tipo declarado)"}
                    for c in colunas_views[view]
                ]
            )
            st.table(colunas, alt=f"Colunas da {view}")
            caminho = arquivo_sql_da_view(view)
            if caminho is None:
                st.warning(f"Arquivo .sql da {view} não encontrado em sql/gold/.")
            else:
                nome_arquivo = os.path.relpath(caminho, os.path.dirname(PASTA_SQL)).replace(os.sep, "/")
                with st.expander(f"Ver o SQL de origem ({nome_arquivo})"):
                    with open(caminho, encoding="utf-8") as arquivo:
                        st.code(arquivo.read(), language="sql")
    st.caption(
        "Tipo declarado: as VIEWs do SQLite herdam o tipo das colunas copiadas das tabelas "
        "(e de um CAST, como em ano e mes_do_ano), mas não declaram tipo para colunas "
        "calculadas por outras expressões (somas, médias, divisões, funções de janela). "
        "Essas aparecem como \"calculada (sem tipo declarado)\"."
    )

    with st.container(border=True):
        st.subheader("Tabelas da bronze e da silver")
        st.table(TABELAS.set_index("Tabela"), alt="O que é uma linha de cada tabela da bronze e da silver")

# --- Rodapé (fora das abas) ----------------------------------------------------
st.divider()
st.caption(
    "Ranking por modelo: veja a seção 'Contexto de mercado' no README "
    "(fonte: imprensa / Fenabrave). Não é um indicador deste pipeline."
)
