import math
import os
import glob
import sqlite3
import pandas as pd
import streamlit as st
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE HELPERS
# ─────────────────────────────────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "simulador.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS campanhas (
            nome TEXT PRIMARY KEY,
            data_criacao TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS campanhas_skus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campanha_nome TEXT,
            cod_prod INTEGER,
            descricao TEXT,
            validade TEXT,
            estoque TEXT,
            ttv_tabela TEXT,
            ttc_tabela TEXT,
            ttv_acao TEXT,
            ttc_acao TEXT,
            fator_boni TEXT,
            UNIQUE(campanha_nome, cod_prod)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendedor TEXT,
            cliente TEXT,
            campanha_nome TEXT,
            cod_prod INTEGER,
            descricao TEXT,
            qtd_compra INTEGER,
            qtd_bonificada INTEGER,
            valor_total REAL,
            data_pedido TEXT
        )
    ''')
    
    # ── Migrações Seguras (Adicionando novas colunas) ──
    try: c.execute("ALTER TABLE pedidos ADD COLUMN ttc_bees TEXT")
    except: pass
    try: c.execute("ALTER TABLE pedidos ADD COLUMN prazo_pagamento TEXT")
    except: pass
    try: c.execute("ALTER TABLE pedidos ADD COLUMN desconto_unidade REAL")
    except: pass
    try: c.execute("ALTER TABLE pedidos ADD COLUMN status_faturamento TEXT DEFAULT 'Pendente'")
    except: pass

    # ── Tabela de Usuários ──
    c.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
    ''')
    # Inserir o Admin padrão se a tabela estiver vazia
    c.execute("SELECT COUNT(*) as qtd FROM usuarios")
    if c.fetchone()["qtd"] == 0:
        c.execute("INSERT INTO usuarios (username, password, role) VALUES ('admin', 'admin123', 'Gestor')")

    conn.commit()
    conn.close()

# Executa na inicialização
init_db()

def get_campanhas():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT nome FROM campanhas", conn)
    conn.close()
    return df["nome"].tolist()

def get_skus_campanha(nome_campanha):
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM campanhas_skus WHERE campanha_nome = ?", conn, params=(nome_campanha,))
    conn.close()
    return df

def salvar_produto_campanha(nome_camp, item):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO campanhas (nome, data_criacao) VALUES (?, ?)', 
              (nome_camp, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    c.execute('''
        REPLACE INTO campanhas_skus (
            campanha_nome, cod_prod, descricao, validade, estoque,
            ttv_tabela, ttc_tabela, ttv_acao, ttc_acao, fator_boni
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        nome_camp, item["CÓD PROD"], item["DESCRIÇÃO"],
        item["VALIDADE"], item["ESTOQUE"], item["TTV TABELA"],
        item["TTC TABELA"], item["TTV AÇÃO"], item["TTC AÇÃO"],
        item["FATOR BONIFICAÇÃO"]
    ))
    conn.commit()
    conn.close()

def salvar_pedido(vendedor, cliente, campanha, cod_prod, desc, qtd_compra, qtd_boni, valor_total, ttc_bees, prazo, desc_unid):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO pedidos (vendedor, cliente, campanha_nome, cod_prod, descricao, qtd_compra, qtd_bonificada, valor_total, data_pedido, ttc_bees, prazo_pagamento, desconto_unidade, status_faturamento)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pendente')
    ''', (vendedor, cliente, campanha, cod_prod, desc, qtd_compra, qtd_boni, valor_total, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ttc_bees, prazo, desc_unid))
    conn.commit()
    conn.close()

def atualizar_status_pedido(pedido_id, novo_status):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('UPDATE pedidos SET status_faturamento = ? WHERE id = ?', (novo_status, pedido_id))
    conn.commit()
    conn.close()

def get_pedidos():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM pedidos ORDER BY id DESC", conn)
    conn.close()
    return df

# ── Funções de Usuário ──
def validar_login(username, password):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT role FROM usuarios WHERE username = ? AND password = ?", (username, password))
    user = c.fetchone()
    conn.close()
    if user:
        return user["role"]
    return None

def get_usuarios():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT id, username, role FROM usuarios", conn)
    conn.close()
    return df

def add_usuario(username, password, role):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO usuarios (username, password, role) VALUES (?, ?, ?)", (username, password, role))
        conn.commit()
        ret = True
    except sqlite3.IntegrityError:
        ret = False # usuário já existe
    conn.close()
    return ret

def del_usuario(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM usuarios WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Simulador Comercial AMBEV – Shelf Curto",
    page_icon="🍺",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BASES_PATH = r"\\INTRANET\intranet\Operações\Distribuição\Gabriel\Estoque"
PORT = 8505

# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    [data-testid="collapsedControl"] { display: none; }
    section[data-testid="stSidebar"]  { display: none; }
    .stTabs [data-baseweb="tab-list"] { gap: 16px; }
    .stTabs [data-baseweb="tab"] { font-size: 16px; font-weight: 600; padding: 10px 20px; }
    .card-agressivo {
        background: linear-gradient(135deg, #ff6b35, #f7c59f);
        border-radius: 12px; padding: 20px; color: #1a1a1a;
    }
    .card-margem {
        background: linear-gradient(135deg, #2ec4b6, #cbf3f0);
        border-radius: 12px; padding: 20px; color: #1a1a1a;
    }
    .stMetric label { font-size: 13px !important; }
    h1 { color: #FFD700; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# CARGA DE DADOS (UPLOAD MANUAL)
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def _load_dpo(file_buffer) -> pd.DataFrame:
    xls   = pd.ExcelFile(file_buffer)
    raw   = pd.read_excel(xls, sheet_name=xls.sheet_names[0], header=None)

    header_row = next(
        (i for i, row in raw.iterrows()
         if any("digo" in str(v).strip().lower() for v in row.values)),
        5
    )

    df = pd.read_excel(xls, sheet_name=xls.sheet_names[0], header=header_row)
    df.columns = [str(c).strip() for c in df.columns]

    for c in list(df.columns):
        if "digo" in c.lower().replace("ó", "o"):
            df = df.rename(columns={c: "Código"})
            break

    df = df.dropna(subset=["Código"])
    df["Código"] = pd.to_numeric(df["Código"], errors="coerce")
    df = df.dropna(subset=["Código"])
    df["Código"] = df["Código"].astype(int)
    return df

@st.cache_data(show_spinner=False)
def _load_csv(file_buffer) -> pd.DataFrame:
    df = pd.read_csv(file_buffer, sep=";", encoding="latin1")
    df.columns = [str(c).strip() for c in df.columns]
    df["Fator"]  = pd.to_numeric(df["Fator"],  errors="coerce")
    df["Código"] = pd.to_numeric(df["Código"], errors="coerce")
    df = df.dropna(subset=["Código", "Fator"])
    df["Código"] = df["Código"].astype(int)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def format_df_dates(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        cl = str(col).lower()
        if ("validad" in cl or "data" in cl) and "qtd" not in cl and "quant" not in cl:
            dt = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
            if dt.notna().any():
                df[col] = dt.dt.strftime("%d/%m/%Y").fillna("-")
    return df

@st.cache_data(show_spinner=False)
def get_shelf_critico(df: pd.DataFrame, hoje: pd.Timestamp) -> pd.DataFrame:
    df_s = df.copy()
    v1 = pd.to_datetime(df_s.get("Validade"), errors="coerce", dayfirst=True)
    v2 = pd.to_datetime(df_s.get("Validade2"), errors="coerce", dayfirst=True)
    
    d1 = (v1 - hoje).dt.days.fillna(9999)
    d2 = (v2 - hoje).dt.days.fillna(9999)
    
    df_s["Dias até vencimento"] = pd.DataFrame({'d1': d1, 'd2': d2}).min(axis=1)
    df_s.loc[df_s["Dias até vencimento"] == 9999, "Dias até vencimento"] = pd.NA
    
    def risco(d):
        if pd.isna(d): return "⚪"
        return ("🔴" if d<=45 else
                "🟡" if d<=60 else
                "🟢" if d<=90 else "⚪")
    
    df_s["Farol"] = df_s["Dias até vencimento"].apply(risco)
    return df_s[df_s["Dias até vencimento"].notna() & (df_s["Dias até vencimento"] <= 90)].copy()


# ─────────────────────────────────────────────────────────────────────────────
# LAYOUT
# ─────────────────────────────────────────────────────────────────────────────
if "perfil_acesso" not in st.session_state:
    st.session_state["perfil_acesso"] = None

if st.session_state["perfil_acesso"] is None:
    st.title("🍺 Simulador Comercial AMBEV")
    st.markdown("Selecione seu perfil para acessar a ferramenta:")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.container(border=True):
            st.subheader("🔐 Login")
            user_login = st.text_input("Usuário")
            senha_login = st.text_input("Senha", type="password")
            if st.button("Entrar", use_container_width=True, type="primary"):
                if not user_login or not senha_login:
                    st.error("Preencha usuário e senha!")
                else:
                    perfil = validar_login(user_login, senha_login)
                    if perfil:
                        st.session_state["perfil_acesso"] = perfil
                        st.session_state["username_logado"] = user_login
                        st.rerun()
                    else:
                        st.error("Usuário ou senha incorretos!")
    st.stop()


# =============================================================================
# TELA DO VENDEDOR (MOBILE-FIRST)
# =============================================================================
if st.session_state["perfil_acesso"] == "Vendedor":
    st.markdown("<h2 style='text-align: center; color: #2ec4b6;'>📱 Vendas & Negociação</h2>", unsafe_allow_html=True)
    if st.button("⬅️ Sair (Trocar Perfil)", type="secondary"):
        st.session_state["perfil_acesso"] = None
        st.rerun()
        
    st.divider()
    
    with st.container(border=True):
        st.subheader("👤 Identificação")
        nome_vendedor = st.text_input("Seu Nome:", value=st.session_state.get("username_logado", ""), disabled=True)
        nome_cliente = st.text_input("Cliente/PDV:")
        
    campanhas_ativas = get_campanhas()
    if not campanhas_ativas:
        st.warning("Nenhuma campanha ativa no momento.")
        st.stop()
        
    campanha_sel = st.selectbox("🚀 Selecione a Campanha", [""] + campanhas_ativas)
    
    if campanha_sel:
        skus_df = get_skus_campanha(campanha_sel)
        if skus_df.empty:
            st.warning("Esta campanha não possui SKUs cadastrados.")
        else:
            sku_opcoes = dict(zip(skus_df["cod_prod"], skus_df["descricao"]))
            def fmt_sku_vend(cod):
                return f"{int(cod)} - {sku_opcoes[cod]}"
                
            produto_sel = st.selectbox("📦 Selecione o Produto", skus_df["cod_prod"].tolist(), format_func=fmt_sku_vend)
            
            row_prod = skus_df[skus_df["cod_prod"] == produto_sel].iloc[0]
            
            st.markdown(f"""
            <div class="card-agressivo" style="margin-top: 15px;">
                <h4 style="margin:0;">Regra da Bonificação:</h4>
                <h2 style="margin:5px 0; color: #1a1a1a;">{row_prod['fator_boni']}</h2>
                <p style="margin:0;"><b>Validade:</b> {row_prod['validade']}</p>
                <p style="margin:0;"><b>Estoque Disponível:</b> {row_prod['estoque']} cxs</p>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown(f"""
            <div style="margin-top: 15px; padding: 15px; background-color: #222; border-radius: 8px;">
                <p style="margin:0; font-size: 14px;">Preço Base (Tabela): <b>{row_prod['ttv_tabela']}</b></p>
                <p style="margin:0; font-size: 18px; color: #ff6b35;">Preço Prático Efetivo: <b>{row_prod['ttv_acao']}</b></p>
                <br>
                <p style="margin:0; font-size: 12px; color: #888;">TTC Tabela: {row_prod['ttc_tabela']} | TTC Ação: {row_prod['ttc_acao']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            st.divider()
            st.subheader("🛒 Simulador de Pedido")
            
            qtd_compra = st.number_input("Quantidade Comprada (Caixas)", min_value=1, value=10, step=1)
            
            import re
            match = re.search(r'Compre (\d+)', row_prod['fator_boni'])
            n_boni = int(match.group(1)) if match else 999999
            
            qtd_ganha = qtd_compra // n_boni
            
            try: valor_ttv_tabela = float(str(row_prod['ttv_tabela']).replace("R$ ", "").replace(".", "").replace(",", "."))
            except: valor_ttv_tabela = 0.0
            
            try: valor_ttv_acao = float(str(row_prod['ttv_acao']).replace("R$ ", "").replace(".", "").replace(",", "."))
            except: valor_ttv_acao = 0.0

            total_pagar = qtd_compra * valor_ttv_tabela
            desconto_unidade = valor_ttv_tabela - valor_ttv_acao
            
            c1, c2 = st.columns(2)
            c1.metric("🎁 Ele Ganha (Cxs)", f"+ {qtd_ganha}")
            c2.metric("💵 Total a Pagar", f"R$ {total_pagar:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            
            st.info(f"💡 Desconto Médio Unidade: **R$ {desconto_unidade:,.2f}**".replace(",", "X").replace(".", ",").replace("X", "."))

            # NOVOS CAMPOS EXIGIDOS
            st.divider()
            st.subheader("📝 Dados Finais")
            ttc_bees = st.text_input("TTC BEES atual")
            prazo_pagto = st.text_input("Prazo de Pagamento")

            if st.button("✅ Confirmar Pedido", use_container_width=True, type="primary"):
                if not nome_cliente.strip() or not ttc_bees.strip() or not prazo_pagto.strip():
                    st.error("Preencha o cliente, o TTC BEES e o Prazo para confirmar.")
                else:
                    salvar_pedido(nome_vendedor, nome_cliente, campanha_sel, int(produto_sel), row_prod['descricao'], qtd_compra, qtd_ganha, total_pagar, ttc_bees, prazo_pagto, desconto_unidade)
                    st.success("🎉 Pedido salvo com sucesso e enviado ao Gestor!")
                    st.balloons()
            
    st.stop()


# =============================================================================
# TELA DO GESTOR (O APP ANTIGO)
# =============================================================================
if st.button("⬅️ Sair (Trocar Perfil)", key="btn_sair_gestor"):
    st.session_state["perfil_acesso"] = None
    st.rerun()

st.title("Simulador Comercial - Gestão de Shelf (Gestor)")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📁  1. Ingestão de Dados",
    "🎯  2. Simulador de Preços & Combos",
    "📦  3. Raio-X de Estoque & Verbas",
    "🚨  4. Visibilidade de Shelf",
    "🚀  5. Gestão de Ações",
    "📊  6. Painel de Pedidos"
])


# ═════════════════════════════════════════════════════════════════════════════
# ABA 1 – INGESTÃO / SINCRONIZAÇÃO
# ═════════════════════════════════════════════════════════════════════════════
with tab1:
    st.header("⚙️ 1. Configurações & Bases")
    
    with st.expander("👤 Gestão de Usuários (Admin)", expanded=False):
        c1, c2, c3 = st.columns(3)
        novo_user = c1.text_input("Novo Usuário")
        nova_senha = c2.text_input("Senha", type="password", key="new_pass")
        novo_perfil = c3.selectbox("Perfil", ["Vendedor", "Gestor"])
        
        if st.button("➕ Adicionar Usuário"):
            if not novo_user or not nova_senha:
                st.error("Preencha todos os campos!")
            else:
                if add_usuario(novo_user, nova_senha, novo_perfil):
                    st.success("Usuário criado com sucesso!")
                    st.rerun()
                else:
                    st.error("Username já existe!")
        
        st.divider()
        st.markdown("**Usuários Cadastrados:**")
        df_users = get_usuarios()
        for idx, row in df_users.iterrows():
            uc1, uc2, uc3 = st.columns([3, 3, 1])
            uc1.write(f"**{row['username']}**")
            uc2.write(f"_{row['role']}_")
            if row['username'] != 'admin':
                if uc3.button("🗑️ Excluir", key=f"del_{row['id']}"):
                    del_usuario(row['id'])
                    st.rerun()

    st.divider()
    st.markdown("Faça o upload dos arquivos de base atualizados para alimentar o Simulador.")

    dpo_ok = "df_dpo" in st.session_state
    csv_ok = "df_csv" in st.session_state

    if dpo_ok and csv_ok:
        st.success(
            f"🚀 **Bases carregadas!**  \n"
            f"📋 DPO: `{st.session_state.get('dpo_origem','—')}` · "
            f"{len(st.session_state['df_dpo']):,} linhas  \n"
            f"🔢 Fatores: `{st.session_state.get('csv_origem','—')}` · "
            f"{len(st.session_state['df_csv']):,} SKUs  \n"
            f"Navegue pelas abas 2, 3 e 4 para simular."
        )

    sc1, sc2 = st.columns(2)
    with sc1:
        dpo_file = st.file_uploader("📂 Planilha de Estoque (DPO) - .xlsx", type=["xlsx", "xlsm"])
    with sc2:
        csv_file = st.file_uploader("📂 Fatores de Conversão - .csv", type=["csv"])
        
    if st.button("🚀 Processar Bases", use_container_width=True, type="primary"):
        erros = []
        if dpo_file:
            try:
                st.session_state["df_dpo"] = _load_dpo(dpo_file)
                st.session_state["dpo_origem"] = dpo_file.name
                dpo_ok = True
            except Exception as e:
                erros.append(f"Erro DPO: {e}")
        
        if csv_file:
            try:
                st.session_state["df_csv"] = _load_csv(csv_file)
                st.session_state["csv_origem"] = csv_file.name
                csv_ok = True
            except Exception as e:
                erros.append(f"Erro Fatores: {e}")
                
        if erros:
            for e in erros: st.error(e)
        elif dpo_file or csv_file:
            st.success("✅ Bases atualizadas na sessão!")
            st.rerun()

    st.divider()

    # ── Upload manual (fallback) ──────────────────────────────────────────────
    with st.expander("📤 Upload manual (fallback)", expanded=not (dpo_ok and csv_ok)):
        c1, c2 = st.columns(2, gap="large")
        with c1:
            st.subheader("📋 DPO (Validades)")
            uploaded_dpo = st.file_uploader("Carregar DPO", type=["xlsm","xlsx"], key="dpo_up")
        with c2:
            st.subheader("🔢 Fatores de Conversão")
            uploaded_csv = st.file_uploader("Carregar CSV", type=["csv"], key="csv_up")

        if uploaded_dpo:
            try:
                xls = pd.ExcelFile(uploaded_dpo)
                raw = pd.read_excel(xls, sheet_name=xls.sheet_names[0], header=None)
                hr  = next((i for i,r in raw.iterrows()
                            if any("digo" in str(v).lower() for v in r.values)), 5)
                df  = pd.read_excel(xls, sheet_name=xls.sheet_names[0], header=hr)
                df.columns = [str(c).strip() for c in df.columns]
                for c in list(df.columns):
                    if "digo" in c.lower().replace("ó","o"):
                        df = df.rename(columns={c:"Código"}); break
                df = df.dropna(subset=["Código"])
                df["Código"] = pd.to_numeric(df["Código"], errors="coerce")
                df = df.dropna(subset=["Código"])
                df["Código"] = df["Código"].astype(int)
                st.session_state["df_dpo"]    = df
                st.session_state["dpo_origem"] = uploaded_dpo.name
                dpo_ok = True
                st.success(f"✅ DPO carregado: {len(df):,} linhas")
            except Exception as e:
                st.error(f"❌ {e}")

        if uploaded_csv:
            try:
                df = pd.read_csv(uploaded_csv, sep=";", encoding="latin1")
                df.columns = [str(c).strip() for c in df.columns]
                df["Fator"]  = pd.to_numeric(df["Fator"],  errors="coerce")
                df["Código"] = pd.to_numeric(df["Código"], errors="coerce")
                df = df.dropna(subset=["Código","Fator"])
                df["Código"] = df["Código"].astype(int)
                st.session_state["df_csv"]    = df
                st.session_state["csv_origem"] = uploaded_csv.name
                csv_ok = True
                st.success(f"✅ Fatores carregados: {len(df):,} SKUs")
            except Exception as e:
                st.error(f"❌ {e}")

    # ── Preview das bases ─────────────────────────────────────────────────────
    if dpo_ok or csv_ok:
        st.divider()
        pc1, pc2 = st.columns(2, gap="large")
        with pc1:
            if dpo_ok:
                df_show = st.session_state["df_dpo"]
                st.caption(f"DPO · {len(df_show):,} linhas")
                st.dataframe(format_df_dates(df_show.head(5)), use_container_width=True, height=200)
        with pc2:
            if csv_ok:
                df_show = st.session_state["df_csv"]
                st.caption(f"Fatores · {len(df_show):,} SKUs")
                st.dataframe(df_show.head(5), use_container_width=True, height=200)


# ═════════════════════════════════════════════════════════════════════════════
# ABA 2 – SIMULADOR DE PREÇOS & COMBOS
# ═════════════════════════════════════════════════════════════════════════════
with tab2:
    st.header("Simulador de Combos e Preços Promocionais")

    if "df_csv" not in st.session_state:
        st.warning("⚠️ Bases não carregadas — verifique a Aba 1.")
        st.stop()

    df_csv = st.session_state["df_csv"]

    # Otimização: Dicionário O(1) para não rodar Pandas mask N vezes na tela
    sku_dict = dict(zip(df_csv["Código"], df_csv["Descrição"]))

    def fmt_sku(cod):
        desc = sku_dict.get(cod, "")
        return f"{int(cod)} – {desc}" if desc else str(int(cod))

    sku_list      = sorted(df_csv["Código"].dropna().unique())
    selected_code = st.selectbox("🔍 Selecione o Produto (SKU):", sku_list, format_func=fmt_sku)
    st.session_state["selected_code"] = selected_code

    row_prod  = df_csv[df_csv["Código"] == selected_code].iloc[0]
    fator     = float(row_prod["Fator"])
    desc_prod = row_prod["Descrição"]

    # Estoque crítico do DPO
    volume_sugerido = 0.0
    dpo_info        = ""
    if "df_dpo" in st.session_state:
        match = st.session_state["df_dpo"][st.session_state["df_dpo"]["Código"] == selected_code]
        if not match.empty:
            r2 = match.iloc[0]
            def _val(col): return pd.to_datetime(r2.get(col), errors="coerce")
            def _qtd(col): return int(pd.to_numeric(r2.get(col, 0), errors="coerce") or 0)
            
            v1 = _val("Validade")
            cx1 = _qtd("QTD.(Validade1)")
            if cx1 == 0:
                qtd_col = next((c for c in r2.index if "qtd" in str(c).lower() or "quant" in str(c).lower()), None)
                cx1 = _qtd(qtd_col) if qtd_col else 0
                
            v2 = _val("Validade2")
            cx2 = _qtd("QTD.(Validade2)")
            
            fmt = lambda d: d.strftime("%d/%m/%Y") if pd.notna(d) else "—"
            
            volume_sugerido = float(cx1)
            
            if cx1 > 0:
                str_v1 = f"Validade 1 = {cx1:,} cxs - {fmt(v1)}"
                str_v2 = f" / Validade 2 = {cx2:,} cxs - {fmt(v2)}" if cx2 > 0 else ""
                dpo_info = f"Estoque: {str_v1}{str_v2} (Sugerido como volume meta: {cx1:,} cxs)"

    st.markdown(f"**Produto:** `{desc_prod}` &nbsp;|&nbsp; **Código:** `{int(selected_code)}` &nbsp;|&nbsp; **Fator:** `{int(fator)} un/cx`")
    if dpo_info:
        st.info(f"📦 {dpo_info}")
    elif "df_dpo" in st.session_state:
        st.warning("SKU não encontrado no Estoque — Volume Meta definido manualmente.")

    st.divider()
    
    col_hdr, col_radio = st.columns([1, 1], vertical_alignment="bottom")
    with col_hdr:
        st.subheader("Parâmetros da Ação Comercial")
    with col_radio:
        tipo_boni = st.radio(
            "🎯 Estratégia de Bonificação:",
            ["BONI TTV AÇÃO (Rebaixa de Custo)", "BONI TTV TABELA (Rebate)"],
            horizontal=True,
            label_visibility="collapsed"
        )

    ca, cb, cc = st.columns(3, gap="medium")

    with ca:
        st.markdown("**Tabela Atual (Canal)**")
        ttv_canal = st.number_input("TTV Canal (R$/un)", value=3.32, step=0.01, format="%.2f")
        ttc_canal = st.number_input("TTC Canal (R$/un)", value=3.89, step=0.01, format="%.2f")
    with cb:
        st.markdown("**Tabela da Ação**")
        ttv_acao = st.number_input("TTV Ação (R$/un)", value=3.00, step=0.01, format="%.2f")
        ttc_acao = st.number_input("TTC Ação (R$/un)", value=3.49, step=0.01, format="%.2f")
    with cc:
        st.markdown("**Volume & Meta**")
        volume_meta = st.number_input(
            "Volume Meta (Caixas)",
            value=volume_sugerido if volume_sugerido > 0 else 1000.0,
            step=100.0, format="%.0f",
            help="Sugerido pelo estoque crítico do DPO."
        )

    markup_canal = ((ttc_canal / ttv_canal) - 1) * 100 if ttv_canal > 0 else 0
    markup_acao  = ((ttc_acao  / ttv_acao)  - 1) * 100 if ttv_acao  > 0 else 0
    desconto_un  = ttv_canal - ttv_acao
    
    if tipo_boni == "BONI TTV AÇÃO (Rebaixa de Custo)":
        n_exato = (ttv_acao / desconto_un) if desconto_un > 0 else 0
    else:
        n_exato = (ttv_canal / desconto_un) if desconto_un > 0 else 0

    n_agg_sug    = max(int(n_exato), 1)
    n_margem_sug = int(n_exato) + 1

    st.divider()
    st.subheader("⚙️ Ajuste Manual do Fator de Bonificação")
    st.markdown("O simulador calculou a sugestão matemática abaixo, mas você pode ajustar a proporção (Compre X, Ganha Y) para forçar um formato específico.")
    col_x, col_y = st.columns(2)
    override_compre = col_x.number_input("Compre (Caixas)", value=n_agg_sug, min_value=1)
    override_ganha = col_y.number_input("Ganha (Caixas)", value=1, min_value=1)

    n_agg = override_compre
    ganha_agg = override_ganha
    preco_agg = (n_agg * ttv_canal) / (n_agg + ganha_agg)

    n_margem = n_margem_sug
    ganha_marg = 1
    preco_margem = (n_margem * ttv_canal) / (n_margem + ganha_marg)

    ressarc_max  = volume_meta * desconto_un * fator

    st.divider()
    st.subheader("📊 Resultado das Simulações")
    mk_agg   = ((ttc_acao / preco_agg)   - 1) * 100 if preco_agg   > 0 else 0
    mk_marg  = ((ttc_acao / preco_margem) - 1) * 100 if preco_margem > 0 else 0

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Desconto Unitário",          f"R$ {desconto_un:.2f}")
    m2.metric("Markup Cliente (Agressivo)", f"{mk_agg:.1f}%")
    m3.metric("Markup Cliente (Margem)",    f"{mk_marg:.1f}%")
    m4.metric("Fator Boni (N)",             f"{n_exato:.3f}")
    m5.metric("Ressarcimento Máximo",       f"R$ {ressarc_max:,.2f}")

    st.divider()
    st.subheader("🎯 Opções de Combos – Orientação para RNs em Campo")
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown(f"""
        <div class="card-agressivo">
            <h3>🚀 Cenário Customizado/Agressivo</h3>
            <p style="font-size:22px;font-weight:700;">Compre {n_agg} &nbsp;·&nbsp; Ganhe {ganha_agg}</p>
            <p><b>Preço Prático:</b> <span style="font-size:20px;">R$ {preco_agg:.2f}</span></p><hr>
            <p>✅ Ideal para queimar estoque crítico.</p>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="card-margem">
            <h3>🛡️ Cenário Proteção de Margem</h3>
            <p style="font-size:22px;font-weight:700;">Compre {n_margem} &nbsp;·&nbsp; Ganhe {ganha_marg}</p>
            <p><b>Preço Prático:</b> <span style="font-size:20px;">R$ {preco_margem:.2f}</span></p><hr>
            <p>✅ Protege o resultado da revenda.</p>
        </div>""", unsafe_allow_html=True)

    if tipo_boni == "BONI TTV TABELA (Rebate)":
        st.warning("⚠️ **Estratégia de Rebate (Encontro de Contas):** Lembre o cliente que a caixa bonificada deve ser vendida ao consumidor no preço de tabela regular para que o reembolso dele feche financeiramente.")

    st.divider()
    st.subheader("📋 Tabela Comparativa")
    st.dataframe(pd.DataFrame({
        "Cenário":                ["Customizado/Agressivo", "Proteção de Margem"],
        "Combo":                  [f"Compre {n_agg}, Ganhe {ganha_agg}", f"Compre {n_margem}, Ganhe {ganha_marg}"],
        "Preço Prático (R$/un)":  [f"R$ {preco_agg:.2f}", f"R$ {preco_margem:.2f}"],
        "Base Canal (R$/un)":     [f"R$ {ttv_canal:.2f}", f"R$ {ttv_canal:.2f}"],
        "Desconto Efetivo":       [f"{(ttv_canal-preco_agg)/ttv_canal*100:.1f}%", f"{(ttv_canal-preco_margem)/ttv_canal*100:.1f}%"],
        "Markup Cliente":         [f"{mk_agg:.1f}%", f"{mk_marg:.1f}%"],
    }), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("💾 Cadastrar Produto em Ação")
    with st.container(border=True):
        col_c1, col_c2 = st.columns([2, 3])
        with col_c1:
            opcoes_camp = get_campanhas()
            if opcoes_camp:
                camp_sel = st.selectbox("Campanhas Existentes", ["Nova Campanha..."] + opcoes_camp)
                if camp_sel == "Nova Campanha...":
                    nome_campanha = st.text_input("Nome da Nova Campanha (Ex: AÇÕES SHELF - SET/2026)")
                else:
                    nome_campanha = camp_sel
            else:
                nome_campanha = st.text_input("Nome da Campanha (Ex: AÇÕES SHELF - SET/2026)")
                
        with col_c2:
            cenario_escolhido = st.radio("Cenário de Combo", ["Cenário Agressivo", "Cenário Margem"], horizontal=True)
            validade_escolhida = st.radio("Validades Alvo", ["Apenas Validade 1 (Mais crítica)", "Validades 1 e 2"], horizontal=True)
            
        if st.button("💾 Cadastrar na Ação", type="primary", use_container_width=True):
            if not nome_campanha.strip():
                st.error("Digite ou selecione um nome para a campanha!")
            else:
                nome = nome_campanha.strip()
                
                val_critica = "—"
                estoque_total = 0
                if "df_dpo" in st.session_state:
                    match_dpo = st.session_state["df_dpo"][st.session_state["df_dpo"]["Código"] == selected_code]
                    if not match_dpo.empty:
                        r = match_dpo.iloc[0]
                        v1 = pd.to_datetime(r.get("Validade"), errors="coerce", dayfirst=True)
                        v2 = pd.to_datetime(r.get("Validade2"), errors="coerce", dayfirst=True)
                        q1 = int(pd.to_numeric(r.get("QTD.(Validade1)", 0), errors="coerce") or 0)
                        q2 = int(pd.to_numeric(r.get("QTD.(Validade2)", 0), errors="coerce") or 0)
                        
                        fmt = lambda d: d.strftime("%d/%m/%Y") if pd.notna(d) else "—"
                        
                        if validade_escolhida == "Apenas Validade 1 (Mais crítica)":
                            if q1 == 0:
                                qc = next((c for c in r.index if "qtd" in str(c).lower() or "quant" in str(c).lower()), None)
                                q1 = int(pd.to_numeric(r.get(qc, 0), errors="coerce") or 0) if qc else 0
                            val_critica = fmt(v1)
                            estoque_total = q1
                        else:
                            val_critica = f"Val1: {fmt(v1)} | Val2: {fmt(v2)}"
                            estoque_total = q1 + q2
                
                fator_boni = f"[Compre {n_agg}, Ganhe {ganha_agg}]" if cenario_escolhido == "Cenário Agressivo" else f"[Compre {n_margem}, Ganhe {ganha_marg}]"
                
                novo_item = {
                    "CÓD PROD": int(selected_code),
                    "DESCRIÇÃO": desc_prod,
                    "VALIDADE": val_critica,
                    "ESTOQUE": f"{estoque_total:,}".replace(",", "."),
                    "TTV TABELA": f"R$ {ttv_canal:.2f}",
                    "TTC TABELA": f"R$ {ttc_canal:.2f}",
                    "TTV AÇÃO": f"R$ {ttv_acao:.2f}",
                    "TTC AÇÃO": f"R$ {ttc_acao:.2f}",
                    "FATOR BONIFICAÇÃO": fator_boni
                }
                
                salvar_produto_campanha(nome, novo_item)
                st.success(f"✅ Produto cadastrado/atualizado na campanha '{nome}' no SQLite!")


# ═════════════════════════════════════════════════════════════════════════════
# ABA 3 – RAIO-X DE ESTOQUE & VERBAS
# ═════════════════════════════════════════════════════════════════════════════
with tab3:
    st.header("Raio-X de Estoque Crítico & Verbas")

    if "df_dpo" not in st.session_state or "df_csv" not in st.session_state:
        st.warning("⚠️ Bases não carregadas — verifique a Aba 1.")
        st.stop()

    df_dpo = st.session_state["df_dpo"]
    df_csv = st.session_state["df_csv"]

    if "selected_code" in st.session_state:
        sc3     = st.session_state["selected_code"]
        r_csv3  = df_csv[df_csv["Código"] == sc3]
        desc_3  = r_csv3["Descrição"].values[0] if not r_csv3.empty else "—"
        fator_3 = float(r_csv3["Fator"].values[0]) if not r_csv3.empty else 1.0
        st.info(f"SKU selecionado na Aba 2: **{int(sc3)} – {desc_3}**")
    else:
        sc3     = st.selectbox("Selecione o SKU:", sorted(df_dpo["Código"].dropna().unique()))
        r_csv3  = df_csv[df_csv["Código"] == sc3]
        desc_3  = r_csv3["Descrição"].values[0] if not r_csv3.empty else "—"
        fator_3 = float(r_csv3["Fator"].values[0]) if not r_csv3.empty else 1.0

    st.divider()
    match_dpo = df_dpo[df_dpo["Código"] == sc3]

    if match_dpo.empty:
        st.warning("⚠️ SKU não encontrado no DPO.")
    else:
        r = match_dpo.iloc[0]

        def _val(col): return pd.to_datetime(r.get(col), errors="coerce")
        def _qtd(col): return int(pd.to_numeric(r.get(col, 0), errors="coerce") or 0)
        def _cxs(q):   return int(q)  # QTD já vem em caixas no DPO

        v1 = _val("Validade");  q1 = _qtd("QTD.(Validade1)"); cx1 = _cxs(q1)
        v2 = _val("Validade2"); q2 = _qtd("QTD.(Validade2)"); cx2 = _cxs(q2)
        fmt = lambda d: d.strftime("%d/%m/%Y") if pd.notna(d) else "—"

        st.subheader("🗓️ Painel de Validades Críticas")
        vv1, vv2, vv3 = st.columns(3, gap="medium")
        vv1.metric("📛 Validade 1 (MAIS CRÍTICA)", fmt(v1), f"{cx1:,} cx", delta_color="inverse")
        vv2.metric("📅 Validade 2 (Secundária)", fmt(v2) if fmt(v2)!="—" else "Não há", f"{cx2:,} cx" if cx2>0 else "—", delta_color="off")
        vv3.metric("📦 Total Estoque Crítico (Val 1)", f"{cx1:,} cx")

        st.divider()
        st.subheader("💰 Projeção de Ressarcimento & Verbas")
        fv      = float(df_csv[df_csv["Código"]==sc3]["Fator"].values[0]) if not df_csv[df_csv["Código"]==sc3].empty else 1.0
        d_un    = st.number_input("Desconto Unitário (R$/un):", value=0.32, step=0.01, format="%.2f", key="d_un3")
        vol_m   = st.number_input("Volume Meta (Caixas):",      value=float(cx1) if cx1>0 else 1000.0, step=100.0, format="%.0f", key="vm3")
        ressarc = vol_m * d_un * fv
        r1,r2,r3 = st.columns(3)
        r1.metric("Volume Meta",              f"{int(vol_m)} cx")
        r2.metric("Desconto × Fator (por cx)",f"R$ {d_un*fv:.2f}")
        r3.metric("💵 Ressarcimento Estimado",f"R$ {ressarc:,.2f}")

        if cx1 > 0:
            gap = cx1 - int(vol_m)
            if gap <= 0:
                st.success(f"✅ Meta cobre o estoque crítico de {cx1} cx.")
            else:
                st.warning(f"⚠️ Meta está {gap} cx abaixo do necessário ({cx1} cx).")

        st.divider()
        st.subheader("📄 Dados DPO para este SKU")
        cols_want = ["Código","Descrição","Validade","Validade2","DZ/PCT",
                     "QTD.(Validade1)","QTD.(Validade2)","Venda Média SKU",
                     "Dias Vencimento","Necessários P/ Vender Estoque","Status"]
        cols_ok   = [c for c in cols_want if c in match_dpo.columns]
        st.dataframe(format_df_dates(match_dpo[cols_ok].reset_index(drop=True)),
                     use_container_width=True, height=(len(match_dpo)+1)*36+10)


# ═════════════════════════════════════════════════════════════════════════════
# ABA 4 – VISIBILIDADE DE SHELF
# ═════════════════════════════════════════════════════════════════════════════
with tab4:
    ch1, ch2 = st.columns([3, 1], vertical_alignment="bottom")
    with ch1:
        st.header("🚨 Visibilidade de Shelf — Estoque Crítico Global")
    with ch2:
        st.markdown("<div style='text-align: right; font-size: 14px;'>🔴 ≤45d &nbsp; 🟡 46-60d &nbsp; 🟢 61-90d</div>", unsafe_allow_html=True)

    if "df_dpo" not in st.session_state:
        st.warning("⚠️ Bases não carregadas — verifique a Aba 1.")
    else:
        df_s = st.session_state["df_dpo"]
        hoje = pd.Timestamp.today().normalize()
        df_r = get_shelf_critico(df_s, hoje)

        cols_want = ["Farol","Código","Descrição","Validade","Validade2",
                     "DZ/PCT","QTD.(Validade1)","QTD.(Validade2)","Venda Média SKU",
                     "Dias até vencimento","Necessários P/ Vender Estoque","Status"]
        cols_ok   = [c for c in cols_want if c in df_r.columns]

        st.markdown("Produtos em Shelf Curto (≤ 90 dias), do mais crítico ao menos.")
        st.metric("Total de SKUs em Risco", len(df_r))

        if not df_r.empty:
            st.dataframe(
                format_df_dates(df_r[cols_ok].sort_values("Dias até vencimento")),
                use_container_width=True,
                height=min((len(df_r)+1)*36+10, 700),
                hide_index=True
            )
        else:
            st.success("🎉 Nenhum SKU com validade < 90 dias!")


# ═════════════════════════════════════════════════════════════════════════════
# ABA 5 – GESTÃO DE AÇÕES (CAMPANHAS)
# ═════════════════════════════════════════════════════════════════════════════
with tab5:
    st.header("🚀 Gestão de Ações (Campanhas)")
    
    opcoes_db = get_campanhas()
    if not opcoes_db:
        st.info("Nenhuma campanha cadastrada ainda. Use a **Aba 2 (Simulador)** para adicionar produtos a uma campanha.")
    else:
        camp_selecionada = st.selectbox("Selecione a Campanha para visualizar:", opcoes_db)
        df_camp = get_skus_campanha(camp_selecionada)
        if df_camp.empty:
            st.warning("Esta campanha está vazia.")
        else:
            st.subheader(f"Painel Executivo: {camp_selecionada}")
            st.metric("Total de SKUs na Ação", len(df_camp))
            
            if "id" in df_camp.columns: df_camp = df_camp.drop(columns=["id", "campanha_nome"])
            
            df_camp = df_camp.rename(columns={
                "cod_prod": "CÓD PROD", "descricao": "DESCRIÇÃO",
                "validade": "VALIDADE", "estoque": "ESTOQUE",
                "ttv_tabela": "TTV TABELA", "ttc_tabela": "TTC TABELA",
                "ttv_acao": "TTV AÇÃO", "ttc_acao": "TTC AÇÃO",
                "fator_boni": "FATOR BONIFICAÇÃO"
            })
            
            st.dataframe(df_camp, use_container_width=True, hide_index=True)
            
            csv_exp = df_camp.to_csv(index=False, sep=";").encode("latin1", errors="replace")
            st.download_button("📥 Exportar Campanha (CSV)", csv_exp, file_name=f"{camp_selecionada}.csv", mime="text/csv")

# ═════════════════════════════════════════════════════════════════════════════
# ABA 6 – PAINEL DE PEDIDOS (NOVO)
# ═════════════════════════════════════════════════════════════════════════════
with tab6:
    st.header("📊 Painel de Pedidos (Mobile Vendas)")
    df_ped = get_pedidos()
    if df_ped.empty:
        st.info("Nenhum pedido recebido ainda.")
    else:
        # Filtros de tempo
        df_ped["data_pedido_dt"] = pd.to_datetime(df_ped["data_pedido"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
        df_ped["mes_ano"] = df_ped["data_pedido_dt"].dt.to_period("M").astype(str)
        df_ped["data_curta"] = df_ped["data_pedido_dt"].dt.date
        
        c_filt1, c_filt2 = st.columns(2)
        visao = c_filt1.selectbox("Filtro de Período", ["Todos", "Hoje", "Mês Atual", "Anual"])
        
        hoje_dt = datetime.now().date()
        mes_atual = pd.Timestamp.now().to_period("M").astype(str)
        ano_atual = hoje_dt.year
        
        if visao == "Hoje":
            df_ped = df_ped[df_ped["data_curta"] == hoje_dt]
        elif visao == "Mês Atual":
            df_ped = df_ped[df_ped["mes_ano"] == mes_atual]
        elif visao == "Anual":
            df_ped = df_ped[df_ped["data_pedido_dt"].dt.year == ano_atual]

        if df_ped.empty:
            st.warning("Nenhum pedido no período selecionado.")
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("Total de Pedidos", len(df_ped))
            c2.metric("Caixas Vendidas", f"{df_ped['qtd_compra'].sum():,}".replace(",", "."))
            c3.metric("Faturamento (Ação)", f"R$ {df_ped['valor_total'].sum():,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            
            st.divider()
            
            for idx, row in df_ped.iterrows():
                try: 
                    stat = row.get('status_faturamento', 'Pendente')
                except:
                    stat = 'Pendente'
                    
                cor = "🟢" if stat == "Faturado" else "🔴" if stat == "Cancelado" else "🟡"
                
                with st.expander(f"{cor} Pedido #{row['id']} - {row['cliente']} | R$ {row['valor_total']:,.2f}"):
                    rc1, rc2, rc3 = st.columns(3)
                    rc1.write(f"**Vendedor:** {row['vendedor']}")
                    rc1.write(f"**Data:** {row['data_pedido']}")
                    rc2.write(f"**Produto:** {row['descricao']}")
                    rc2.write(f"**Qtd:** {row['qtd_compra']} (+{row['qtd_bonificada']} boni)")
                    rc3.write(f"**TTC BEES:** {row.get('ttc_bees', '-')}")
                    rc3.write(f"**Prazo:** {row.get('prazo_pagamento', '-')}")
                    
                    if stat == 'Pendente':
                        vc1, vc2, vc3 = st.columns(3)
                        if vc1.button("✅ Validar Faturamento", key=f"val_{row['id']}"):
                            atualizar_status_pedido(row['id'], "Faturado")
                            st.rerun()
                        if vc2.button("❌ Cancelar", key=f"canc_{row['id']}"):
                            atualizar_status_pedido(row['id'], "Cancelado")
                            st.rerun()
