import streamlit as st
from modules import usinagem, estamparia #, furadeiras (futuro)

print("--- LEITURA DOS SEGREDOS ---")
print(f"HOST LIDO: {st.secrets['postgres']['DB_HOST']}")
print("----------------------------")

# --- CONFIGURAÇÃO DA PÁGINA (SÓ PODE TER AQUI) ---
st.set_page_config(page_title="Sistema Integrado IPAR", layout="wide", page_icon="🏭")

# --- SISTEMA DE LOGIN SIMPLES ---
# Dicionário de Usuários: "usuario": ["senha", "setor"]
USUARIOS = {
    "lider_usinagem": ["usi123", "USINAGEM"],
    "lider_estamparia": ["est123", "ESTAMPARIA"],
    "admin": ["admin", "ADMIN"], # Vê tudo
    "lider_furadeira": ["fur123", "FURADEIRAS"]
}

def check_login(user, password):
    """Verifica se usuário e senha batem"""
    if user in USUARIOS:
        if USUARIOS[user][0] == password:
            return USUARIOS[user][1] # Retorna o setor
    return None

# --- INTERFACE DE LOGIN ---
if "logado" not in st.session_state:
    st.session_state["logado"] = False
    st.session_state["setor"] = None

if not st.session_state["logado"]:
    st.title("🔒 Portal IPAR - Acesso Restrito")
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        with st.form("login_form"):
            st.markdown("### Identificação")
            user = st.text_input("Usuário")
            password = st.text_input("Senha", type="password")
            submit = st.form_submit_button("Entrar no Sistema")
            
            if submit:
                setor = check_login(user, password)
                if setor:
                    st.session_state["logado"] = True
                    st.session_state["setor"] = setor
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")

# --- REDIRECIONAMENTO POR SETOR ---
else:
    # Botão de Sair no topo lateral
    with st.sidebar:
        st.write(f"👤 Logado como: **{st.session_state['setor']}**")
        if st.button("Sair / Logout"):
            st.session_state["logado"] = False
            st.session_state["setor"] = None
            st.rerun()
        st.divider()

    # Lógica de Roteamento (Router)
    setor = st.session_state["setor"]

    if setor == "USINAGEM":
        usinagem.render_app()
    
    elif setor == "ESTAMPARIA":
        estamparia.render_app()
    
    elif setor == "FURADEIRAS":
        st.title("🚧 Setor de Furadeiras em Construção")
    
    elif setor == "ADMIN":
        st.title("Painel Geral")
        opcao = st.selectbox("Qual setor deseja visualizar?", ["USINAGEM", "ESTAMPARIA"])
        if opcao == "USINAGEM":
            usinagem.render_app()
        elif opcao == "ESTAMPARIA":
            estamparia.render_app()
