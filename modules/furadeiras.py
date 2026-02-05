import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
from datetime import datetime, date, time, timedelta
import io

# ==============================================================================
# 1. CONEXÃO E BANCO DE DADOS (COM CACHE DE PERFORMANCE)
# ==============================================================================

@st.cache_resource(ttl=3600)
def init_connection():
    try:
        return psycopg2.connect(
            host=st.secrets["postgres"]["DB_HOST"],
            user=st.secrets["postgres"]["DB_USER"],
            password=st.secrets["postgres"]["DB_PASS"],
            dbname=st.secrets["postgres"]["DB_NAME"],
            port=st.secrets["postgres"]["DB_PORT"],
            sslmode='require'
        )
    except Exception as e:
        st.error(f"Erro Conexão: {e}")
        return None

def run_query(query, params=(), fetch=False, commit=False):
    conn = init_connection()
    if not conn: return None
    try:
        # Usamos 'with' para garantir que o cursor feche, mas a conexão fica aberta
        with conn.cursor() as cur:
            cur.execute(query, params)
            res = None
            if commit: 
                conn.commit()
                res = "OK"
            if fetch: 
                res = cur.fetchall()
        return res
    except Exception as e:
        st.error(f"Erro SQL: {e}")
        conn.rollback()
        return None

def get_dataframe(query, params=None):
    conn = init_connection()
    if not conn: return pd.DataFrame()
    try:
        df = pd.read_sql(query, conn, params=params)
        return df
    except Exception: 
        return pd.DataFrame()

# ... (O resto do código init_db_furadeira, render_app, etc., continua igual)

def init_db_furadeira():
    queries = [
        "CREATE TABLE IF NOT EXISTS furadeira_operadores (id SERIAL PRIMARY KEY, nome TEXT, ativo INTEGER DEFAULT 1);",
        "CREATE TABLE IF NOT EXISTS furadeira_motivos_parada (id SERIAL PRIMARY KEY, motivo TEXT, ativo INTEGER DEFAULT 1);",
        """CREATE TABLE IF NOT EXISTS furadeira_apontamentos (
            id SERIAL PRIMARY KEY, data_registro DATE, operador TEXT, cliente TEXT, peca TEXT, 
            tipo_operacao TEXT, tempo_ciclo_seg REAL, inicio_prod TIME, fim_prod TIME, 
            qtd_produzida INTEGER, refugo INTEGER, eficiencia_calc REAL, observacao TEXT, 
            ativo INTEGER DEFAULT 1, criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );""",
        "CREATE TABLE IF NOT EXISTS furadeira_paradas_reg (id SERIAL PRIMARY KEY, data_registro DATE, motivo TEXT, inicio TIME, fim TIME, observacao TEXT, ativo INTEGER DEFAULT 1);"
    ]
    for q in queries: run_query(q, commit=True)
    
    # Inserir motivos padrão se vazio
    if run_query("SELECT count(*) FROM furadeira_motivos_parada", fetch=True)[0][0] == 0:
        padroes = ["Afiação de Broca", "Quebra de Ferramenta", "Setup/Preparação", "Aguardando Material", "Manutenção", "Limpeza/5S", "Refeição"]
        for p in padroes: run_query("INSERT INTO furadeira_motivos_parada (motivo, ativo) VALUES (%s, 1)", (p,), commit=True)

# ==============================================================================
# 2. APP PRINCIPAL DA FURADEIRA
# ==============================================================================
def render_app():
    init_db_furadeira()
    
    st.sidebar.divider()
    # Menu Interno da Furadeira
    menu_fura = st.sidebar.radio("Menu Furadeira", [
        "📝 Apontamento Diário",
        "📊 Dashboard & KPIs",
        "🛑 Registro de Paradas",
        "🔐 Cadastros & Admin" # Tem cadeado no nome pra indicar senha
    ])

    # --------------------------------------------------------------------------
    # 1. APONTAMENTO
    # --------------------------------------------------------------------------
    if menu_fura == "📝 Apontamento Diário":
        st.header("📝 Apontamento de Produção")
        
        ops = [r[0] for r in run_query("SELECT nome FROM furadeira_operadores WHERE ativo=1 ORDER BY nome", fetch=True)]
        if not ops: st.warning("Cadastre operadores na aba Admin primeiro.")
        
        with st.form("form_fura"):
            c1, c2, c3 = st.columns(3)
            dt = c1.date_input("Data", date.today())
            op = c2.selectbox("Operador", ops) if ops else c2.text_input("Operador")
            tipo = c3.selectbox("Operação", ["Furadeira (F)", "Escareador (E)", "Rosqueadeira (R)", "Rebarba (RB)"])
            
            c4, c5 = st.columns(2)
            cli = c4.text_input("Cliente")
            peca = c5.text_input("Peça")
            
            st.markdown("---")
            k1, k2, k3 = st.columns(3)
            hi = k1.time_input("Início", time(7,0))
            hf = k2.time_input("Fim", time(17,0))
            ciclo = k3.number_input("Ciclo (seg)", value=30.0, step=1.0)
            
            k4, k5 = st.columns(2)
            qtd = k4.number_input("Produzido (Boas)", min_value=0)
            ref = k5.number_input("Refugo", min_value=0)
            obs = st.text_area("Obs")
            
            if st.form_submit_button("Salvar Produção"):
                dti = datetime.combine(dt, hi)
                dtf = datetime.combine(dt, hf)
                if hf < hi: dtf += timedelta(days=1)
                h_trab = (dtf - dti).total_seconds() / 3600
                
                # Cálculo Eficiência
                efic = 0
                if h_trab > 0:
                    prod_teorica = (h_trab * 3600) / ciclo if ciclo > 0 else 0
                    efic = ((qtd + ref) / prod_teorica * 100) if prod_teorica > 0 else 0
                
                sigla = {"Furadeira (F)":"F", "Escareador (E)":"E", "Rosqueadeira (R)":"R", "Rebarba (RB)":"RB"}.get(tipo, "F")
                
                run_query("""INSERT INTO furadeira_apontamentos 
                    (data_registro, operador, cliente, peca, tipo_operacao, tempo_ciclo_seg, inicio_prod, fim_prod, qtd_produzida, refugo, eficiencia_calc, observacao, ativo)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)""",
                    (dt, op, cli.upper(), peca.upper(), sigla, ciclo, hi, hf, qtd, ref, efic, obs), commit=True)
                st.success(f"Salvo! Eficiência: {efic:.1f}%")
                st.rerun()

    # --------------------------------------------------------------------------
    # 2. DASHBOARD & KPIS (NOVO!)
    # --------------------------------------------------------------------------
    elif menu_fura == "📊 Dashboard & KPIs":
        st.header("📊 Indicadores de Desempenho")
        filtro_data = st.date_input("Filtrar Data", date.today())
        
        # Dados do dia
        df = get_dataframe(f"SELECT * FROM furadeira_apontamentos WHERE ativo=1 AND data_registro='{filtro_data}'")
        
        # KPI Cards
        total_pcs = df['qtd_produzida'].sum() if not df.empty else 0
        total_ref = df['refugo'].sum() if not df.empty else 0
        media_efic = df['eficiencia_calc'].mean() if not df.empty else 0
        
        k1, k2, k3 = st.columns(3)
        k1.metric("Peças Produzidas", f"{total_pcs}")
        k2.metric("Refugo Total", f"{total_ref}", delta=f"{(total_ref/(total_pcs+total_ref)*100 if total_pcs>0 else 0):.1f}% Taxa", delta_color="inverse")
        k3.metric("Eficiência Média", f"{media_efic:.1f}%")
        
        st.divider()
        
        # Gráficos
        c1, c2 = st.columns(2)
        
        with c1:
            if not df.empty:
                st.subheader("Eficiência por Operador")
                # Gráfico de Barras Colorido pela Eficiência
                fig_bar = px.bar(df, x='operador', y='eficiencia_calc', color='cliente', title="Eficiência % por Registro", text_auto='.1f')
                fig_bar.add_hline(y=90, line_dash="dot", annotation_text="Meta 90%", annotation_position="bottom right")
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.info("Sem produção nesta data.")
                
        with c2:
            st.subheader("Motivos de Parada (Pareto)")
            df_par = get_dataframe(f"SELECT * FROM furadeira_paradas_reg WHERE ativo=1 AND data_registro='{filtro_data}'")
            if not df_par.empty:
                # Converter para minutos
                df_par['minutos'] = df_par.apply(lambda x: (datetime.combine(date.min, x['fim']) - datetime.combine(date.min, x['inicio'])).seconds / 60, axis=1)
                fig_pie = px.pie(df_par, values='minutos', names='motivo', title='Distribuição de Tempo Parado')
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("Nenhuma parada registrada hoje.")

    # --------------------------------------------------------------------------
    # 3. PARADAS
    # --------------------------------------------------------------------------
    elif menu_fura == "🛑 Registro de Paradas":
        st.header("🛑 Registrar Parada")
        mots = [r[0] for r in run_query("SELECT motivo FROM furadeira_motivos_parada WHERE ativo=1 ORDER BY motivo", fetch=True)]
        
        with st.form("form_p"):
            c1, c2 = st.columns(2)
            mot = c1.selectbox("Motivo", mots) if mots else c1.text_input("Motivo")
            obs = c2.text_input("Obs")
            c3, c4 = st.columns(2)
            ini = c3.time_input("Início", time(10,0))
            fim = c4.time_input("Fim", time(10,15))
            
            if st.form_submit_button("Salvar Parada"):
                run_query("INSERT INTO furadeira_paradas_reg (data_registro, motivo, inicio, fim, observacao, ativo) VALUES (%s,%s,%s,%s,%s,1)",
                          (date.today(), mot, ini, fim, obs), commit=True)
                st.success("Registrado!")
                st.rerun()

    # --------------------------------------------------------------------------
    # 4. CADASTROS & ADMIN (COM SENHA!)
    # --------------------------------------------------------------------------
    elif menu_fura == "🔐 Cadastros & Admin":
        st.header("🔒 Área Restrita - Supervisão")
        
        # --- BLOQUEIO DE SENHA ---
        senha = st.text_input("Digite a senha de supervisor", type="password")
        if senha != "1234":
            st.warning("🔒 Digite a senha correta para acessar Cadastros, Histórico e Exportação.")
            return # Para o código aqui se a senha estiver errada
        
        # --- SE PASSOU DA SENHA, MOSTRA TUDO: ---
        st.success("Acesso Permitido")
        tab1, tab2, tab3 = st.tabs(["👥 Operadores", "🛑 Motivos Parada", "📤 Exportar Excel"])
        
        # Editor Genérico
        def admin_editor(tabela, col_nome, key):
            df = get_dataframe(f"SELECT id, {col_nome}, ativo FROM {tabela} WHERE ativo=1 ORDER BY {col_nome}")
            edit = st.data_editor(df, column_config={"id":None, "ativo":None, col_nome: st.column_config.TextColumn("Nome", required=True)}, num_rows="dynamic", key=key)
            if st.button(f"Salvar {key}"):
                for i, row in edit.iterrows():
                    if row[col_nome]:
                        if pd.notna(row['id']): run_query(f"UPDATE {tabela} SET {col_nome}=%s WHERE id=%s", (str(row[col_nome]).upper(), int(row['id'])), commit=True)
                        else: run_query(f"INSERT INTO {tabela} ({col_nome}, ativo) VALUES (%s,1)", (str(row[col_nome]).upper(),), commit=True)
                st.success("Salvo!"); st.rerun()
        
        with tab1: admin_editor("furadeira_operadores", "nome", "ed_ops")
        with tab2: admin_editor("furadeira_motivos_parada", "motivo", "ed_mots")
        with tab3:
            st.subheader("Histórico Completo")
            df_full = get_dataframe("SELECT * FROM furadeira_apontamentos WHERE ativo=1 ORDER BY id DESC")
            st.dataframe(df_full, use_container_width=True)
            
            # Botão de Download
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_full.to_excel(writer, sheet_name='Producao', index=False)
                get_dataframe("SELECT * FROM furadeira_paradas_reg WHERE ativo=1").to_excel(writer, sheet_name='Paradas', index=False)
            
            st.download_button("📥 Baixar Planilha Completa", buffer.getvalue(), "relatorio_furadeira.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
