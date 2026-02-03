import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
from datetime import datetime, date, time, timedelta
import io

# ==============================================================================
# 1. FUNÇÕES DE BANCO DE DADOS (PADRÃO SEGURO)
# ==============================================================================

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
        st.error(f"Erro de Conexão: {e}")
        return None

def run_query(query, params=(), fetch=False, commit=False):
    conn = init_connection()
    if not conn: return None
    result = None
    try:
        cur = conn.cursor()
        cur.execute(query, params)
        if commit:
            conn.commit()
            result = "OK"
        if fetch:
            result = cur.fetchall()
        cur.close()
        conn.close()
        return result
    except Exception as e:
        st.error(f"Erro SQL: {e}")
        if conn: conn.rollback()
        return None

def get_dataframe(query, params=None):
    conn = init_connection()
    if not conn: return pd.DataFrame()
    try:
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Erro ao gerar tabela: {e}")
        return pd.DataFrame()

# ==============================================================================
# 2. CONFIGURAÇÃO INICIAL (CRIA TABELAS SE NÃO EXISTIREM)
# ==============================================================================
def init_db_furadeira():
    # Cria tabelas específicas da Furadeira se não existirem
    queries = [
        """CREATE TABLE IF NOT EXISTS furadeira_operadores (
            id SERIAL PRIMARY KEY, nome TEXT, ativo INTEGER DEFAULT 1
        );""",
        """CREATE TABLE IF NOT EXISTS furadeira_motivos_parada (
            id SERIAL PRIMARY KEY, motivo TEXT, ativo INTEGER DEFAULT 1
        );""",
        """CREATE TABLE IF NOT EXISTS furadeira_apontamentos (
            id SERIAL PRIMARY KEY,
            data_registro DATE,
            operador TEXT,
            cliente TEXT,
            peca TEXT,
            tipo_operacao TEXT,
            tempo_ciclo_seg REAL,
            inicio_prod TIME,
            fim_prod TIME,
            qtd_produzida INTEGER,
            refugo INTEGER,
            eficiencia_calc REAL,
            observacao TEXT,
            ativo INTEGER DEFAULT 1,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );""",
        """CREATE TABLE IF NOT EXISTS furadeira_paradas_reg (
            id SERIAL PRIMARY KEY,
            data_registro DATE,
            motivo TEXT,
            inicio TIME,
            fim TIME,
            observacao TEXT,
            ativo INTEGER DEFAULT 1
        );"""
    ]
    for q in queries:
        run_query(q, commit=True)

# ==============================================================================
# 3. APLICAÇÃO PRINCIPAL
# ==============================================================================
def render_app():
    # Garante que as tabelas existem
    init_db_furadeira()
    
    st.sidebar.divider()
    st.sidebar.title("🔩 Setor Furadeira")
    
    menu = st.sidebar.radio("Navegação", [
        "📝 Apontamento Diário",
        "🛑 Registro de Paradas",
        "⚙️ Cadastros & Dados"
    ])

    # ==========================================================================
    # ABA 1: APONTAMENTO DIÁRIO
    # ==========================================================================
    if menu == "📝 Apontamento Diário":
        st.header("📝 Apontamento de Produção")
        
        # Carregar Operadores
        ops = run_query("SELECT nome FROM furadeira_operadores WHERE ativo = 1 ORDER BY nome", fetch=True)
        lista_ops = [o[0] for o in ops] if ops else []
        
        if not lista_ops:
            st.warning("⚠️ Cadastre Operadores na aba 'Cadastros' primeiro.")
        
        with st.form("form_furadeira", clear_on_submit=False):
            st.subheader("1. Dados Gerais")
            c1, c2, c3 = st.columns(3)
            data_reg = c1.date_input("Data", date.today())
            operador = c2.selectbox("Operador", lista_ops) if lista_ops else c2.text_input("Operador (Temp)")
            tipo_op = c3.selectbox("Tipo de Operação", ["Furadeira (F)", "Escareador (E)", "Rosqueadeira (R)", "Rebarba (RB)"])
            
            c4, c5 = st.columns(2)
            cliente = c4.text_input("Cliente")
            peca = c5.text_input("Descrição da Peça")
            
            st.divider()
            st.subheader("2. Tempos e Quantidades")
            
            col_t1, col_t2, col_t3 = st.columns(3)
            h_ini = col_t1.time_input("Hora Início", time(7,0))
            h_fim = col_t2.time_input("Hora Fim", time(17,0))
            ciclo = col_t3.number_input("Tempo de Ciclo (segundos)", min_value=1.0, value=30.0, step=1.0)
            
            col_q1, col_q2 = st.columns(2)
            qtd = col_q1.number_input("Peças Boas", min_value=0)
            refugo = col_q2.number_input("Refugo", min_value=0)
            
            obs = st.text_area("Observações (Opcional)")

            # Cálculo de Prévia de Eficiência (Visual)
            submit = st.form_submit_button("💾 Salvar Produção")
            
            if submit:
                # Validar
                dt_i = datetime.combine(data_reg, h_ini)
                dt_f = datetime.combine(data_reg, h_fim)
                if h_fim < h_ini: dt_f += timedelta(days=1)
                
                horas_trabalhadas = (dt_f - dt_i).total_seconds() / 3600
                tempo_disponivel_seg = horas_trabalhadas * 3600
                
                # Cálculo Eficiência Simplificado
                # Eficiência = (Peças * Ciclo) / Tempo Disponível
                eficiencia = 0
                if tempo_disponivel_seg > 0:
                    tempo_produtivo = (qtd + refugo) * ciclo
                    eficiencia = (tempo_produtivo / tempo_disponivel_seg) * 100
                
                if horas_trabalhadas <= 0:
                    st.error("❌ Horário inválido (Início maior ou igual ao Fim).")
                else:
                    # Mapear Siglas
                    sigla_map = {
                        "Furadeira (F)": "F",
                        "Escareador (E)": "E",
                        "Rosqueadeira (R)": "R",
                        "Rebarba (RB)": "RB"
                    }
                    sigla = sigla_map.get(tipo_op, "F")
                    
                    sql = """
                        INSERT INTO furadeira_apontamentos 
                        (data_registro, operador, cliente, peca, tipo_operacao, tempo_ciclo_seg, inicio_prod, fim_prod, qtd_produzida, refugo, eficiencia_calc, observacao, ativo)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
                    """
                    run_query(sql, (data_reg, operador, cliente.upper(), peca.upper(), sigla, ciclo, h_ini, h_fim, qtd, refugo, eficiencia, obs), commit=True)
                    st.success(f"✅ Produção Salva! Eficiência Calculada: {eficiencia:.1f}%")
                    st.rerun()

    # ==========================================================================
    # ABA 2: PARADAS
    # ==========================================================================
    elif menu == "🛑 Registro de Paradas":
        st.header("🛑 Controle de Paradas")
        
        motivos = run_query("SELECT motivo FROM furadeira_motivos_parada WHERE ativo = 1 ORDER BY motivo", fetch=True)
        lista_motivos = [m[0] for m in motivos] if motivos else []
        
        with st.form("form_parada"):
            c1, c2 = st.columns(2)
            d_p = c1.date_input("Data", date.today())
            mot = c2.selectbox("Motivo", lista_motivos) if lista_motivos else c2.text_input("Motivo (Temp)")
            
            c3, c4 = st.columns(2)
            hi = c3.time_input("Início Parada", time(12,0))
            hf = c4.time_input("Fim Parada", time(13,0))
            
            obs_p = st.text_input("Detalhe (Opcional)")
            
            if st.form_submit_button("Registrar Parada"):
                run_query("""
                    INSERT INTO furadeira_paradas_reg (data_registro, motivo, inicio, fim, observacao, ativo)
                    VALUES (%s, %s, %s, %s, %s, 1)
                """, (d_p, mot, hi, hf, obs_p), commit=True)
                st.success("Parada Registrada!")
                st.rerun()
        
        st.divider()
        st.subheader("Histórico do Dia")
        df_p = get_dataframe(f"SELECT id, motivo, inicio, fim, observacao FROM furadeira_paradas_reg WHERE data_registro = '{date.today()}' AND ativo = 1")
        st.dataframe(df_p, use_container_width=True)

    # ==========================================================================
    # ABA 3: CADASTROS & DADOS
    # ==========================================================================
    elif menu == "⚙️ Cadastros & Dados":
        st.header("⚙️ Gestão de Dados - Furadeira")
        
        tab1, tab2, tab3 = st.tabs(["👥 Operadores", "🛑 Motivos Parada", "📊 Histórico Completo"])
        
        # Função Auxiliar de Edição (A mesma da Usinagem)
        def editor_simples(tabela, col_nome, key_suf):
            df = get_dataframe(f"SELECT id, {col_nome}, ativo FROM {tabela} WHERE ativo = 1 ORDER BY {col_nome}")
            edited = st.data_editor(
                df, 
                column_config={"id": None, "ativo": None, col_nome: st.column_config.TextColumn("Descrição", required=True)},
                num_rows="dynamic",
                key=f"ed_{key_suf}",
                use_container_width=True
            )
            if st.button("Salvar Alterações", key=f"btn_{key_suf}"):
                for index, row in edited.iterrows():
                    nome = row[col_nome]
                    if not nome: continue
                    if pd.notna(row['id']) and isinstance(row['id'], (int, float)):
                        run_query(f"UPDATE {tabela} SET {col_nome} = %s WHERE id = %s", (str(nome).upper(), int(row['id'])), commit=True)
                    else:
                        run_query(f"INSERT INTO {tabela} ({col_nome}, ativo) VALUES (%s, 1)", (str(nome).upper(),), commit=True)
                st.success("Salvo!")
                st.rerun()

        with tab1:
            st.info("Cadastre os Operadores aqui para aparecerem na lista.")
            editor_simples("furadeira_operadores", "nome", "f_ops")
            
        with tab2:
            st.info("Cadastre motivos como: Afiação de Broca, Manutenção, Falta de Peça.")
            editor_simples("furadeira_motivos_parada", "motivo", "f_mot")
            
        with tab3:
            st.subheader("Histórico de Produção")
            df_h = get_dataframe("SELECT * FROM furadeira_apontamentos WHERE ativo = 1 ORDER BY id DESC LIMIT 100")
            st.dataframe(df_h)
            
            if st.button("Baixar Excel Completo"):
                out = io.BytesIO()
                with pd.ExcelWriter(out, engine='openpyxl') as w:
                    get_dataframe("SELECT * FROM furadeira_apontamentos WHERE ativo=1").to_excel(w, sheet_name="Producao", index=False)
                    get_dataframe("SELECT * FROM furadeira_paradas_reg WHERE ativo=1").to_excel(w, sheet_name="Paradas", index=False)
                st.download_button("Download .xlsx", out.getvalue(), "relatorio_furadeira.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")