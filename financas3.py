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
                responsavel TEXT, -- Novo campo para Receita
                banco TEXT,       -- Novo campo para Receita
                forma_recebimento TEXT, -- Novo campo para Receita
                datas_parcelas TEXT,    -- Novo campo para Receita (JSON string de datas)
                FOREIGN KEY (username) REFERENCES users(username)
            )
        ''')
        conn.commit()

def add_transaction(username, data, descricao, valor, tipo, categoria=None,
                    responsavel=None, banco=None, forma_recebimento=None, datas_parcelas=None):
    """Adiciona uma nova transação ao banco de dados, vinculada ao usuário."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO transacoes (username, data, descricao, valor, tipo, categoria,
                                    responsavel, banco, forma_recebimento, datas_parcelas)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (username, data, descricao, valor, tipo, categoria,
              responsavel, banco, forma_recebimento, datas_parcelas))
        conn.commit()

def get_transactions(username):
    """Recupera todas as transações de um usuário específico."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        # Seleciona todos os campos para poder exibir os novos campos de receita
        cursor.execute('SELECT data, descricao, valor, tipo, categoria, responsavel, banco, forma_recebimento, datas_parcelas FROM transacoes WHERE username = ? ORDER BY data DESC', (username,))
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
    st.subheader("Login ou Crie sua Conta")

    col_login, col_register = st.columns(2)

    with col_login:
        st.markdown("### Fazer Login")
        username = st.text_input("Nome de Usuário", key="login_username")
        password = st.text_input("Senha", type='password', key="login_password")

        if st.button("Entrar", key="login_button"):
            if verify_user(username, password):
                st.session_state['logged_in'] = True
                st.session_state['username'] = username
                st.success(f"Login bem-sucedido! Bem-vindo(a), {username} 🎉")
                st.balloons()
                st.rerun() # Recarrega a página para mostrar o dashboard
            else:
                st.error("Nome de usuário ou senha incorretos.")

    with col_register:
        st.markdown("### Criar Nova Conta")
        new_username = st.text_input("Escolha um Nome de Usuário", key="register_username")
        new_password = st.text_input("Escolha uma Senha", type='password', key="register_password")
        confirm_password = st.text_input("Confirme a Senha", type='password', key="confirm_password")

        if st.button("Registrar Nova Conta", key="register_button"):
            if not new_username or not new_password or not confirm_password:
                st.warning("Por favor, preencha todos os campos.")
            elif new_password != confirm_password:
                st.warning("As senhas não coincidem.")
            elif add_user(new_username, new_password):
                st.success("Conta criada com sucesso! Faça login na coluna ao lado.")
                st.balloons()
            else:
                st.warning("Nome de usuário já existe. Escolha outro.")

def render_transaction_form(transaction_type):
    """Função para renderizar o formulário de Entrada/Despesa."""
    current_username = st.session_state['username']
    st.header(f"Registrar {transaction_type.capitalize()}")

    with st.form(f"{transaction_type}_form"):
        data_transacao = st.date_input("Data da Transação", datetime.now())
        descricao = st.text_input("Descrição (Ex: Venda de Ebook, Conta de Luz)")
        valor = st.number_input("Valor", min_value=0.01, format="%.2f")

        responsavel = None
        banco = None
        forma_recebimento = None
        datas_parcelas_json = None
        categoria_selecionada = None # Inicializa para Despesa

        if transaction_type == "receita":
            st.subheader("Detalhes da Entrada")
            responsavel = st.selectbox("Responsável pela Entrada", ["Higo", "Raissa"])
            banco = st.selectbox("Banco", ["Itaú - Raissa", "C6 - Raissa", "Nubank - Raissa", "PagBank - Clear"])
            tipo_entrada = st.selectbox("Tipo de Entrada", ["Venda de Produto", "Prestação de Serviço"])
            forma_recebimento = st.selectbox("Forma de Recebimento", ["Parcela Única", "2x", "3x"])

            if forma_recebimento in ["2x", "3x"]:
                st.markdown("##### Datas de Recebimento das Parcelas")
                datas_parcelas = []
                num_parcelas = int(forma_recebimento.replace('x', ''))
                for i in range(1, num_parcelas + 1):
                    parcel_date = st.date_input(f"Data da {i}ª Parcela", datetime.now() + pd.DateOffset(months=i-1), key=f"parcel_date_{i}")
                    datas_parcelas.append(parcel_date.strftime("%Y-%m-%d"))
                import json
                datas_parcelas_json = json.dumps(datas_parcelas) # Armazenar como JSON string
        elif transaction_type == "despesa":
            st.subheader("Detalhes da Despesa")
            categorias_despesa = [
                "Alimentação", "Transporte", "Moradia", "Lazer", "Educação",
                "Saúde", "Contas Fixas", "Compras", "Outros"
            ]
            categoria_selecionada = st.selectbox("Categoria", categorias_despesa)


        submitted = st.form_submit_button("Adicionar Lançamento")

        if submitted:
            if not descricao or not valor:
                st.error("Por favor, preencha a descrição e o valor.")
            else:
                try:
                    data_str = data_transacao.strftime("%Y-%m-%d")
                    add_transaction(
                        username=current_username,
                        data=data_str,
                        descricao=descricao,
                        valor=float(valor),
                        tipo=transaction_type,
                        categoria=categoria_selecionada, # Apenas para despesas
                        responsavel=responsavel,         # Apenas para receitas
                        banco=banco,                     # Apenas para receitas
                        forma_recebimento=forma_recebimento, # Apenas para receitas
                        datas_parcelas=datas_parcelas_json # Apenas para receitas
                    )
                    st.success(f"{transaction_type.capitalize()} adicionada com sucesso!")
                    st.balloons()
                    # Opcional: st.rerun() para atualizar os dashboards imediatamente
                except Exception as e:
                    st.error(f"Erro ao adicionar {transaction_type}: {e}")

def render_analysis_dashboard():
    """Renderiza o dashboard de análise de finanças."""
    current_username = st.session_state['username']
    st.header("Visão Geral Financeira")

    total_receitas, total_despesas = get_summary(current_username)
    saldo = total_receitas - total_despesas

    st.markdown(f"### Saldo Atual: R$ {saldo:,.2f}")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total de Receitas", f"R$ {total_receitas:,.2f}", delta_color="normal")
    with col2:
        st.metric("Total de Despesas", f"R$ {total_despesas:,.2f}", delta_color="inverse")

    st.subheader("Transações Recentes")
    transactions_data = get_transactions(current_username)
    if transactions_data:
        # Ajuste para as novas colunas
        df = pd.DataFrame(transactions_data, columns=['Data', 'Descrição', 'Valor', 'Tipo', 'Categoria', 'Responsável', 'Banco', 'Forma Recebimento', 'Datas Parcelas'])
        df['Valor_Exibicao'] = df.apply(lambda row: -row['Valor'] if row['Tipo'] == 'despesa' else row['Valor'], axis=1)
        df['Tipo'] = df['Tipo'].apply(lambda x: 'Despesa' if x == 'despesa' else 'Receita')
        
        # Seleciona e exibe as colunas relevantes
        display_columns = ['Data', 'Descrição', 'Valor_Exibicao', 'Tipo', 'Categoria', 'Responsável', 'Banco', 'Forma Recebimento']
        
        st.dataframe(df[display_columns].style.format({'Valor_Exibicao': "R$ {:,.2f}"}), use_container_width=True)
    else:
        st.info("Nenhuma transação registrada ainda.")

    st.subheader("Análise de Gastos por Categoria")
    if transactions_data:
        df = pd.DataFrame(transactions_data, columns=['Data', 'Descrição', 'Valor', 'Tipo', 'Categoria', 'Responsável', 'Banco', 'Forma Recebimento', 'Datas Parcelas'])
        despesas_df = df[df['Tipo'] == 'despesa']

        if not despesas_df.empty:
            gastos_por_categoria = despesas_df.groupby('Categoria')['Valor'].sum().sort_values(ascending=False)
            st.dataframe(gastos_por_categoria.reset_index().style.format({'Valor': "R$ {:,.2f}"}), use_container_width=True)

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

def render_planning_section():
    """Esboço da seção de Planejamento."""
    st.header("Planejamento Financeiro")
    st.info("Esta seção ainda está em desenvolvimento. Aqui você poderá definir orçamentos, metas e projeções.")
    st.write("Em breve: Orçamentos por categoria, metas de economia, projeções de fluxo de caixa.")
    # Você pode adicionar campos para:
    # st.text_input("Definir Orçamento para Categoria X")
    # st.number_input("Meta de Economia Mensal")

# --- Lógica Principal da Aplicação ---
if st.session_state['logged_in']:
    st.sidebar.title(f"Olá, {st.session_state['username']}!")
    
    # Menu lateral para as funcionalidades
    app_menu = ["Análise de Finanças", "Registrar Entrada", "Registrar Despesa", "Planejamento"]
    selected_option = st.sidebar.selectbox("Navegação", app_menu)

    if selected_option == "Análise de Finanças":
        render_analysis_dashboard()
    elif selected_option == "Registrar Entrada":
        render_transaction_form("receita")
    elif selected_option == "Registrar Despesa":
        render_transaction_form("despesa")
    elif selected_option == "Planejamento":
        render_planning_section()

    st.sidebar.markdown("---")
    if st.sidebar.button("Sair"):
        st.session_state['logged_in'] = False
        st.session_state['username'] = None
        st.info("Você foi desconectado(a).")
        st.rerun()
else:
    login_page()

st.markdown("---")
st.markdown("Desenvolvido com 💜 e Streamlit para o controle financeiro familiar.")