import streamlit as st
import sqlite3
import hashlib
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import json

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
                categoria TEXT,    -- para despesa
                username TEXT NOT NULL, -- Para vincular a transação ao usuário logado
                
                -- Campos específicos para Receita
                responsavel TEXT, 
                banco TEXT,       
                forma_recebimento TEXT, 
                datas_parcelas_receita TEXT,    -- JSON string de datas
                
                -- Novos campos específicos para Despesa
                recorrente TEXT,    -- 'Sim' ou 'Não'
                vezes_recorrencia INTEGER, -- Quantas vezes a despesa se repete
                status TEXT,        -- 'A Pagar' ou 'Pago'
                
                FOREIGN KEY (username) REFERENCES users(username)
            )
        ''')
        conn.commit()

def add_transaction(username, data, descricao, valor, tipo, categoria=None,
                    responsavel=None, banco=None, forma_recebimento=None, datas_parcelas_receita=None,
                    recorrente=None, vezes_recorrencia=None, status=None):
    """Adiciona uma nova transação ao banco de dados, vinculada ao usuário."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO transacoes (username, data, descricao, valor, tipo, categoria,
                                    responsavel, banco, forma_recebimento, datas_parcelas_receita,
                                    recorrente, vezes_recorrencia, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (username, data, descricao, valor, tipo, categoria,
              responsavel, banco, forma_recebimento, datas_parcelas_receita,
              recorrente, vezes_recorrencia, status))
        conn.commit()

def get_transactions(username):
    """Recupera todas as transações de um usuário específico."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        # Seleciona todos os campos para poder exibir os novos campos de receita/despesa
        cursor.execute('''
            SELECT id, data, descricao, valor, tipo, categoria, responsavel, banco,
                   forma_recebimento, datas_parcelas_receita, recorrente,
                   vezes_recorrencia, status
            FROM transacoes WHERE username = ? ORDER BY data DESC
        ''', (username,))
        return cursor.fetchall()

def delete_transaction(transaction_id, username):
    """Exclui uma transação específica de um usuário."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM transacoes WHERE id = ? AND username = ?", (transaction_id, username))
        conn.commit()
        return cursor.rowcount > 0 # Retorna True se alguma linha foi deletada

def get_summary(username):
    """Calcula o resumo de receitas e despesas para um usuário específico."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(valor) FROM transacoes WHERE username = ? AND tipo = 'receita'", (username,))
        total_receitas = cursor.fetchone()[0] or 0.0

        cursor.execute("SELECT SUM(valor) FROM transacoes WHERE username = ? AND tipo = 'despesa' AND status = 'Pago'", (username,))
        total_despesas_pagas = cursor.fetchone()[0] or 0.0

        cursor.execute("SELECT SUM(valor) FROM transacoes WHERE username = ? AND tipo = 'despesa' AND status = 'A Pagar'", (username,))
        total_despesas_apagar = cursor.fetchone()[0] or 0.0

        return total_receitas, total_despesas_pagas, total_despesas_apagar

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
        descricao = st.text_input(f"Descrição da {transaction_type.capitalize()}")
        valor = st.number_input("Valor", min_value=0.01, format="%.2f")

        # Inicializa todos os campos extras como None
        responsavel = None
        banco = None
        forma_recebimento = None
        datas_parcelas_receita_json = None
        categoria_selecionada = None
        recorrente = None
        vezes_recorrencia = None
        status = None

        if transaction_type == "receita":
            st.subheader("Detalhes da Entrada")
            responsavel = st.selectbox("Responsável pela Entrada", ["Higo", "Raissa"])
            banco = st.selectbox("Banco", ["Itaú - Raissa", "C6 - Raissa", "Nubank - Raissa", "PagBank - Clear"])
            tipo_entrada = st.selectbox("Tipo de Entrada", ["Venda de Produto", "Prestação de Serviço"]) 
            categoria_selecionada = tipo_entrada # Usamos categoria para tipo de entrada na DB

            forma_recebimento = st.selectbox("Forma de Recebimento", ["Parcela Única", "2x", "3x"])

            if forma_recebimento in ["2x", "3x"]:
                st.markdown("##### Datas de Recebimento das Parcelas")
                datas_parcelas = []
                num_parcelas = int(forma_recebimento.replace('x', ''))
                for i in range(1, num_parcelas + 1):
                    parcel_date = st.date_input(f"Data da {i}ª Parcela", datetime.now() + pd.DateOffset(months=i-1), key=f"receita_parcel_date_{i}")
                    datas_parcelas.append(parcel_date.strftime("%Y-%m-%d"))
                datas_parcelas_receita_json = json.dumps(datas_parcelas) 

        elif transaction_type == "despesa":
            st.subheader("Detalhes da Despesa")
            categorias_despesa = [
                "Alimentação", "Transporte", "Moradia", "Lazer", "Educação",
                "Saúde", "Contas Fixas", "Compras", "Outros"
            ]
            categoria_selecionada = st.selectbox("Categoria", categorias_despesa)

            recorrente = st.radio("Despesa Recorrente?", ["Não", "Sim"])
            if recorrente == "Sim":
                vezes_recorrencia = st.number_input("Quantas vezes a despesa se repete (incluindo a atual)?", min_value=1, value=1, step=1)
                st.info("Para despesas recorrentes, apenas o primeiro lançamento é adicionado. As futuras parcelas precisam ser registradas individualmente ou por automação.")
            
            status = st.radio("Status da Despesa", ["A Pagar", "Pago"])


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
                        categoria=categoria_selecionada, 
                        responsavel=responsavel,
                        banco=banco,
                        forma_recebimento=forma_recebimento,
                        datas_parcelas_receita=datas_parcelas_receita_json,
                        recorrente=recorrente,          
                        vezes_recorrencia=vezes_recorrencia, 
                        status=status                   
                    )
                    st.success(f"{transaction_type.capitalize()} adicionada com sucesso!")
                    st.balloons()
                    # st.rerun() # Descomentar se quiser que o dashboard atualize imediatamente
                except Exception as e:
                    st.error(f"Erro ao adicionar {transaction_type}: {e}")
                    st.exception(e) # Mostra o erro completo para debug

def render_analysis_dashboard():
    """Renderiza o dashboard de análise de finanças."""
    current_username = st.session_state['username']
    st.header("Visão Geral Financeira")

    total_receitas, total_despesas_pagas, total_despesas_apagar = get_summary(current_username)
    saldo_real = total_receitas - total_despesas_pagas
    saldo_projetado = total_receitas - (total_despesas_pagas + total_despesas_apagar)


    st.markdown(f"### Saldo Real (Até o momento): R$ {saldo_real:,.2f}")
    st.markdown(f"### Saldo Projetado (Considerando a Pagar): R$ {saldo_projetado:,.2f}")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Receitas", f"R$ {total_receitas:,.2f}", delta_color="normal")
    with col2:
        st.metric("Despesas Pagas", f"R$ {total_despesas_pagas:,.2f}", delta_color="inverse")
    with col3:
        st.metric("Despesas a Pagar", f"R$ {total_despesas_apagar:,.2f}", delta_color="inverse")

    st.subheader("Todas as Transações")
    transactions_data = get_transactions(current_username)
    
    if transactions_data:
        # Colunas esperadas agora (ID adicionado ao SELECT):
        df = pd.DataFrame(transactions_data, columns=[
            'ID', 'Data', 'Descrição', 'Valor', 'Tipo', 'Categoria', 'Responsavel', 'Banco',
            'Forma Recebimento', 'Datas Parcelas Receita', 'Recorrente', 'Vezes Recorrencia', 'Status'
        ])
        
        df['Valor_Exibicao'] = df.apply(lambda row: -row['Valor'] if row['Tipo'] == 'despesa' else row['Valor'], axis=1)
        df['Tipo'] = df['Tipo'].apply(lambda x: 'Despesa' if x == 'despesa' else 'Receita')
        
        # Display columns for the main table (without ID for user view)
        display_columns = [
            'Data', 'Tipo', 'Descrição', 'Valor_Exibicao', 'Categoria', 'Status',
            'Responsavel', 'Banco', 'Forma Recebimento', 'Recorrente'
        ]
        
        st.dataframe(df[display_columns].style.format({'Valor_Exibicao': "R$ {:,.2f}"}), use_container_width=True)

        st.subheader("Excluir Transação")
        transaction_ids = df['ID'].tolist()
        if transaction_ids:
            col_del_id, col_del_btn = st.columns([0.7, 0.3])
            trans_to_delete = col_del_id.selectbox("Selecione o ID da transação para excluir", options=transaction_ids)
            if col_del_btn.button("Excluir Selecionada"):
                if delete_transaction(trans_to_delete, current_username):
                    st.success(f"Transação ID {trans_to_delete} excluída com sucesso.")
                    st.rerun() # Recarrega para refletir a exclusão
                else:
                    st.error("Erro ao excluir transação ou ID não encontrado.")
        else:
            st.info("Nenhuma transação para excluir.")

    else:
        st.info("Nenhuma transação registrada ainda.")


    st.markdown("---")
    st.subheader("Saldos por Responsável")
    if transactions_data:
        df_all = pd.DataFrame(transactions_data, columns=[
            'ID', 'Data', 'Descrição', 'Valor', 'Tipo', 'Categoria', 'Responsavel', 'Banco',
            'Forma Recebimento', 'Datas Parcelas Receita', 'Recorrente', 'Vezes Recorrencia', 'Status'
        ])
        
        # Considerando que Despesas não tem 'Responsável', vamos atribuir ao usuário logado ou criar uma lógica para isso.
        # Para simplificar, vou focar no 'Responsável' da Receita por enquanto.
        # Para despesas, precisaríamos de um campo 'Responsável pela Despesa' se quisermos granular por pessoa.
        
        # Saldo por Responsável (focando em Receitas)
        receitas_por_responsavel = df_all[df_all['Tipo'] == 'receita'].groupby('Responsavel')['Valor'].sum()
        if not receitas_por_responsavel.empty:
            st.dataframe(receitas_por_responsavel.reset_index().style.format({'Valor': "R$ {:,.2f}"}))
        else:
            st.info("Nenhuma receita registrada por responsável para análise.")
            
        # Saldo por Banco
        receitas_por_banco = df_all[df_all['Tipo'] == 'receita'].groupby('Banco')['Valor'].sum()
        if not receitas_por_banco.empty:
            st.subheader("Receitas por Banco")
            st.dataframe(receitas_por_banco.reset_index().style.format({'Valor': "R$ {:,.2f}"}))
        else:
            st.info("Nenhuma receita registrada por banco para análise.")
            
    st.markdown("---")
    st.subheader("Análise de Gastos por Categoria (Despesas Pagas)")
    if transactions_data:
        df = pd.DataFrame(transactions_data, columns=[
            'ID', 'Data', 'Descrição', 'Valor', 'Tipo', 'Categoria', 'Responsavel', 'Banco',
            'Forma Recebimento', 'Datas Parcelas Receita', 'Recorrente', 'Vezes Recorrencia', 'Status'
        ])
        despesas_pagas_df = df[(df['Tipo'] == 'despesa') & (df['Status'] == 'Pago')]

        if not despesas_pagas_df.empty:
            gastos_por_categoria = despesas_pagas_df.groupby('Categoria')['Valor'].sum().sort_values(ascending=False)
            st.dataframe(gastos_por_categoria.reset_index().style.format({'Valor': "R$ {:,.2f}"}), use_container_width=True)

            fig = px.pie(gastos_por_categoria.reset_index(),
                         values='Valor',
                         names='Categoria',
                         title='Distribuição de Despesas Pagas por Categoria',
                         hole=0.3)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Nenhuma despesa paga para análise por categoria.")
    else:
        st.info("Nenhuma transação para analisar ainda.")

    st.markdown("---")
    st.subheader("Projeção de Fluxo de Caixa Futuro (Próximos 3 Meses)")
    if transactions_data:
        df_proj = pd.DataFrame(transactions_data, columns=[
            'ID', 'Data', 'Descrição', 'Valor', 'Tipo', 'Categoria', 'Responsavel', 'Banco',
            'Forma Recebimento', 'Datas Parcelas Receita', 'Recorrente', 'Vezes Recorrencia', 'Status'
        ])
        
        df_proj['Data'] = pd.to_datetime(df_proj['Data'])
        
        current_date = datetime.now().date()
        future_months = [current_date + pd.DateOffset(months=i) for i in range(4)] # Inclui o mês atual + 3 futuros
        
        projection_data = {}
        for month_date in future_months:
            month_key = month_date.strftime("%Y-%m")
            projection_data[month_key] = {'Receitas': 0.0, 'Despesas': 0.0, 'Saldo': 0.0}

        for index, row in df_proj.iterrows():
            trans_date = row['Data'].date()
            trans_month_key = trans_date.strftime("%Y-%m")

            if row['Tipo'] == 'receita':
                # Adiciona receita ao mês da transação
                if trans_month_key in projection_data:
                    projection_data[trans_month_key]['Receitas'] += row['Valor']
                
                # Se for parcelada, adiciona às datas futuras
                if row['Forma Recebimento'] in ["2x", "3x"] and row['Datas Parcelas Receita']:
                    parcel_dates = json.loads(row['Datas Parcelas Receita'])
                    for p_date_str in parcel_dates:
                        p_date = datetime.strptime(p_date_str, "%Y-%m-%d").date()
                        p_month_key = p_date.strftime("%Y-%m")
                        if p_month_key in projection_data and p_date > current_date:
                            projection_data[p_month_key]['Receitas'] += row['Valor'] / len(parcel_dates) # Divide o valor total pela qtd de parcelas
                            
            elif row['Tipo'] == 'despesa':
                # Adiciona despesa ao mês da transação (seja 'A Pagar' ou 'Pago')
                if trans_month_key in projection_data:
                    projection_data[trans_month_key]['Despesas'] += row['Valor']
                
                # Se for recorrente, projeta para os próximos meses
                if row['Recorrente'] == 'Sim' and row['Vezes Recorrencia'] > 1:
                    for i in range(1, row['Vezes Recorrencia']): # Já contabilizou a primeira
                        future_date = trans_date + pd.DateOffset(months=i).date()
                        future_month_key = future_date.strftime("%Y-%m")
                        if future_month_key in projection_data:
                            projection_data[future_month_key]['Despesas'] += row['Valor']


        # Calcular saldos
        for month_key in projection_data:
            projection_data[month_key]['Saldo'] = projection_data[month_key]['Receitas'] - projection_data[month_key]['Despesas']

        proj_df = pd.DataFrame.from_dict(projection_data, orient='index')
        proj_df.index.name = 'Mês'
        st.dataframe(proj_df.style.format({
            'Receitas': "R$ {:,.2f}", 
            'Despesas': "R$ {:,.2f}", 
            'Saldo': "R$ {:,.2f}"
        }), use_container_width=True)

        fig_proj = px.bar(proj_df.reset_index(), x='Mês', y=['Receitas', 'Despesas', 'Saldo'],
                          title='Projeção Mensal de Fluxo de Caixa',
                          barmode='group')
        st.plotly_chart(fig_proj, use_container_width=True)


    else:
        st.info("Nenhuma transação para projeção ainda.")


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