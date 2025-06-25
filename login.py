import streamlit as st
import hashlib

# --- Funções de Ajuda ---
def make_hashes(password):
    """Cria um hash SHA256 da senha."""
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    """Verifica se a senha fornecida corresponde ao hash."""
    return make_hashes(password) == hashed_text

# --- Banco de Dados de Usuários (simulado) ---
# Em um aplicativo real, você usaria um banco de dados como SQLite, PostgreSQL, etc.
# Para este exemplo, vamos usar um dicionário simples.
users_db = {}

# --- Configurações da Página ---
st.set_page_config(
    page_title="Sistema de Login",
    page_icon="🔑",
    layout="centered"
)

# --- Título Principal ---
st.title("🔑 Sistema de Login e Registro")

# --- Escolha entre Login e Registro ---
menu = ["Login", "Registrar"]
choice = st.sidebar.selectbox("Menu", menu)

# --- Seção de Login ---
if choice == "Login":
    st.subheader("Fazer Login")

    username = st.text_input("Nome de Usuário")
    password = st.text_input("Senha", type='password')

    if st.button("Login"):
        # Em um sistema real, você buscaria o hash do usuário no banco de dados
        # e compararia. Aqui, estamos simulando com o dicionário users_db.
        if username in users_db:
            hashed_password = users_db[username]
            if check_hashes(password, hashed_password):
                st.success(f"Bem-vindo(a), {username}! 🎉")
                st.balloons() # Balões de sucesso
                # Aqui você poderia redirecionar para a página principal do aplicativo
            else:
                st.error("Nome de usuário ou senha incorretos.")
        else:
            st.error("Nome de usuário ou senha incorretos.")

# --- Seção de Registro ---
elif choice == "Registrar":
    st.subheader("Criar Nova Conta")

    new_username = st.text_input("Nome de Usuário")
    new_password = st.text_input("Senha", type='password')
    confirm_password = st.text_input("Confirme a Senha", type='password')

    if st.button("Registrar"):
        if not new_username or not new_password or not confirm_password:
            st.warning("Por favor, preencha todos os campos.")
        elif new_password != confirm_password:
            st.warning("As senhas não coincidem.")
        elif new_username in users_db:
            st.warning("Nome de usuário já existe. Escolha outro.")
        else:
            hashed_new_password = make_hashes(new_password)
            users_db[new_username] = hashed_new_password
            st.success("Sua conta foi criada com sucesso! Você já pode fazer login.")
            st.balloons() # Balões de sucesso no registro

# --- Rodapé ---
st.markdown("---")
st.markdown("Desenvolvido com ❤️ e Streamlit")