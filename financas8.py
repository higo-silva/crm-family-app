import streamlit as st
import sqlite3
import hashlib
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import json

# --- Configurações da Página Streamlit (DEVE SER O PRIMEIRO COMANDO STREAMLIT) ---
st.set_page_config(
    page_title="Finanças da Família 💰",
    page_icon="💸",
    layout="wide"
)

# --- Configurações Iniciais ---
DB_NAME = 'financas_familia.db' # Nome do arquivo do banco de dados

# --- Carregar CSS personalizado ---
try:
    with open('style.css') as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
except FileNotFoundError:
    st.warning("Arquivo style.css não encontrado. O aplicativo pode não ter o estilo esperado.")

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
                categoria TEXT,    -- para despesa ou tipo de receita
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

def update_transaction(transaction_id, username, **kwargs):
    """Atualiza uma transação específica de um usuário."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values())
        values.extend([transaction_id, username]) # Adiciona ID e username no final para a cláusula WHERE

        try:
            cursor.execute(f"UPDATE transacoes SET {set_clause} WHERE id = ? AND username = ?", tuple(values))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Erro ao atualizar transação: {e}")
            return False

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

# --- Funções de Renderização de Formulários ---
def render_unified_transaction_form(current_username):
    """Função para renderizar o formulário de Entrada/Despesa unificado."""
    st.header("➕ Adicionar Novo Lançamento")

    # Escolha do tipo de lançamento
    transaction_type = st.radio("Tipo de Lançamento", ["Receita", "Despesa"], horizontal=True)

    with st.form("unified_transaction_form", clear_on_submit=True):
        # Campos comuns a ambos os tipos
        col_date, col_value = st.columns(2)
        with col_date:
            data_transacao = st.date_input("Data da Transação", datetime.now())
        with col_value:
            valor = st.number_input("Valor (R$)", min_value=0.01, format="%.2f")
        
        descricao = st.text_input("Descrição", placeholder="Ex: Salário, Aluguel, Compra de Supermercado")

        # Inicializa todos os campos extras como None
        responsavel = None
        banco = None
        forma_recebimento = None
        datas_parcelas_receita_json = None
        categoria_selecionada = None
        recorrente = None
        vezes_recorrencia = None
        status = None

        if transaction_type == "Receita":
            st.markdown("---")
            st.subheader("Detalhes da Receita")
            col_resp, col_bank = st.columns(2)
            with col_resp:
                responsavel = st.selectbox("Responsável pela Entrada", ["Higo", "Raissa", "Outro"])
            with col_bank:
                banco = st.selectbox("Banco", ["Itaú - Raissa", "C6 - Raissa", "Nubank - Raissa", "PagBank - Clear", "Outro"])
            
            col_type, col_form = st.columns(2)
            with col_type:
                # Usamos categoria para tipo de entrada na DB
                categoria_selecionada = st.selectbox("Tipo de Entrada (Categoria)", ["Venda de Produto", "Prestação de Serviço", "Salário", "Investimento", "Outros"]) 
            with col_form:
                forma_recebimento = st.selectbox("Forma de Recebimento", ["Parcela Única", "2x", "3x", "4x", "5x", "6x", "Mais de 6x"])

            if forma_recebimento not in ["Parcela Única", "Mais de 6x"]:
                st.markdown("##### Datas de Recebimento das Parcelas")
                datas_parcelas = []
                try:
                    num_parcelas = int(forma_recebimento.replace('x', ''))
                    for i in range(1, num_parcelas + 1):
                        parcel_date = st.date_input(f"Data da {i}ª Parcela", datetime.now().date() + pd.DateOffset(months=i-1), key=f"receita_parcel_date_{i}")
                        datas_parcelas.append(parcel_date.strftime("%Y-%m-%d"))
                    datas_parcelas_receita_json = json.dumps(datas_parcelas)
                except ValueError: # Caso seja "Mais de 6x" ou outra opção que não converta para int
                    st.warning("Para 'Mais de 6x', por favor, registre as parcelas individualmente.")

            # Limpar campos de despesa
            recorrente, vezes_recorrencia, status = None, None, None

        elif transaction_type == "Despesa":
            st.markdown("---")
            st.subheader("Detalhes da Despesa")
            categorias_despesa = [
                "Alimentação", "Transporte", "Moradia", "Lazer", "Educação",
                "Saúde", "Contas Fixas", "Compras", "Outros", "Investimentos"
            ]
            categoria_selecionada = st.selectbox("Categoria", categorias_despesa)

            col_rec, col_status = st.columns(2)
            with col_rec:
                recorrente = st.radio("Despesa Recorrente?", ["Não", "Sim"])
                vezes_recorrencia = None
                if recorrente == "Sim":
                    vezes_recorrencia = st.number_input("Quantas vezes a despesa se repete (incluindo a atual)?", min_value=1, value=1, step=1)
                    st.info("Para despesas recorrentes, apenas o primeiro lançamento é adicionado. As futuras parcelas precisam ser registradas individualmente ou por automação.")
            with col_status:
                status = st.radio("Status da Despesa", ["A Pagar", "Pago"])
            
            # Limpar campos de receita
            responsavel, banco, forma_recebimento, datas_parcelas_receita_json = None, None, None, None

        submitted = st.form_submit_button("Adicionar Lançamento", use_container_width=True)

        if submitted:
            if not descricao or not valor:
                st.error("Por favor, preencha a descrição e o valor.")
            else:
                try:
                    data_str = data_transacao.strftime("%Y-%m-%d")
                    add_transaction( # Chamada para a função global
                        username=current_username,
                        data=data_str,
                        descricao=descricao,
                        valor=float(valor),
                        tipo=transaction_type.lower(),
                        categoria=categoria_selecionada, 
                        responsavel=responsavel,
                        banco=banco,
                        forma_recebimento=forma_recebimento,
                        datas_parcelas_receita=datas_parcelas_receita_json,
                        recorrente=recorrente,          
                        vezes_recorrencia=vezes_recorrencia, 
                        status=status                   
                    )
                    st.success(f"{transaction_type.capitalize()} adicionada com sucesso! 🎉")
                    st.balloons()
                    st.rerun() # Recarrega a página para refletir a nova transação
                except Exception as e:
                    st.error(f"Erro ao adicionar {transaction_type}: {e}")
                    st.exception(e) # Mostra o erro completo para debug

# --- Funções de Renderização dos Elementos do Dashboard e Análises ---
def render_overview_dashboard(current_username, df_all_transactions):
    """Renderiza o dashboard de visão geral compacta."""
    st.header("📊 Visão Geral Financeira")

    total_receitas, total_despesas_pagas, total_despesas_apagar = get_summary(current_username)
    saldo_real = total_receitas - total_despesas_pagas
    saldo_projetado = total_receitas - (total_despesas_pagas + total_despesas_apagar)

    st.markdown(f"### Saldo Real (Até o momento): <span style='color:{'green' if saldo_real >= 0 else 'red'};'>R$ {saldo_real:,.2f}</span>", unsafe_allow_html=True)
    st.markdown(f"### Saldo Projetado (Considerando a Pagar): <span style='color:{'green' if saldo_projetado >= 0 else 'red'};'>R$ {saldo_projetado:,.2f}</span>", unsafe_allow_html=True)

    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Receitas", f"R$ {total_receitas:,.2f}", delta_color="normal")
    with col2:
        st.metric("Despesas Pagas", f"R$ {total_despesas_pagas:,.2f}", delta_color="inverse")
    with col3:
        st.metric("Despesas a Pagar", f"R$ {total_despesas_apagar:,.2f}", delta_color="inverse")
    
    st.markdown("---")
    st.subheader("Tendência Mensal (Últimos 12 Meses)")
    if not df_all_transactions.empty:
        # Filtrar transações dos últimos 12 meses
        end_date = datetime.now()
        start_date = end_date - pd.DateOffset(months=12)
        
        df_filtered = df_all_transactions[
            (df_all_transactions['Data'] >= start_date) & 
            (df_all_transactions['Data'] <= end_date)
        ].copy() 

        if not df_filtered.empty:
            df_filtered['AnoMes'] = df_filtered['Data'].dt.to_period('M').astype(str)
            
            # Garante que 'receita' e 'despesa' sejam categorias no 'Tipo' para unstack
            # Adiciona um pivot_table para garantir todas as combinações de AnoMes e Tipo
            monthly_summary = pd.pivot_table(df_filtered, values='Valor', index='AnoMes', columns='Tipo', aggfunc='sum', fill_value=0)
            
            # Renomeia as colunas para o que px.line espera
            monthly_summary = monthly_summary.rename(columns={'despesa': 'Despesa', 'receita': 'Receita'})
            
            # Garante que as colunas existam, mesmo que vazias
            for col in ['Receita', 'Despesa']:
                if col not in monthly_summary.columns:
                    monthly_summary[col] = 0.0

            monthly_summary['Saldo'] = monthly_summary['Receita'] - monthly_summary['Despesa']
            
            # Reindexar para garantir todos os meses no período
            all_months = pd.period_range(start_date, end_date, freq='M').astype(str)
            # Use .reindex() com colunas após garantir que elas existem
            monthly_summary = monthly_summary.reindex(all_months, fill_value=0)
            
            # Assegura que o índice seja um RangeIndex ou similar para px.line
            monthly_summary = monthly_summary.reset_index()

            fig = px.line(monthly_summary, x='AnoMes', y=['Receita', 'Despesa', 'Saldo'], # Usar nomes das colunas renomeadas
                          title='Receitas, Despesas e Saldo Mensal',
                          labels={'value': 'Valor (R$)', 'AnoMes': 'Mês'},
                          color_discrete_map={'Receita': 'green', 'Despesa': 'red', 'Saldo': 'blue'})
            fig.update_layout(hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Nenhuma transação nos últimos 12 meses para análise de tendência.")
    else:
        st.info("Nenhuma transação para análise de tendência ainda.")

    st.markdown("---")
    st.subheader("Últimas Transações")
    if not df_all_transactions.empty:
        # Exibe as 10 transações mais recentes
        display_columns = [
            'Data', 'Tipo', 'Descrição', 'Valor', 'Categoria', 'Status',
            'Responsavel', 'Banco', 'Forma Recebimento', 'Recorrente'
        ]
        # Formata o valor para exibição (negativo para despesas)
        df_display = df_all_transactions.head(10).copy()
        df_display['Valor_Exibicao'] = df_display.apply(lambda row: -row['Valor'] if row['Tipo'] == 'despesa' else row['Valor'], axis=1)
        df_display['Tipo_Exibicao'] = df_display['Tipo'].apply(lambda x: 'Despesa' if x == 'despesa' else 'Receita')
        
        st.dataframe(df_display[display_columns].style.format({'Valor_Exibicao': "R$ {:,.2f}"}), use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma transação recente para exibir.")

def render_transactions_table(current_username, df_all_transactions):
    """Renderiza a tabela de todas as transações com funcionalidades de filtro, busca e edição."""
    st.header("📝 Todas as Transações")

    if df_all_transactions.empty:
        st.info("Nenhuma transação registrada ainda.")
        return

    # --- Filtros e Busca ---
    st.subheader("Filtros")
    col_search, col_type_filter = st.columns([2, 1])
    with col_search:
        search_query = st.text_input("Buscar por Descrição ou Categoria", placeholder="Ex: aluguel, salário, supermercado")
    with col_type_filter:
        type_filter = st.selectbox("Filtrar por Tipo", ["Todos", "Receita", "Despesa"])

    col_cat_filter, col_status_filter = st.columns(2)
    with col_cat_filter:
        all_categories = df_all_transactions['Categoria'].dropna().unique().tolist()
        category_filter = st.multiselect("Filtrar por Categoria", options=all_categories, default=all_categories)
    with col_status_filter:
        all_statuses = df_all_transactions['Status'].dropna().unique().tolist()
        status_filter = st.multiselect("Filtrar por Status (Despesa)", options=all_statuses, default=all_statuses)

    col_date_start, col_date_end = st.columns(2)
    with col_date_start:
        min_date_val = df_all_transactions['Data'].min().date() if not df_all_transactions.empty else datetime.now().date()
        date_start = st.date_input("Data Inicial", min_date_val)
    with col_date_end:
        max_date_val = df_all_transactions['Data'].max().date() if not df_all_transactions.empty else datetime.now().date()
        date_end = st.date_input("Data Final", datetime.now().date())

    df_filtered = df_all_transactions.copy()

    # Aplicar filtros
    if search_query:
        df_filtered = df_filtered[
            df_filtered['Descrição'].str.contains(search_query, case=False, na=False) |
            df_filtered['Categoria'].str.contains(search_query, case=False, na=False)
        ]
    
    if type_filter != "Todos":
        df_filtered = df_filtered[df_filtered['Tipo'] == type_filter.lower()]
    
    if category_filter:
        df_filtered = df_filtered[df_filtered['Categoria'].isin(category_filter)]
    
    if status_filter:
        # Apenas aplica o filtro de status para despesas ou se o tipo for "Despesa"
        if type_filter == "Despesa":
            df_filtered = df_filtered[df_filtered['Status'].isin(status_filter)]
        elif type_filter == "Todos":
            # Filtra despesas pelo status e concatena com receitas
            despesas_filtradas = df_filtered[(df_filtered['Tipo'] == 'despesa') & (df_filtered['Status'].isin(status_filter))]
            receitas = df_filtered[df_filtered['Tipo'] == 'receita']
            df_filtered = pd.concat([despesas_filtradas, receitas])

    # Filtrar por data
    df_filtered = df_filtered[
        (df_filtered['Data'].dt.date >= date_start) & 
        (df_filtered['Data'].dt.date <= date_end)
    ]
    
    # Adicionar coluna de exibição para valores
    df_filtered['Valor_Exibicao'] = df_filtered.apply(lambda row: -row['Valor'] if row['Tipo'] == 'despesa' else row['Valor'], axis=1)
    df_filtered['Tipo_Exibicao'] = df_filtered['Tipo'].apply(lambda x: 'Despesa' if x == 'despesa' else 'Receita')

    # Colunas a serem exibidas e formatadas
    display_cols_for_editor = [
        'ID', 'Data', 'Tipo_Exibicao', 'Descrição', 'Valor_Exibicao', 'Categoria', 'Status',
        'Responsavel', 'Banco', 'Forma Recebimento', 'Recorrente'
    ]
    
    st.subheader("Transações Encontradas")
    if not df_filtered.empty:
        # Usar st.data_editor para permitir edição e exclusão
        edited_df = st.data_editor(
            df_filtered[display_cols_for_editor].rename(columns={'Tipo_Exibicao': 'Tipo', 'Valor_Exibicao': 'Valor'}),
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "ID": st.column_config.NumberColumn("ID", help="Identificador único da transação", disabled=True),
                "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                "Tipo": st.column_config.Column("Tipo", disabled=True), # Não permitir mudar o tipo diretamente
                "Valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
                "Categoria": st.column_config.SelectboxColumn(
                    "Categoria", options=["Alimentação", "Transporte", "Moradia", "Lazer", "Educação",
                                         "Saúde", "Contas Fixas", "Compras", "Outros", 
                                         "Venda de Produto", "Prestação de Serviço", "Salário", "Investimento", "Outro"],
                    required=True
                ),
                "Status": st.column_config.SelectboxColumn("Status", options=["A Pagar", "Pago"]),
                "Responsavel": st.column_config.SelectboxColumn("Responsável", options=["Higo", "Raissa", "Outro"]),
                "Banco": st.column_config.SelectboxColumn("Banco", options=["Itaú - Raissa", "C6 - Raissa", "Nubank - Raissa", "PagBank - Clear", "Outro"]),
                "Forma Recebimento": st.column_config.SelectboxColumn("Forma Recebimento", options=["Parcela Única", "2x", "3x", "4x", "5x", "6x", "Mais de 6x"]),
                "Recorrente": st.column_config.SelectboxColumn("Recorrente?", options=["Não", "Sim"]),
                # Não exibir "Vezes Recorrencia" e "Datas Parcelas Receita" diretamente aqui para simplicidade
            }
        )

        st.markdown("---")
        st.subheader("Ações na Tabela")
        col_save, col_delete = st.columns(2)

        with col_save:
            if st.button("Salvar Alterações na Tabela", use_container_width=True):
                rows_updated = 0
                for index, edited_row in edited_df.iterrows():
                    original_row = df_filtered[df_filtered['ID'] == edited_row['ID']].iloc[0]
                    
                    valor_original_db = original_row['Valor']
                    valor_editado_db = abs(edited_row['Valor']) 

                    changes = {}
                    if edited_row['Descrição'] != original_row['Descrição']:
                        changes['descricao'] = edited_row['Descrição']
                    if valor_editado_db != valor_original_db:
                        changes['valor'] = valor_editado_db
                    if edited_row['Categoria'] != original_row['Categoria']:
                        changes['categoria'] = edited_row['Categoria']
                    if edited_row['Status'] != original_row['Status']:
                        changes['status'] = edited_row['Status']
                    if edited_row['Responsavel'] != original_row['Responsavel']:
                        changes['responsavel'] = edited_row['Responsavel']
                    if edited_row['Banco'] != original_row['Banco']:
                        changes['banco'] = edited_row['Banco']
                    if edited_row['Forma Recebimento'] != original_row['Forma Recebimento']:
                        changes['forma_recebimento'] = edited_row['Forma Recebimento']
                    if edited_row['Recorrente'] != original_row['Recorrente']:
                        changes['recorrente'] = edited_row['Recorrente']
                    
                    if edited_row['Data'].strftime("%Y-%m-%d") != original_row['Data'].strftime("%Y-%m-%d"):
                        changes['data'] = edited_row['Data'].strftime("%Y-%m-%d")

                    if changes:
                        if update_transaction(edited_row['ID'], current_username, **changes): # Chamada para a função global
                            rows_updated += 1
                
                if rows_updated > 0:
                    st.success(f"{rows_updated} transação(ões) atualizada(s) com sucesso! 🎉")
                    st.rerun()
                else:
                    st.info("Nenhuma alteração detectada para salvar.")
        
        with col_delete:
            st.warning("Para deletar, selecione o ID da transação.")
            trans_to_delete = st.selectbox("Selecione o ID da transação para excluir", options=edited_df['ID'].tolist(), key="delete_id_select")
            if st.button("Excluir Transação Selecionada", use_container_width=True):
                if delete_transaction(trans_to_delete, current_username): # Chamada para a função global
                    st.success(f"Transação ID {trans_to_delete} excluída com sucesso.")
                    st.rerun()
                else:
                    st.error("Erro ao excluir transação ou ID não encontrado.")
    else:
        st.info("Nenhuma transação correspondente aos filtros.")

def render_detailed_analysis_section(df_all_transactions):
    """Renderiza a seção de análises detalhadas com gráficos."""
    st.header("📈 Análises Detalhadas")

    if df_all_transactions.empty:
        st.info("Nenhuma transação para analisar ainda.")
        return

    st.markdown("---")
    st.subheader("Análise de Gastos por Categoria (Despesas Pagas)")
    despesas_pagas_df = df_all_transactions[(df_all_transactions['Tipo'] == 'despesa') & (df_all_transactions['Status'] == 'Pago')].copy()

    if not despesas_pagas_df.empty:
        gastos_por_categoria = despesas_pagas_df.groupby('Categoria')['Valor'].sum().sort_values(ascending=False)
        st.dataframe(gastos_por_categoria.reset_index().style.format({'Valor': "R$ {:,.2f}"}), use_container_width=True, hide_index=True)

        fig_pie = px.pie(gastos_por_categoria.reset_index(),
                         values='Valor',
                         names='Categoria',
                         title='Distribuição de Despesas Pagas por Categoria',
                         hole=0.3)
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("Nenhuma despesa paga para análise por categoria.")

    st.markdown("---")
    st.subheader("Receitas por Responsável e Banco")
    receitas_df = df_all_transactions[df_all_transactions['Tipo'] == 'receita'].copy()

    if not receitas_df.empty:
        col_resp_chart, col_bank_chart = st.columns(2)
        with col_resp_chart:
            receitas_por_responsavel = receitas_df.groupby('Responsavel')['Valor'].sum().sort_values(ascending=False)
            if not receitas_por_responsavel.empty:
                st.subheader("Receitas por Responsável")
                st.dataframe(receitas_por_responsavel.reset_index().style.format({'Valor': "R$ {:,.2f}"}), use_container_width=True, hide_index=True)
                fig_resp = px.bar(receitas_por_responsavel.reset_index(), x='Responsavel', y='Valor',
                                  title='Total de Receitas por Responsável',
                                  labels={'Responsavel': 'Responsável', 'Valor': 'Valor (R$)'},
                                  color='Responsavel')
                st.plotly_chart(fig_resp, use_container_width=True)
            else:
                st.info("Nenhuma receita registrada por responsável para análise.")

        with col_bank_chart:
            receitas_por_banco = receitas_df.groupby('Banco')['Valor'].sum().sort_values(ascending=False)
            if not receitas_por_banco.empty:
                st.subheader("Receitas por Banco")
                st.dataframe(receitas_por_banco.reset_index().style.format({'Valor': "R$ {:,.2f}"}), use_container_width=True, hide_index=True)
                fig_bank = px.bar(receitas_por_banco.reset_index(), x='Banco', y='Valor',
                                  title='Total de Receitas por Banco',
                                  labels={'Banco': 'Banco', 'Valor': 'Valor (R$)'},
                                  color='Banco')
                st.plotly_chart(fig_bank, use_container_width=True)
            else:
                st.info("Nenhuma receita registrada por banco para análise.")
    else:
        st.info("Nenhuma receita para analisar ainda.")

    st.markdown("---")
    st.subheader("Projeção de Fluxo de Caixa Futuro (Próximos 3 Meses)")
    # Inclui o mês atual + 3 futuros
    future_months = [datetime.now().date() + pd.DateOffset(months=i) for i in range(4)] 
    
    projection_data = {}
    for month_date in future_months:
        month_key = month_date.strftime("%Y-%m")
        projection_data[month_key] = {'Receitas': 0.0, 'Despesas': 0.0, 'Saldo': 0.0}

    current_date = datetime.now().date()

    for index, row in df_all_transactions.iterrows():
        trans_date = row['Data'].date()
        trans_month_key = trans_date.strftime("%Y-%m")

        if row['Tipo'] == 'receita':
            # Adiciona receita ao mês da transação
            if trans_month_key in projection_data:
                projection_data[trans_month_key]['Receitas'] += row['Valor']
            
            # Se for parcelada, adiciona às datas futuras
            if row['Forma Recebimento'] not in ["Parcela Única", "Mais de 6x"] and row['Datas Parcelas Receita']:
                parcel_dates = json.loads(row['Datas Parcelas Receita'])
                for p_date_str in parcel_dates:
                    p_date = datetime.strptime(p_date_str, "%Y-%m-%d").date()
                    p_month_key = p_date.strftime("%Y-%m")
                    # Se a parcela for para um mês futuro e estiver no nosso range de projeção
                    if p_month_key in projection_data and p_date > current_date:
                        # Divide o valor total pela quantidade de parcelas para cada ocorrência
                        projection_data[p_month_key]['Receitas'] += row['Valor'] / len(parcel_dates) 
                        
        elif row['Tipo'] == 'despesa':
            # Adiciona despesa ao mês da transação (seja 'A Pagar' ou 'Pago')
            # Apenas despesas com status 'A Pagar' ou despesas 'Pago' do mês atual/futuro são relevantes para projeção futura.
            # As despesas 'Pago' passadas já impactaram o saldo real e não a projeção futura.
            
            if row['Status'] == 'A Pagar' and trans_month_key in projection_data:
                projection_data[trans_month_key]['Despesas'] += row['Valor']
            elif row['Status'] == 'Pago' and trans_date >= datetime.now().date().replace(day=1) and trans_month_key in projection_data:
                # Inclui despesas pagas do mês corrente para frente na projeção
                projection_data[trans_month_key]['Despesas'] += row['Valor']
            
            # Se for recorrente, projeta para os próximos meses
            # Cuidado para não duplicar se já foi adicionado como 'A Pagar' acima
            if row['Recorrente'] == 'Sim' and row['Vezes Recorrencia'] > 1:
                # Itera a partir da segunda ocorrência
                for i in range(1, row['Vezes Recorrencia']): 
                    future_date = trans_date + pd.DateOffset(months=i).date()
                    future_month_key = future_date.strftime("%Y-%m")
                    # Só adiciona se estiver no range de projeção e a data for futura
                    if future_month_key in projection_data and future_date > current_date:
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
                      barmode='group',
                      color_discrete_map={'Receitas': 'green', 'Despesas': 'red', 'Saldo': 'blue'})
    st.plotly_chart(fig_proj, use_container_width=True)

def render_planning_section():
    """Esboço da seção de Planejamento."""
    st.header("🎯 Planejamento Financeiro")
    st.info("Esta seção ainda está em desenvolvimento. Aqui você poderá definir orçamentos, metas e projeções mais complexas.")
    st.write("Em breve: Orçamentos por categoria, metas de economia, acompanhamento de dívidas e investimentos.")
    st.markdown("---")
    st.subheader("Definir Orçamento por Categoria")
    with st.expander("Definir Novo Orçamento"):
        col_cat_budget, col_val_budget = st.columns(2)
        with col_cat_budget:
            categoria_orcamento = st.selectbox("Categoria", ["Alimentação", "Transporte", "Moradia", "Lazer", "Educação", "Saúde", "Contas Fixas", "Compras", "Outros"])
        with col_val_budget:
            valor_orcamento = st.number_input("Valor do Orçamento Mensal (R$)", min_value=0.0, format="%.2f")
        if st.button("Salvar Orçamento"):
            st.success(f"Orçamento de R$ {valor_orcamento:,.2f} definido para {categoria_orcamento}.")
            # Lógica para salvar isso em um DB ou session_state
    
    st.subheader("Metas de Economia")
    with st.expander("Definir Nova Meta"):
        meta_descricao = st.text_input("Descrição da Meta")
        meta_valor = st.number_input("Valor da Meta (R$)", min_value=0.0, format="%.2f")
        meta_data_limite = st.date_input("Data Limite para Atingir a Meta", datetime.now().date() + timedelta(days=365))
        if st.button("Salvar Meta"):
            st.success(f"Meta '{meta_descricao}' de R$ {meta_valor:,.2f} definida até {meta_data_limite.strftime('%d/%m/%Y')}.")
            # Lógica para salvar isso em um DB ou session_state


# --- Inicialização dos Bancos de Dados ---
init_user_db()
init_transactions_db()

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

        if st.button("Entrar", key="login_button", use_container_width=True):
            if verify_user(username, password): # Chamada para a função global
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

        if st.button("Registrar Nova Conta", key="register_button", use_container_width=True):
            if not new_username or not new_password or not confirm_password:
                st.warning("Por favor, preencha todos os campos.")
            elif new_password != confirm_password:
                st.warning("As senhas não coincidem.")
            elif add_user(new_username, new_password): # Chamada para a função global
                st.success("Conta criada com sucesso! Faça login na coluna ao lado.")
                st.balloons()
            else:
                st.warning("Nome de usuário já existe. Escolha outro.")

# --- Lógica Principal da Aplicação ---
if st.session_state['logged_in']:
    st.sidebar.title(f"Olá, {st.session_state['username']}!")
    
    # Menu lateral para as funcionalidades (substituindo as abas superiores)
    app_menu = ["📊 Visão Geral", "📝 Transações", "➕ Adicionar Lançamento", "📈 Análises Detalhadas", "🎯 Planejamento"]
    selected_option = st.sidebar.radio("Navegação", app_menu)

    current_username = st.session_state['username']
    all_transactions_data = get_transactions(current_username) # Carrega todas as transações uma vez
    
    # Converte para DataFrame aqui para ser usado por todas as seções
    if all_transactions_data:
        df_all_transactions = pd.DataFrame(all_transactions_data, columns=[
            'ID', 'Data', 'Descrição', 'Valor', 'Tipo', 'Categoria', 'Responsavel', 'Banco',
            'Forma Recebimento', 'Datas Parcelas Receita', 'Recorrente', 'Vezes Recorrencia', 'Status'
        ])
        df_all_transactions['Data'] = pd.to_datetime(df_all_transactions['Data'])
    else:
        df_all_transactions = pd.DataFrame(columns=[
            'ID', 'Data', 'Descrição', 'Valor', 'Tipo', 'Categoria', 'Responsavel', 'Banco',
            'Forma Recebimento', 'Datas Parcelas Receita', 'Recorrente', 'Vezes Recorrencia', 'Status'
        ])

    # Renderiza a seção selecionada
    if selected_option == "📊 Visão Geral":
        render_overview_dashboard(current_username, df_all_transactions)
    elif selected_option == "📝 Transações":
        render_transactions_table(current_username, df_all_transactions)
    elif selected_option == "➕ Adicionar Lançamento":
        render_unified_transaction_form(current_username)
    elif selected_option == "📈 Análises Detalhadas":
        render_detailed_analysis_section(df_all_transactions)
    elif selected_option == "🎯 Planejamento":
        render_planning_section()

    st.sidebar.markdown("---")
    if st.sidebar.button("Sair", use_container_width=True):
        st.session_state['logged_in'] = False
        st.session_state['username'] = None
        st.info("Você foi desconectado(a).")
        st.rerun()
else:
    login_page()

st.markdown("---")
st.markdown("Desenvolvido com 💜 e Streamlit para o controle financeiro familiar.")