import streamlit as st
import sqlite3
import hashlib
from datetime import datetime
import pandas as pd
import plotly.express as px

# --- Configurações Iniciais ---
DB_NAME = 'financas_familia.db' # Nome do arquivo do banco de dados

# --- Funções de Ajuda para Segurança (Hashing) ---
def make_hashes(password):
    """Cria um hash SHA256 da senha para armazenamento seguro."""
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    """Verifica se a senha fornecida corresponde ao hash armazenado."""
    return make_hashes(password) == hashed_text

# --- Funções do Banco de Dados para Usuários ---
def init_user_db():
    """Inicializa o banco de dados de usuários e cria a tabela 'users'."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL
            )
        ''')
        conn.commit()

def add_user(username, password):
    """Adiciona um novo usuário ao banco de dados."""
    hashed_password = make_hashes(password)
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
            conn.commit()
            return True
        except sqlite3.IntegrityError: # Usuário já existe
            return False

def verify_user(username, password):
    """Verifica as credenciais do usuário."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()
        if result:
            hashed_password_db = result[0]
            return check_hashes(password, hashed_password_db)
        return False

# --- Funções do Banco de Dados para Transações Financeiras ---
def init_transactions_db():
    """Inicializa o banco de dados de transações e cria a tabela 'transacoes'."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                descricao TEXT NOT NULL,
                valor REAL NOT NULL,
                tipo TEXT NOT NULL, -- 'receita' ou 'despesa'
                categoria TEXT,    -- pode ser nulo para receitas ou indefinido
                username TEXT NOT NULL, -- Para vincular a transação ao usuário logado
                FOREIGN KEY (username) REFERENCES users(username)
            )
        ''')
        conn.commit()

def add_transaction(username, data, descricao, valor, tipo, categoria=None):
    """Adiciona uma nova transação ao banco de dados, vinculada ao usuário."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO transacoes (username, data, descricao, valor, tipo, categoria)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (username, data, descricao, valor, tipo, categoria))
        conn.commit()

def get_transactions(username):
    """Recupera todas as transações de um usuário específico."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT data, descricao, valor, tipo, categoria FROM transacoes WHERE username = ? ORDER BY data DESC', (username,))
        return cursor.fetchall()

def get_summary(username):
    """Calcula o resumo de receitas e despesas para um usuário específico."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(valor) FROM transacoes WHERE username = ? AND tipo = 'receita'", (username,))
        total_receitas = cursor.fetchone()[0] or 0.0

        cursor.execute("SELECT SUM(valor) FROM transacoes WHERE username = ? AND tipo = 'despesa'", (username,))
        total_despesas = cursor.fetchone()[0] or 0.0

        return total_receitas, total_despesas

# --- Inicialização dos Bancos de Dados ---
init_user_db()
init_transactions_db()

# --- Configurações da Página Streamlit ---
st.set_page_config(
    page_title="Finanças da Família 💰",
    page_icon="💸",
    layout="wide"
)

# --- Gerenciamento de Sessão (Login) ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = None

def login_page():
    """Exibe a tela de login e registro."""
    st.title("🔑 Bem-vindo(a) ao Sistema de Finanças Familiares")
    menu = ["Login", "Registrar"]
    choice = st.sidebar.selectbox("Menu", menu)

    if choice == "Login":
        st.subheader("Fazer Login")
        username = st.text_input("Nome de Usuário")
        password = st.text_input("Senha", type='password')

        if st.button("Entrar"):
            if verify_user(username, password):
                st.session_state['logged_in'] = True
                st.session_state['username'] = username
                st.success(f"Login bem-sucedido! Bem-vindo(a), {username} 🎉")
                st.balloons()
                st.rerun() # Recarrega a página para mostrar o dashboard
            else:
                st.error("Nome de usuário ou senha incorretos.")

    elif choice == "Registrar":
        st.subheader("Criar Nova Conta")
        new_username = st.text_input("Escolha um Nome de Usuário")
        new_password = st.text_input("Escolha uma Senha", type='password')
        confirm_password = st.text_input("Confirme a Senha", type='password')

        if st.button("Registrar Nova Conta"):
            if not new_username or not new_password or not confirm_password:
                st.warning("Por favor, preencha todos os campos.")
            elif new_password != confirm_password:
                st.warning("As senhas não coincidem.")
            elif add_user(new_username, new_password):
                st.success("Conta criada com sucesso! Faça login.")
                st.balloons()
            else:
                st.warning("Nome de usuário já existe. Escolha outro.")

def main_app_page():
    """Exibe a página principal do aplicativo com dashboards e funcionalidades."""
    st.title(f"💰 Finanças da Família de {st.session_state['username']}")

    st.sidebar.markdown(f"**Usuário logado:** `{st.session_state['username']}`")
    if st.sidebar.button("Sair"):
        st.session_state['logged_in'] = False
        st.session_state['username'] = None
        st.info("Você foi desconectado(a).")
        st.rerun()

    # --- Abas de Navegação ---
    tab1, tab2, tab3 = st.tabs(["Registro de Transações", "Visão Geral", "Análise de Gastos"])

    with tab1:
        st.header("Novo Lançamento")

        with st.form("transaction_form"):
            tipo = st.radio("Tipo de Transação", ["Despesa", "Receita"])
            data = st.date_input("Data", datetime.now())
            descricao = st.text_input("Descrição (Ex: Pizza, Salário, Conta de Luz)")
            valor = st.number_input("Valor", min_value=0.01, format="%.2f")

            categorias_despesa = [
                "Alimentação", "Transporte", "Moradia", "Lazer", "Educação",
                "Saúde", "Contas Fixas", "Compras", "Outros"
            ]
            categoria_selecionada = None
            if tipo == "Despesa":
                categoria_selecionada = st.selectbox("Categoria", categorias_despesa)
            else:
                st.markdown("<p style='font-size:14px; color:gray;'>Categorias se aplicam principalmente a despesas.</p>", unsafe_allow_html=True)

            submitted = st.form_submit_button("Adicionar Transação")

            if submitted:
                if not descricao or not valor:
                    st.error("Por favor, preencha a descrição e o valor.")
                else:
                    try:
                        data_str = data.strftime("%Y-%m-%d")
                        add_transaction(st.session_state['username'], data_str, descricao, float(valor), tipo.lower(), categoria_selecionada)
                        st.success("Transação adicionada com sucesso!")
                        st.balloons()
                        # Opcional: st.rerun() para atualizar os dashboards imediatamente
                    except Exception as e:
                        st.error(f"Erro ao adicionar transação: {e}")

    with tab2:
        st.header("Visão Geral das Transações")

        total_receitas, total_despesas = get_summary(st.session_state['username'])
        saldo = total_receitas - total_despesas

        st.markdown(f"### Saldo Atual: R$ {saldo:,.2f}")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total de Receitas", f"R$ {total_receitas:,.2f}", delta_color="normal")
        with col2:
            st.metric("Total de Despesas", f"R$ {total_despesas:,.2f}", delta_color="inverse")

        st.subheader("Todas as Transações")
        transactions_data = get_transactions(st.session_state['username'])
        if transactions_data:
            df = pd.DataFrame(transactions_data, columns=['Data', 'Descrição', 'Valor', 'Tipo', 'Categoria'])
            # Ajustar valor para exibir despesas como negativas no DataFrame, se desejar
            df['Valor_Exibicao'] = df.apply(lambda row: -row['Valor'] if row['Tipo'] == 'despesa' else row['Valor'], axis=1)
            df['Tipo'] = df['Tipo'].apply(lambda x: 'Despesa' if x == 'despesa' else 'Receita')
            st.dataframe(df[['Data', 'Descrição', 'Valor_Exibicao', 'Tipo', 'Categoria']].style.format({'Valor_Exibicao': "R$ {:,.2f}"}), use_container_width=True)
        else:
            st.info("Nenhuma transação registrada ainda.")

    with tab3:
        st.header("Análise de Gastos por Categoria")
        transactions_data = get_transactions(st.session_state['username'])
        if transactions_data:
            df = pd.DataFrame(transactions_data, columns=['Data', 'Descrição', 'Valor', 'Tipo', 'Categoria'])
            despesas_df = df[df['Tipo'] == 'despesa']

            if not despesas_df.empty:
                gastos_por_categoria = despesas_df.groupby('Categoria')['Valor'].sum().sort_values(ascending=False)
                st.subheader("Gastos por Categoria")
                st.dataframe(gastos_por_categoria.reset_index().style.format({'Valor': "R$ {:,.2f}"}), use_container_width=True)

                # Gráfico de pizza
                fig = px.pie(gastos_por_categoria.reset_index(),
                             values='Valor',
                             names='Categoria',
                             title='Distribuição de Despesas por Categoria',
                             hole=0.3)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Nenhuma despesa registrada para análise.")
        else:
            st.info("Nenhuma transação para analisar ainda.")

    st.markdown("---")
    st.markdown("Desenvolvido com 💜 e Streamlit para o controle financeiro familiar.")


# --- Lógica Principal da Aplicação ---
if st.session_state['logged_in']:
    main_app_page()
else:
    login_page()