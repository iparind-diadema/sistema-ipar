import streamlit as st
import modules.usinagem as usinagem
import modules.estamparia as estamparia
import modules.furadeiras as furadeiras

# Configuração da Página
st.set_page_config(page_title="Portal IPAR", page_icon="🏭", layout="wide")

# --- 1. CREDENCIAIS E PERMISSÕES ---
USUARIOS = {
    "lider_usinagem": "usi123",
    "lider_estamparia": "est123",
    "lider_furadeira": "fur123",
    "admin": "admin123"
}

# Define quais módulos cada usuário pode ver
PERMISSOES = {
    "lider_usinagem": ["Usinagem (CNC)"],
    "lider_estamparia": ["Estamparia (Prensas)"],
    "lider_furadeira": ["Furadeiras / Acabamento"],
    "admin": ["Usinagem (CNC)", "Estamparia (Prensas)", "Furadeiras / Acabamento"] # Admin vê tudo
}

def check_login(user, password):
    return USUARIOS.get(user) == password

def login_screen():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>🏭 Portal Industrial IPAR</h1>", unsafe_allow_html=True)
        with st.form("login_form"):
            user = st.text_input("Usuário")
            password = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
                if check_login(user, password):
                    st.session_state['usuario'] = user
                    st.session_state['logado'] = True
                    st.rerun()
                else:
                    st.error("Acesso Negado.")

def main():
    if 'logado' not in st.session_state: st.session_state['logado'] = False

    if not st.session_state['logado']:
        login_screen()
    else:
        # --- ÁREA LOGADA ---
        usuario_atual = st.session_state['usuario']
        st.sidebar.markdown(f"👤 **{usuario_atual.upper()}**")
        
        if st.sidebar.button("Sair"):
            st.session_state['logado'] = False
            st.rerun()

        st.sidebar.divider()
        st.sidebar.title("Navegação")
        
        # Filtra o menu baseado no usuário
        opcoes_validas = PERMISSOES.get(usuario_atual, [])
        if not opcoes_validas:
            st.error("Seu usuário não tem permissão configurada.")
            return

        # Se tiver mais de uma opção, mostra o menu. Se só tiver uma, seleciona automático.
        if len(opcoes_validas) > 1:
            menu = st.sidebar.radio("Selecione o Setor:", opcoes_validas)
        else:
            menu = opcoes_validas[0] # Seleciona o único disponível
            st.sidebar.markdown(f"📍 **{menu}**")

        # Roteador de Módulos
        if menu == "Usinagem (CNC)":
            usinagem.render_app()
        elif menu == "Estamparia (Prensas)":
            estamparia.render_app()
        elif menu == "Furadeiras / Acabamento":
            furadeiras.render_app()

if __name__ == "__main__":
    main()
