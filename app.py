import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
from datetime import datetime, date, time, timedelta
import io
import os

# ==============================================================================
# 1. CONFIGURAÇÕES E CONSTANTES
# ==============================================================================
st.set_page_config(page_title="Controle Setor Estamparia", layout="wide", page_icon="🏭")

# SENHA DO SUPERVISOR
SENHA_SUPERVISOR = "1234"

# ==============================================================================
# 2. CAMADA DE DADOS (CONEXÃO COM CORREÇÃO IPV4)
# ==============================================================================

def init_connection():
    try:
        # CONEXÃO VIA URL (Mais robusta para Nuvem)
        # Montamos uma "frase" com todos os dados e pedimos para conectar
        # Isso ajuda o sistema a escolher o melhor caminho (IPv4) sozinho
        
        connection_url = (
            f"postgresql://{st.secrets['DB_USER']}:{st.secrets['DB_PASS']}"
            f"@{st.secrets['DB_HOST']}:{st.secrets['DB_PORT']}"
            f"/{st.secrets['DB_NAME']}?sslmode=require"
        )
        
        return psycopg2.connect(connection_url)
        
    except Exception as e:
        st.error(f"ERRO DE CONEXÃO: {e}")
        return None

def db_query(query, params=(), fetch=False, commit=False):
    conn = None
    data = None
    try:
        conn = init_connection()
        if conn:
            cur = conn.cursor()
            cur.execute(query, params)
            if fetch:
                data = cur.fetchall()
            if commit:
                conn.commit()
            cur.close()
            conn.close()
    except Exception as e:
        st.error(f"Erro na execução do comando: {e}")
    return data

def get_list(table_name):
    query = f"SELECT nome FROM {table_name} WHERE ativo = 1 ORDER BY nome"
    res = db_query(query, fetch=True)
    return [r[0] for r in res] if res else []

def soft_delete(tabela, id_registro):
    query = f"UPDATE {tabela} SET ativo = 0 WHERE id = %s"
    db_query(query, (id_registro,), commit=True)

# ==============================================================================
# 3. CAMADA DE INTERFACE
# ==============================================================================

st.sidebar.title("🏭 Navegação")
st.title("🏭 IPAR ESTAMPARIA (WEB)")

st.sidebar.divider()

menu = st.sidebar.radio("Ir para:", [
    "📝 Apontamento Diário", 
    "⏸️ Registrar Parada",
    "📊 Dashboard de Performance", 
    "⚙️ Status de Manutenção",
    "🛠️ Prontuário de Manutenção",
    "⚙️ Cadastros Gerais",       
    "📂 Histórico & Exportar"    
])

autenticado = False
areas_restritas = ["⚙️ Cadastros Gerais", "📂 Histórico & Exportar"]

if menu in areas_restritas:
    st.sidebar.subheader("🔒 Acesso Supervisor")
    senha = st.sidebar.text_input("Senha", type="password")
    if senha == SENHA_SUPERVISOR:
        autenticado = True
    else:
        st.warning("Insira a senha para acessar.")
        st.stop()

# ==============================================================================
# 4. FUNCIONALIDADES
# ==============================================================================

# ---------------- APONTAMENTO DIÁRIO ----------------
if menu == "📝 Apontamento Diário":
    st.header("📝 Registro de Produção")
    
    if "confirma_producao" not in st.session_state:
        st.session_state.confirma_producao = None
    
    # Busca as listas atualizadas do banco (já com AR, BC, P1, etc.)
    ops = get_list("operadores")
    maqs = get_list("maquinas")
    list_materias = get_list("cad_materias")
    list_operacoes = get_list("cad_operacoes")
    
    if not ops or not maqs:
        st.warning("⚠️ Atenção: Cadastre Operadores e Máquinas antes de apontar.")
    else:
        if st.session_state.confirma_producao is None:
            with st.form("f_prod", clear_on_submit=False):
                st.subheader("1. Identificação")
                c1, c2, c3 = st.columns(3)
                with c1:
                    data_reg = st.date_input("Data", date.today())
                    cliente = st.text_input("Cliente")
                    operador = st.selectbox("Operador", ops)
                    maquina = c1.selectbox("Máquina", maqs)
                with c2:
                    desc_pc = st.text_input("Descrição da Peça / Produto")
                    operacao_sel = st.selectbox("Operação", list_operacoes) if list_operacoes else st.text_input("Operação (Digite)")
                with c3:
                    materia = st.selectbox("Matéria-Prima", list_materias)
                    tempo_c = st.number_input("Ciclo (Segundos/Peça)", value=5.0, step=0.1)

                st.markdown("---")
                st.subheader("2. Quantidades e Horários")
                c4, c5, c6 = st.columns(3)
                with c4:
                    qtd_p = st.number_input("Peças Boas", min_value=0)
                    refugo = st.number_input("Refugo", min_value=0)
                with c5:
                    h_i = st.time_input("Hora Início", time(7, 30))
                    h_f = st.time_input("Hora Fim", time(17, 0))
                with c6:
                    setup = st.number_input("Tempo Setup (min)", value=0)

                submitted = st.form_submit_button("🔍 Revisar Dados (Passo 1/2)")
                
                if submitted:
                    erro = False
                    dt_i = datetime.combine(data_reg, h_i)
                    dt_f = datetime.combine(data_reg, h_f)
                    if h_f < h_i: dt_f += timedelta(days=1)
                    
                    horas_trabalhadas = (dt_f - dt_i).total_seconds() / 3600
                    
                    if horas_trabalhadas <= 0:
                        st.error("❌ Tempo de produção inválido.")
                        erro = True
                    
                    if (qtd_p + refugo) <= 0:
                        st.error("❌ Quantidade zerada.")
                        erro = True

                    capacidade_teorica = (horas_trabalhadas * 3600) / tempo_c if tempo_c > 0 else 0
                    producao_total = qtd_p + refugo
                    
                    if not erro:
                        st.session_state.confirma_producao = {
                            "data": data_reg, "cliente": cliente, "descricao_pc": desc_pc, 
                            "operacao": operacao_sel, "materia": materia, "maquina": maquina, 
                            "tempo_c": tempo_c, "operador": operador, "setup": setup, 
                            "h_i": h_i, "h_f": h_f, "qtd_p": qtd_p, "refugo": refugo,
                            "horas_trab": horas_trabalhadas
                        }
                        st.rerun()

        else:
            dados = st.session_state.confirma_producao
            st.info("✋ **PARE E CONFIRME:** Verifique os dados abaixo.")
            
            with st.container(border=True):
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Produto", dados['descricao_pc'])
                k2.metric("Produção Total", f"{dados['qtd_p'] + dados['refugo']} pçs")
                k3.metric("Tempo Gasto", f"{dados['horas_trab']:.2f} h")
                
                ciclo_real = (dados['horas_trab'] * 3600) / (dados['qtd_p'] + dados['refugo']) if (dados['qtd_p'] + dados['refugo']) > 0 else 0
                k4.metric("Ciclo Realizado", f"{ciclo_real:.1f} seg", delta=f"{dados['tempo_c'] - ciclo_real:.1f}s vs Padrão")

                st.write(f"**Operador:** {dados['operador']} | **Máquina:** {dados['maquina']} | **Refugo:** {dados['refugo']}")
            
            col_confirma, col_cancela = st.columns(2)
            
            if col_confirma.button("✅ CONFIRMAR E GRAVAR"):
                query_insert = """
                    INSERT INTO apontamentos (data, cliente, descricao_pc, operacao, materia_prima, 
                    maquina, tempo_ciclo_seg, operador, setup_min, inicio_prod, fim_prod, 
                    qtd_produzida, refugo, meta_pc_hora, custo_refugo_unit, ativo) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, 0, 1)
                """
                params = (
                    dados['data'].isoformat(), dados['cliente'], dados['descricao_pc'], dados['operacao'], dados['materia'], 
                    dados['maquina'], dados['tempo_c'], dados['operador'], dados['setup'], 
                    dados['h_i'].strftime("%H:%M"), dados['h_f'].strftime("%H:%M"), 
                    dados['qtd_p'], dados['refugo']
                )
                db_query(query_insert, params, commit=True)
                
                db_query("UPDATE maquinas SET horimetro_total = horimetro_total + %s WHERE nome = %s", 
                         (dados['horas_trab'], dados['maquina']), commit=True)
                
                st.success("🎉 Produção registrada!")
                st.session_state.confirma_producao = None
                st.rerun()
            
            if col_cancela.button("❌ VOLTAR"):
                st.session_state.confirma_producao = None
                st.rerun()

    st.divider()
    st.markdown("### 🕒 Últimos 5 Registros Inseridos")
    conn = init_connection()
    if conn:
        df_ultimos = pd.read_sql("""
            SELECT id, data, fim_prod as "Hora Fim", operador, maquina, descricao_pc as "Produto", qtd_produzida as "Qtd" 
            FROM apontamentos 
            WHERE ativo = 1 
            ORDER BY id DESC LIMIT 5
        """, conn)
        conn.close()
        st.dataframe(df_ultimos, use_container_width=True, hide_index=True)

# ---------------- REGISTRAR PARADA ----------------
elif menu == "⏸️ Registrar Parada":
    st.header("⏸️ Registro de Paradas")
    maqs = get_list("maquinas")
    list_paradas = get_list("cad_paradas")
    
    with st.form("f_parada", clear_on_submit=True):
        c1, c2 = st.columns(2)
        d_p = c1.date_input("Data", date.today())
        m_p = c1.selectbox("Máquina", maqs) if maqs else st.text_input("Máquina")
        motivo = c1.selectbox("Motivo", list_paradas) if list_paradas else st.text_input("Motivo")
        h_i_p = c2.time_input("Início", time(10,0))
        h_f_p = c2.time_input("Fim", time(10,15))
        obs = c2.text_input("Obs")
        
        if st.form_submit_button("Salvar Parada"):
            db_query("""INSERT INTO paradas_reg (data, maquina, motivo, inicio, fim, observacao, ativo) 
                        VALUES (%s, %s, %s, %s, %s, %s, 1)""", 
                     (d_p.isoformat(), m_p, motivo, h_i_p.strftime("%H:%M"), h_f_p.strftime("%H:%M"), obs), commit=True)
            st.success("Registrado!")
    
    st.divider()
    st.subheader("Paradas do Dia")
    conn = init_connection()
    if conn:
        # Correção ::date para garantir que o filtro funcione
        df_hj = pd.read_sql("SELECT * FROM paradas_reg WHERE data::date = %s AND ativo = 1", conn, params=(date.today(),))
        conn.close()
        st.dataframe(df_hj, use_container_width=True)

# ---------------- CADASTROS GERAIS ----------------
elif menu == "⚙️ Cadastros Gerais" and autenticado:
    st.header("⚙️ Central de Cadastros")
    
    tab_op, tab_mq, tab_opr, tab_mat, tab_par = st.tabs([
        "👥 Operadores", "🏗️ Máquinas", "📝 Operações", "🧱 Matérias", "🛑 Paradas"
    ])
    
    def gerenciar_cadastro(tabela, label_singular, key_suf):
        c1, c2 = st.columns([3, 1])
        novo = c1.text_input(f"Nova {label_singular}", key=f"n_{key_suf}")
        
        if c2.button("Adicionar", key=f"a_{key_suf}"):
            if novo:
                novo_ajustado = novo.strip().upper() 
                check = db_query(f"SELECT id, ativo FROM {tabela} WHERE upper(nome) = %s", (novo_ajustado,), fetch=True)
                
                if check:
                    id_existente, is_ativo = check[0]
                    if is_ativo == 1:
                        st.warning(f"⚠️ '{novo_ajustado}' já existe!")
                    else:
                        query = f"UPDATE {tabela} SET ativo = 1 WHERE id = %s"
                        db_query(query, (id_existente,), commit=True)
                        st.success(f"♻️ '{novo_ajustado}' recuperado da lixeira!")
                        st.rerun()
                else:
                    query = f"INSERT INTO {tabela} (nome, ativo) VALUES (%s, 1)"
                    db_query(query, (novo_ajustado,), commit=True)
                    st.success("✅ Adicionado!")
                    st.rerun()
        
        conn = init_connection()
        if conn:
            df = pd.read_sql(f"SELECT * FROM {tabela} WHERE ativo = 1 ORDER BY nome", conn)
            conn.close()
            for _, row in df.iterrows():
                col_a, col_b = st.columns([4, 1])
                col_a.write(row['nome'])
                if col_b.button("🗑️", key=f"del_{key_suf}_{row['id']}"):
                    soft_delete(tabela, row['id'])
                    st.rerun()

    with tab_op: gerenciar_cadastro("operadores", "Operador", "oper")
    
    with tab_mq:
        c1, c2, c3 = st.columns([2, 1, 1])
        n_mq = c1.text_input("Nome Máquina")
        m_mq = c2.number_input("Meta Manut.", value=500)
        if c3.button("Adicionar Máquina"):
            if n_mq:
                n_mq = n_mq.strip().upper()
                check = db_query("SELECT id, ativo FROM maquinas WHERE upper(nome) = %s", (n_mq,), fetch=True)
                if check:
                    if check[0][1] == 1: st.warning("Máquina já existe!")
                    else:
                        db_query("UPDATE maquinas SET ativo=1, meta_manutencao=%s WHERE id=%s", (m_mq, check[0][0]), commit=True)
                        st.success("Recuperada!")
                        st.rerun()
                else:
                    db_query("INSERT INTO maquinas (nome, meta_manutencao, ativo) VALUES (%s,%s,1)", (n_mq, m_mq), commit=True)
                    st.success("Ok!")
                    st.rerun()

        conn = init_connection()
        if conn:
            df_mq = pd.read_sql("SELECT * FROM maquinas WHERE ativo = 1 ORDER BY nome", conn)
            conn.close()
            for _, r in df_mq.iterrows():
                ca, cb, cc = st.columns([2, 1, 1])
                ca.write(f"**{r['nome']}**")
                cb.write(f"Meta: {r['meta_manutencao']}h")
                if cc.button("🗑️", key=f"del_mq_{r['id']}"):
                    soft_delete("maquinas", r['id'])
                    st.rerun()

    with tab_opr: gerenciar_cadastro("cad_operacoes", "Operação", "oprs")
    with tab_mat: gerenciar_cadastro("cad_materias", "Matéria", "mats")
    with tab_par: gerenciar_cadastro("cad_paradas", "Motivo", "pars")

# ---------------- DASHBOARD ----------------
elif menu == "📊 Dashboard de Performance":
    st.header("📊 Inteligência de Produção")
    
    conn = init_connection()
    if conn:
        df = pd.read_sql("SELECT * FROM apontamentos WHERE ativo = 1", conn)
        df_p = pd.read_sql("SELECT * FROM paradas_reg WHERE ativo = 1", conn)
        conn.close()

        if df.empty:
            st.info("Sem dados ativos.")
        else:
            df["data_dt"] = pd.to_datetime(df["data"])
            dr = st.sidebar.date_input("Período", [df["data_dt"].min().date(), date.today()])
            
            if len(dr) == 2:
                df_f = df[(df["data_dt"].dt.date >= dr[0]) & (df["data_dt"].dt.date <= dr[1])].copy()
                
                # --- CÁLCULO DOS INDICADORES DE OEE ---
                df_f['dt_ini'] = pd.to_datetime(df_f['data'] + ' ' + df_f['inicio_prod'])
                df_f['dt_fim'] = pd.to_datetime(df_f['data'] + ' ' + df_f['fim_prod'])
                df_f.loc[df_f['dt_fim'] < df_f['dt_ini'], 'dt_fim'] += pd.Timedelta(days=1)
                
                # CRIAÇÃO DAS COLUNAS ESSENCIAIS
                df_f['tempo_real_min'] = (df_f['dt_fim'] - df_f['dt_ini']).dt.total_seconds() / 60
                df_f['tempo_teorico_min'] = ((df_f['qtd_produzida'] + df_f['refugo']) * df_f['tempo_ciclo_seg']) / 60
                total_setup_min = df_f['setup_min'].sum()
                
                # Disponibilidade
                tempo_prod_real_total = df_f['tempo_real_min'].sum()
                
                tempo_parado = 0
                df_pf = pd.DataFrame()
                if not df_p.empty:
                    df_p["data_dt"] = pd.to_datetime(df_p["data"])
                    df_pf = df_p[(df_p["data_dt"].dt.date >= dr[0]) & (df_p["data_dt"].dt.date <= dr[1])].copy()
                    if not df_pf.empty:
                        df_pf['dt_ini'] = pd.to_datetime(df_pf['data'] + ' ' + df_pf['inicio'])
                        df_pf['dt_fim'] = pd.to_datetime(df_pf['data'] + ' ' + df_pf['fim'])
                        df_pf.loc[df_pf['dt_fim'] < df_pf['dt_ini'], 'dt_fim'] += pd.Timedelta(days=1)
                        tempo_parado = ((df_pf['dt_fim'] - df_pf['dt_ini']).dt.total_seconds() / 60).sum()
                
                tempo_total_disponivel = tempo_prod_real_total + tempo_parado
                idx_disponibilidade = (tempo_prod_real_total / tempo_total_disponivel * 100) if tempo_total_disponivel > 0 else 0

                # Performance (Eficiência)
                tempo_teorico_total = df_f['tempo_teorico_min'].sum()
                idx_performance = (tempo_teorico_total / tempo_prod_real_total * 100) if tempo_prod_real_total > 0 else 0
                if idx_performance > 100: idx_performance = 100 

                # Qualidade
                total_pecas = df_f['qtd_produzida'].sum() + df_f['refugo'].sum()
                idx_qualidade = (df_f['qtd_produzida'].sum() / total_pecas * 100) if total_pecas > 0 else 0

                # OEE GLOBAL
                oee_global = (idx_disponibilidade/100) * (idx_performance/100) * (idx_qualidade/100) * 100

                # MTTR
                mttr = 0
                if not df_pf.empty:
                    quebras = df_pf[df_pf['motivo'].str.contains("QUEBRA|PANE|MANUTENÇÃO", case=False, na=False)]
                    if not quebras.empty:
                        duracao_quebras = ((quebras['dt_fim'] - quebras['dt_ini']).dt.total_seconds() / 60).sum()
                        mttr = duracao_quebras / len(quebras)
                
                taxa_setup = (total_setup_min / tempo_prod_real_total * 100) if tempo_prod_real_total > 0 else 0

                # --- VISUAL DO DASHBOARD ---
                col_oee, col_kpis = st.columns([1, 2])
                
                with col_oee:
                    fig_oee = go.Figure(go.Indicator(
                        mode = "gauge+number",
                        value = oee_global,
                        title = {'text': "OEE GLOBAL"},
                        gauge = {
                            'axis': {'range': [None, 100]},
                            'bar': {'color': "#1f77b4"},
                            'steps': [
                                {'range': [0, 65], 'color': "#ff4b4b"}, 
                                {'range': [65, 85], 'color': "#ffa500"}, 
                                {'range': [85, 100], 'color': "#00cc96"}], 
                            'threshold': {
                                'line': {'color': "black", 'width': 4},
                                'thickness': 0.75,
                                'value': 85}}))
                    fig_oee.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20))
                    st.plotly_chart(fig_oee, use_container_width=True)

                with col_kpis:
                    st.markdown("### Pilares do OEE")
                    k1, k2, k3 = st.columns(3)
                    k1.metric("1. Disponibilidade", f"{idx_disponibilidade:.1f}%", delta=f"Parado: {tempo_parado:.0f} min", delta_color="inverse")
                    k2.metric("2. Performance", f"{idx_performance:.1f}%", help="Velocidade Real vs Teórica")
                    k3.metric("3. Qualidade", f"{idx_qualidade:.1f}%", delta=f"Refugo: {df_f['refugo'].sum()} pçs", delta_color="inverse")
                    
                    st.info(f"Produção Total no Período: **{int(total_pecas)} peças**")
                    
                    k4, k5 = st.columns(2)
                    k4.metric("Setup Impacto", f"{taxa_setup:.1f}%", delta_color="inverse")
                    k5.metric("MTTR (Quebras)", f"{mttr:.0f} min", delta_color="inverse")

                st.divider()
                
                col_g1, col_g2 = st.columns(2)
                
                with col_g1:
                    st.subheader("Performance por Operador")
                    op_stats = df_f.groupby("operador").agg({"tempo_teorico_min": "sum", "tempo_real_min": "sum"}).reset_index()
                    op_stats['Eficiencia'] = 0.0
                    mask_real = op_stats['tempo_real_min'] > 0
                    op_stats.loc[mask_real, 'Eficiencia'] = (op_stats.loc[mask_real, 'tempo_teorico_min'] / op_stats.loc[mask_real, 'tempo_real_min']) * 100
                    op_stats['Cor'] = op_stats['Eficiencia'].apply(lambda x: '#FF4B4B' if x < 85 else '#00CC96')
                    
                    fig_perf = px.bar(op_stats, x="operador", y="Eficiencia", 
                                      color="Eficiencia", color_continuous_scale="RdYlGn", range_color=[50,100],
                                      text_auto='.1f')
                    fig_perf.add_hline(y=85, line_dash="dash", annotation_text="Meta")
                    st.plotly_chart(fig_perf, use_container_width=True)

                with col_g2:
                    st.subheader("Pareto de Paradas")
                    if tempo_parado > 0 and not df_pf.empty:
                        pg = df_pf.groupby("motivo")["duracao_min"].sum().reset_index().sort_values("duracao_min", ascending=False)
                        fig_par = px.bar(pg, x="duracao_min", y="motivo", orientation='h', text_auto='.0f')
                        st.plotly_chart(fig_par, use_container_width=True)
                    else:
                        st.info("Sem paradas registradas.")

# ---------------- STATUS MANUTENÇÃO ----------------
elif menu == "⚙️ Status de Manutenção":
    st.header("⚙️ Horímetros")
    conn = init_connection()
    if conn:
        df_m = pd.read_sql("SELECT * FROM maquinas WHERE ativo = 1", conn)
        conn.close()
        for _, row in df_m.iterrows():
            p = (row['horimetro_total'] / row['meta_manutencao']) if row['meta_manutencao'] > 0 else 0
            st.write(f"**{row['nome']}**")
            c1, c2 = st.columns([4,1])
            c1.progress(min(p, 1.0))
            c2.write(f"{row['horimetro_total']:.1f}/{row['meta_manutencao']}h")

elif menu == "🛠️ Prontuário de Manutenção":
    st.header("🛠️ Histórico Técnico")
    maqs = get_list("maquinas")
    with st.form("f_m"):
        c1, c2 = st.columns(2)
        d = c1.date_input("Data", date.today())
        m = c1.selectbox("Máquina", maqs) if maqs else st.warning("Cadastre máquinas")
        tp = c2.selectbox("Tipo", ["Preventiva", "Corretiva"])
        t = c2.text_input("Técnico")
        p = st.text_area("Peças/Serviço")
        z = st.checkbox("Zerar Horímetro?")
        if st.form_submit_button("Registrar"):
            db_query("INSERT INTO manutencoes (data_manut, maquina, tipo_manut, pecas_trocadas, tecnico, ativo) VALUES (%s,%s,%s,%s,%s,1)", (d.isoformat(), m, tp, p, t), commit=True)
            if z: db_query("UPDATE maquinas SET horimetro_total = 0 WHERE nome = %s", (m,), commit=True)
            st.success("Salvo!")

# ---------------- HISTÓRICO HÍBRIDO ----------------
elif menu == "📂 Histórico & Exportar" and autenticado:
    st.header("📂 Gerenciamento de Dados")

    tab_view, tab_export = st.tabs(["🔍 Visualização Rápida (Últimos)", "📉 Fechamento & Exportar (Excel)"])

    # ABA 1: VISUALIZAÇÃO RÁPIDA
    with tab_view:
        st.subheader("📋 Últimos 50 Registros (Edição Rápida)")
        st.caption("Aqui você vê os lançamentos mais recentes para conferência imediata.")
        
        conn = init_connection()
        if conn:
            df_recent = pd.read_sql("""
                SELECT id, data, maquina, operador, descricao_pc, qtd_produzida, refugo 
                FROM apontamentos 
                WHERE ativo = 1 
                ORDER BY id DESC LIMIT 50
            """, conn)
            conn.close()
            
            st.dataframe(df_recent, use_container_width=True)
            
            st.write("---")
            st.write("**Correção de Lançamento:**")
            c_del, c_btn = st.columns([1, 3])
            id_del = c_del.number_input("Digite o ID para Excluir", min_value=0, step=1)
            
            if c_btn.button("🗑️ Excluir Registro (Soft Delete)", type="primary"):
                check = db_query("SELECT id FROM apontamentos WHERE id=%s AND ativo=1", (id_del,), fetch=True)
                if check:
                    soft_delete("apontamentos", id_del)
                    st.success(f"Registro {id_del} movido para a lixeira.")
                    st.rerun()
                else:
                    st.error("ID não encontrado ou já excluído.")

    # ABA 2: FECHAMENTO & EXPORTAR
    with tab_export:
        st.subheader("📅 Filtro de Período (Fechamento)")
        
        hoje = date.today()
        primeiro_dia = hoje.replace(day=1)
        
        c1, c2 = st.columns(2)
        dt_ini = c1.date_input("Data Inicial", primeiro_dia)
        dt_fim = c2.date_input("Data Final", hoje)
        
        conn = init_connection()
        if conn:
            # Correção ::date para permitir filtro de data no Supabase
            df_prod = pd.read_sql("""
                SELECT * FROM apontamentos 
                WHERE ativo = 1 AND data::date BETWEEN %s AND %s
                ORDER BY data DESC, id DESC
            """, conn, params=(dt_ini, dt_fim))
            
            df_par = pd.read_sql("""
                SELECT * FROM paradas_reg 
                WHERE ativo = 1 AND data::date BETWEEN %s AND %s
                ORDER BY data DESC
            """, conn, params=(dt_ini, dt_fim))
            
            df_man = pd.read_sql("""
                SELECT * FROM manutencoes 
                WHERE ativo = 1 AND data_manut::date BETWEEN %s AND %s
                ORDER BY data_manut DESC
            """, conn, params=(dt_ini, dt_fim))
            conn.close()

            st.divider()
            st.info(f"📊 **Resumo do Período Selecionado:**")
            k1, k2, k3 = st.columns(3)
            k1.metric("Total Produzido", f"{df_prod['qtd_produzida'].sum():,} pçs" if not df_prod.empty else "0")
            k2.metric("Refugo Total", f"{df_prod['refugo'].sum():,} pçs" if not df_prod.empty else "0")
            k3.metric("Tempo Total Parado", f"{len(df_par)} eventos" if not df_par.empty else "0")

            st.divider()
            st.subheader("🚀 Baixar Relatório")
            
            if not df_prod.empty or not df_par.empty:
                nome_arquivo = f"Fechamento_{dt_ini.strftime('%d%m')}_a_{dt_fim.strftime('%d%m')}.xlsx"
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    if not df_prod.empty: df_prod.to_excel(writer, index=False, sheet_name='Producao')
                    if not df_par.empty: df_par.to_excel(writer, index=False, sheet_name='Paradas')
                    if not df_man.empty: df_man.to_excel(writer, index=False, sheet_name='Manutencao')
                    
                    if not df_prod.empty:
                        resumo = df_prod.groupby("operador")[["qtd_produzida", "refugo"]].sum().reset_index()
                        resumo.to_excel(writer, index=False, sheet_name='Resumo_Operador')

                st.download_button(
                    label=f"⬇️ Baixar Excel ({nome_arquivo})",
                    data=output.getvalue(),
                    file_name=nome_arquivo,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("Sem dados no período para exportar.")




