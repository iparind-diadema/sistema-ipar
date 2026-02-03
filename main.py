import streamlit as st
import modules.usinagem as usinagem
import modules.estamparia as estamparia
import modules.furadeiras as furadeiras  # <--- MÓDULO NOVO

# Configuração da Página (Sempre a primeira linha)
st.set_page_config(page_title="Portal IPAR", page_icon="🏭", layout="wide")

# --- SISTEMA DE LOGIN SIMPLES ---
USUARIOS = {
    "lider_usinagem": "usi123",
    "lider_estamparia": "est123",
    "lider_furadeira": "fur123",  # <--- LOGIN NOVO
    "admin": "admin123"
}

def check_login(user, password):
    return USUARIOS.get(user) == password

def login_screen():
    st.markdown("<h1 style='text-align: center;'>🏭 Portal Industrial IPAR</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center;'>Acesso Restrito aos Líderes</h3>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            user = st.text_input("Usuário")
            password = st.text_input("Senha", type="password")
            submit = st.form_submit_button("Entrar no Sistema")
            
            if submit:
                if check_login(user, password):
                    st.session_state['usuario'] = user
                    st.session_state['logado'] = True
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")

def main():
    if 'logado' not in st.session_state:
        st.session_state['logado'] = False

    if not st.session_state['logado']:
        login_screen()
    else:
        # --- ÁREA LOGADA ---
        st.sidebar.markdown(f"👤 Olá, **{st.session_state['usuario']}**")
        
        if st.sidebar.button("Sair / Logout"):
            st.session_state['logado'] = False
            st.rerun()

        st.sidebar.title("Navegação")
        # Define qual módulo abrir com base na escolha ou permissão
        # Aqui deixamos livre para todos verem todos, ou você pode restringir por 'if'
        
        menu_principal = st.sidebar.radio(
            "Selecione o Setor:",
            ["Usinagem (CNC)", "Estamparia (Prensas)", "Furadeiras / Acabamento"]
        )

        if menu_principal == "Usinagem (CNC)":
            usinagem.render_app()
            
        elif menu_principal == "Estamparia (Prensas)":
            estamparia.render_app()
            
        elif menu_principal == "Furadeiras / Acabamento":
            furadeiras.render_app()  # <--- CHAMA A TELA NOVA

# Execução
if __name__ == "__main__":
    main()
