import streamlit as st
import os

st.title("🕵️ Detetive de Segredos")

# 1. Mostra onde o Python está rodando
st.write(f"📂 **Pasta Atual:** `{os.getcwd()}`")

# 2. Verifica se a pasta .streamlit existe
caminho_pasta = os.path.join(os.getcwd(), ".streamlit")
if os.path.exists(caminho_pasta):
    st.success("✅ Pasta .streamlit encontrada!")
else:
    st.error(f"❌ Pasta .streamlit NÃO encontrada em: {caminho_pasta}")

# 3. Verifica se o arquivo secrets.toml existe
caminho_arquivo = os.path.join(caminho_pasta, "secrets.toml")
if os.path.exists(caminho_arquivo):
    st.success("✅ Arquivo secrets.toml encontrado!")
else:
    st.error(f"❌ Arquivo secrets.toml NÃO encontrado. Verifique se não está como secrets.toml.txt")

# 4. Tenta ler os segredos
try:
    # Tenta acessar a chave
    dados = st.secrets["postgres"]
    st.success("🎉 SUCESSO! O Streamlit leu a chave [postgres].")
    st.json(dados) # Mostra os dados (cuidado, vai mostrar a senha na tela)
except Exception as e:
    st.error(f"💀 O Streamlit não conseguiu ler. Erro: {e}")
    st.write("Conteúdo bruto dos segredos encontrados:", st.secrets)