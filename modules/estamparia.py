import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
from datetime import datetime, date, time, timedelta
import io

# ==============================================================================
# 1. CONFIGURAÇÕES DE CONEXÃO E BANCO DE DADOS
# ==============================================================================

# Senha para áreas administrativas
SENHA_SUPERVISOR = "1234"

def init_connection():
    """
    Estabelece a conexão com o Supabase (PostgreSQL) usando st.secrets
    Padrão blindado compartilhado com o módulo de Usinagem.
    """
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
    """
    Executa comandos SQL (INSERT, UPDATE, DELETE) ou consultas simples.
    """
    conn = init_connection()
    result = None
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(query, params)
            if fetch:
                result = cur.fetchall()
            if commit:
                conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            st.error(f"Erro na execução do SQL: {e}")
            if conn: conn.close()
    return result

def get_dataframe(query, params=()):
    """
    Retorna um Pandas DataFrame a partir de uma query SQL.
    """
    conn = init_connection()
    df = pd.DataFrame()
    if conn:
        try:
            df = pd.read_sql(query, conn, params=params)
            conn.close()
        except Exception as e:
            st.error(f"Erro ao ler dados: {e}")
            if conn: conn.close()
    return df

def get_list(table_suffix):
    """
    Busca lista de nomes ativos para dropdowns.
    Adiciona automaticamente o prefixo 'estamparia_'.
    """
    query = f"SELECT nome FROM estamparia_{table_suffix} WHERE ativo = 1 ORDER BY nome"
    res = run_query(query, fetch=True)
    return [r[0] for r in res] if res else []

def soft_delete(table_suffix, id_registro):
    """
    Realiza a exclusão lógica (ativo = 0).
    """
    query = f"UPDATE estamparia_{table_suffix} SET ativo = 0 WHERE id = %s"
    run_query(query, (id_registro,), commit=True)

# ==============================================================================
# 2. FUNÇÃO PRINCIPAL (ENVELOPE)
# ==============================================================================

def render_app():
    """
    Função principal que renderiza todo o módulo de Estamparia.
    """
    st.markdown("## 🏭 Módulo de Estamparia")
    st.markdown("---")

    # --- MENU LATERAL ESPECÍFICO DO MÓDULO ---
    st.sidebar.markdown("### 🧭 Menu Estamparia")
    
    # Key única para não conflitar com o menu da Usinagem ou Main
    menu = st.sidebar.radio("Navegação:", [
        "📝 Apontamento Diário", 
        "⏸️ Registrar Parada",
        "📊 Dashboard", 
        "⚙️ Status Máquinas",
        "🛠️ Prontuário Manutenção",
        "⚙️ Cadastros Gerais",       
        "📂 Histórico & Exportar"    
    ], key="nav_estamparia")

    # Controle de Acesso Supervisor
    autenticado = False
    areas_restritas = ["⚙️ Cadastros Gerais", "📂 Histórico & Exportar"]

    if menu in areas_restritas:
        st.sidebar.markdown("🔒 **Área Restrita**")
        senha = st.sidebar.text_input("Senha Supervisor", type="password", key="pass_estamparia")
        if senha == SENHA_SUPERVISOR:
            autenticado = True
        else:
            st.warning("🔒 Digite a senha para acessar.")
            return # Para a execução aqui se não tiver senha

    # ==========================================================================
    # 3. IMPLEMENTAÇÃO DAS FUNCIONALIDADES
    # ==========================================================================

    # ---------------- APONTAMENTO DIÁRIO ----------------
    if menu == "📝 Apontamento Diário":
        st.subheader("📝 Registro de Produção")
        
        if "confirma_est" not in st.session_state:
            st.session_state.confirma_est = None
        
        # Carrega Listas
        ops = get_list("operadores")
        maqs = get_list("maquinas")
        list_materias = get_list("cad_materias")
        list_operacoes = get_list("cad_operacoes")
        
        if not ops or not maqs:
            st.warning("⚠️ Cadastre Operadores e Máquinas em 'Cadastros Gerais' antes de apontar.")
        else:
            if st.session_state.confirma_est is None:
                with st.form("form_prod_est", clear_on_submit=False):
                    st.markdown("##### 1. Identificação")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        data_reg = st.date_input("Data", date.today())
                        cliente = st.text_input("Cliente")
                        operador = st.selectbox("Operador", ops)
                        maquina = st.selectbox("Máquina", maqs)
                    with c2:
                        desc_pc = st.text_input("Produto / Peça")
                        operacao = st.selectbox("Operação", list_operacoes) if list_operacoes else st.text_input("Operação")
                    with c3:
                        materia = st.selectbox("Matéria-Prima", list_materias) if list_materias else st.text_input("Matéria")
                        tempo_c = st.number_input("Ciclo (seg/pç)", value=5.0, step=0.1, min_value=0.1)

                    st.markdown("##### 2. Quantidades e Horários")
                    c4, c5, c6 = st.columns(3)
                    with c4:
                        qtd_p = st.number_input("Peças Boas", min_value=0)
                        refugo = st.number_input("Refugo", min_value=0)
                    with c5:
                        h_i = st.time_input("Hora Início", time(7, 30))
                        h_f = st.time_input("Hora Fim", time(17, 0))
                    with c6:
                        setup = st.number_input("Tempo Setup (min)", value=0)

                    if st.form_submit_button("🔍 Revisar"):
                        # Cálculo de horas
                        dt_i = datetime.combine(data_reg, h_i)
                        dt_f = datetime.combine(data_reg, h_f)
                        if h_f < h_i: dt_f += timedelta(days=1)
                        horas_trab = (dt_f - dt_i).total_seconds() / 3600
                        
                        erro = False
                        if horas_trab <= 0:
                            st.error("Tempo inválido.")
                            erro = True
                        if (qtd_p + refugo) <= 0:
                            st.error("Quantidade zerada.")
                            erro = True

                        if not erro:
                            st.session_state.confirma_est = {
                                "data": data_reg, "cliente": cliente, "descricao_pc": desc_pc, 
                                "operacao": operacao, "materia": materia, "maquina": maquina, 
                                "tempo_c": tempo_c, "operador": operador, "setup": setup, 
                                "h_i": h_i, "h_f": h_f, "qtd_p": qtd_p, "refugo": refugo,
                                "horas_trab": horas_trab
                            }
                            st.rerun()

            else:
                # Confirmação
                d = st.session_state.confirma_est
                st.info("✋ **Confirme os dados:**")
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Produto", d['descricao_pc'])
                k2.metric("Total Peças", int(d['qtd_p'] + d['refugo']))
                k3.metric("Tempo", f"{d['horas_trab']:.2f} h")
                
                prod_total = d['qtd_p'] + d['refugo']
                ciclo_real = (d['horas_trab'] * 3600) / prod_total if prod_total > 0 else 0
                k4.metric("Ciclo Real", f"{ciclo_real:.1f}s")
                
                col_ok, col_nok = st.columns(2)
                if col_ok.button("✅ SALVAR"):
                    sql = """
                        INSERT INTO estamparia_apontamentos 
                        (data, cliente, descricao_pc, operacao, materia_prima, maquina, tempo_ciclo_seg, 
                        operador, setup_min, inicio_prod, fim_prod, qtd_produzida, refugo, ativo) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
                    """
                    params = (
                        d['data'], d['cliente'], d['descricao_pc'], d['operacao'], d['materia'], d['maquina'],
                        d['tempo_c'], d['operador'], d['setup'], d['h_i'].strftime("%H:%M"), 
                        d['h_f'].strftime("%H:%M"), d['qtd_p'], d['refugo']
                    )
                    run_query(sql, params, commit=True)
                    
                    # Atualiza Horímetro
                    run_query("UPDATE estamparia_maquinas SET horimetro_total = horimetro_total + %s WHERE nome = %s", 
                             (d['horas_trab'], d['maquina']), commit=True)
                    
                    st.success("Salvo com sucesso!")
                    st.session_state.confirma_est = None
                    st.rerun()
                
                if col_nok.button("❌ VOLTAR"):
                    st.session_state.confirma_est = None
                    st.rerun()

        st.divider()
        st.markdown("### Últimos Registros")
        df_ult = get_dataframe("""
            SELECT id, data, maquina, operador, descricao_pc as "Produto", qtd_produzida as "Qtd" 
            FROM estamparia_apontamentos WHERE ativo = 1 ORDER BY id DESC LIMIT 5
        """)
        st.dataframe(df_ult, use_container_width=True, hide_index=True)

    # ---------------- REGISTRAR PARADA ----------------
    elif menu == "⏸️ Registrar Parada":
        st.subheader("⏸️ Registrar Parada")
        maqs = get_list("maquinas")
        motivos = get_list("cad_paradas")
        
        with st.form("form_parada_est"):
            c1, c2 = st.columns(2)
            dt_p = c1.date_input("Data", date.today())
            mq_p = c1.selectbox("Máquina", maqs) if maqs else st.text_input("Máquina")
            mt_p = c1.selectbox("Motivo", motivos) if motivos else st.text_input("Motivo")
            h_i = c2.time_input("Início", time(10,0))
            h_f = c2.time_input("Fim", time(10,15))
            obs = c2.text_input("Obs")
            
            if st.form_submit_button("Salvar Parada"):
                sql = """
                    INSERT INTO estamparia_paradas_reg (data, maquina, motivo, inicio, fim, observacao, ativo)
                    VALUES (%s, %s, %s, %s, %s, %s, 1)
                """
                run_query(sql, (dt_p, mq_p, mt_p, h_i.strftime("%H:%M"), h_f.strftime("%H:%M"), obs), commit=True)
                st.success("Parada registrada!")
        
        st.divider()
        st.write("Paradas de Hoje:")
        df_par = get_dataframe("SELECT * FROM estamparia_paradas_reg WHERE data::date = %s AND ativo = 1", (date.today(),))
        st.dataframe(df_par, use_container_width=True)

    # ---------------- DASHBOARD ----------------
    elif menu == "📊 Dashboard":
        st.subheader("📊 Indicadores de Performance")
        
        # Filtro de Data
        c1, c2 = st.columns(2)
        d_ini = c1.date_input("De:", date.today().replace(day=1), key="d1_est")
        d_fim = c2.date_input("Até:", date.today(), key="d2_est")
        
        # Carrega Dados
        df = get_dataframe("SELECT * FROM estamparia_apontamentos WHERE ativo = 1 AND data::date BETWEEN %s AND %s", (d_ini, d_fim))
        df_p = get_dataframe("SELECT * FROM estamparia_paradas_reg WHERE ativo = 1 AND data::date BETWEEN %s AND %s", (d_ini, d_fim))
        
        if df.empty:
            st.info("Sem produção no período.")
        else:
            # Processamento de Dados
            df['dt_ini'] = pd.to_datetime(df['data'].astype(str) + ' ' + df['inicio_prod'].astype(str))
            df['dt_fim'] = pd.to_datetime(df['data'].astype(str) + ' ' + df['fim_prod'].astype(str))
            df.loc[df['dt_fim'] < df['dt_ini'], 'dt_fim'] += timedelta(days=1)
            
            df['tempo_real_min'] = (df['dt_fim'] - df['dt_ini']).dt.total_seconds() / 60
            df['tempo_teorico_min'] = ((df['qtd_produzida'] + df['refugo']) * df['tempo_ciclo_seg']) / 60
            
            # Cálculos KPI
            tempo_prod = df['tempo_real_min'].sum()
            tempo_parado = 0
            
            if not df_p.empty:
                df_p['dt_ini'] = pd.to_datetime(df_p['data'].astype(str) + ' ' + df_p['inicio'].astype(str))
                df_p['dt_fim'] = pd.to_datetime(df_p['data'].astype(str) + ' ' + df_p['fim'].astype(str))
                df_p.loc[df_p['dt_fim'] < df_p['dt_ini'], 'dt_fim'] += timedelta(days=1)
                tempo_parado = ((df_p['dt_fim'] - df_p['dt_ini']).dt.total_seconds() / 60).sum()
            
            tempo_disp = tempo_prod + tempo_parado
            idx_disp = (tempo_prod / tempo_disp * 100) if tempo_disp > 0 else 0
            
            idx_perf = (df['tempo_teorico_min'].sum() / tempo_prod * 100) if tempo_prod > 0 else 0
            if idx_perf > 100: idx_perf = 100
            
            total_pcs = df['qtd_produzida'].sum() + df['refugo'].sum()
            idx_qual = (df['qtd_produzida'].sum() / total_pcs * 100) if total_pcs > 0 else 0
            
            oee = (idx_disp/100) * (idx_perf/100) * (idx_qual/100) * 100
            
            # Gráfico Gauge OEE
            col_g, col_k = st.columns([1, 2])
            with col_g:
                fig = go.Figure(go.Indicator(
                    mode = "gauge+number", value = oee, title = {'text': "OEE"},
                    gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "#3366CC"},
                             'steps': [{'range': [0, 65], 'color': "#FF9999"}, {'range': [85, 100], 'color': "#99FF99"}]}
                ))
                fig.update_layout(height=250, margin=dict(l=20,r=20,t=40,b=20))
                st.plotly_chart(fig, use_container_width=True)
            
            with col_k:
                k1, k2, k3 = st.columns(3)
                k1.metric("Disponibilidade", f"{idx_disp:.1f}%")
                k2.metric("Performance", f"{idx_perf:.1f}%")
                k3.metric("Qualidade", f"{idx_qual:.1f}%", delta=f"Refugo: {df['refugo'].sum()}")
                st.info(f"Produção Total: **{int(total_pcs)} peças**")

            # Gráficos de Barra
            g1, g2 = st.columns(2)
            with g1:
                st.markdown("##### Eficiência por Operador")
                op_stats = df.groupby("operador").agg({"tempo_teorico_min": "sum", "tempo_real_min": "sum"}).reset_index()
                op_stats['Efic'] = 0.0
                mask = op_stats['tempo_real_min'] > 0
                op_stats.loc[mask, 'Efic'] = (op_stats.loc[mask, 'tempo_teorico_min'] / op_stats.loc[mask, 'tempo_real_min']) * 100
                fig_op = px.bar(op_stats, x="operador", y="Efic", text_auto='.1f', range_y=[0,110])
                st.plotly_chart(fig_op, use_container_width=True)

    # ---------------- STATUS MÁQUINAS ----------------
    elif menu == "⚙️ Status Máquinas":
        st.subheader("⚙️ Manutenção Preventiva (Horímetros)")
        df_mq = get_dataframe("SELECT * FROM estamparia_maquinas WHERE ativo = 1 ORDER BY nome")
        
        if not df_mq.empty:
            for _, r in df_mq.iterrows():
                perc = (r['horimetro_total'] / r['meta_manutencao']) if r['meta_manutencao'] > 0 else 0
                st.write(f"**{r['nome']}**")
                c1, c2 = st.columns([4, 1])
                c1.progress(min(perc, 1.0))
                c2.write(f"{r['horimetro_total']:.0f} / {r['meta_manutencao']:.0f} h")
                if perc >= 1: st.error("⚠️ Manutenção Vencida!")

    # ---------------- PRONTUÁRIO MANUTENÇÃO ----------------
    elif menu == "🛠️ Prontuário Manutenção":
        st.subheader("🛠️ Registrar Manutenção")
        maqs = get_list("maquinas")
        
        with st.form("form_manut"):
            c1, c2 = st.columns(2)
            dt_m = c1.date_input("Data", date.today())
            mq_m = c1.selectbox("Máquina", maqs) if maqs else st.text_input("Máquina")
            tp_m = c2.selectbox("Tipo", ["Preventiva", "Corretiva"])
            tec = c2.text_input("Técnico")
            desc = st.text_area("Descrição")
            zerar = st.checkbox("Zerar Horímetro?")
            
            if st.form_submit_button("Registrar"):
                sql = """
                    INSERT INTO estamparia_manutencoes (data_manut, maquina, tipo_manut, descricao, tecnico, ativo)
                    VALUES (%s, %s, %s, %s, %s, 1)
                """
                run_query(sql, (dt_m, mq_m, tp_m, desc, tec), commit=True)
                
                if zerar:
                    run_query("UPDATE estamparia_maquinas SET horimetro_total = 0 WHERE nome = %s", (mq_m,), commit=True)
                
                st.success("Manutenção registrada!")

    # ---------------- CADASTROS GERAIS ----------------
    elif menu == "⚙️ Cadastros Gerais" and autenticado:
        st.subheader("⚙️ Cadastros")
        t1, t2, t3, t4, t5 = st.tabs(["Operadores", "Máquinas", "Operações", "Materiais", "Paradas"])
        
        def crud_simples(sufixo, label):
            c1, c2 = st.columns([3, 1])
            novo = c1.text_input(f"Novo {label}", key=f"n_{sufixo}")
            if c2.button("Adicionar", key=f"add_{sufixo}"):
                if novo:
                    run_query(f"INSERT INTO estamparia_{sufixo} (nome, ativo) VALUES (%s, 1)", (novo.upper(),), commit=True)
                    st.rerun()
            
            df = get_dataframe(f"SELECT * FROM estamparia_{sufixo} WHERE ativo=1 ORDER BY nome")
            for _, r in df.iterrows():
                ca, cb = st.columns([4, 1])
                ca.write(r['nome'])
                if cb.button("🗑️", key=f"del_{sufixo}_{r['id']}"):
                    soft_delete(sufixo, r['id'])
                    st.rerun()

        with t1: crud_simples("operadores", "Operador")
        with t3: crud_simples("cad_operacoes", "Operação")
        with t4: crud_simples("cad_materias", "Matéria")
        with t5: crud_simples("cad_paradas", "Motivo")
        
        with t2: # Máquinas (com meta)
            c1, c2, c3 = st.columns([2,1,1])
            nm = c1.text_input("Nome Máquina")
            meta = c2.number_input("Meta (h)", value=500)
            if c3.button("Add Máquina"):
                if nm:
                    run_query("INSERT INTO estamparia_maquinas (nome, meta_manutencao, ativo) VALUES (%s, %s, 1)", 
                             (nm.upper(), meta), commit=True)
                    st.rerun()
            
            df = get_dataframe("SELECT * FROM estamparia_maquinas WHERE ativo=1 ORDER BY nome")
            for _, r in df.iterrows():
                ca, cb, cc = st.columns([3, 1, 1])
                ca.write(r['nome'])
                cb.write(f"{r['meta_manutencao']}h")
                if cc.button("🗑️", key=f"del_mq_{r['id']}"):
                    soft_delete("maquinas", r['id'])
                    st.rerun()

    # ---------------- HISTÓRICO E EXPORTAR ----------------
    elif menu == "📂 Histórico & Exportar" and autenticado:
        st.subheader("📂 Dados")
        tab_v, tab_e = st.tabs(["Visualizar", "Exportar Excel"])
        
        with tab_v:
            df = get_dataframe("SELECT id, data, maquina, operador, descricao_pc FROM estamparia_apontamentos WHERE ativo=1 ORDER BY id DESC LIMIT 20")
            st.dataframe(df, use_container_width=True)
            
            del_id = st.number_input("ID para excluir", step=1)
            if st.button("Excluir Registro"):
                soft_delete("apontamentos", del_id)
                st.success("Excluído.")
                st.rerun()
        
        with tab_e:
            c1, c2 = st.columns(2)
            d1 = c1.date_input("Início", date.today().replace(day=1))
            d2 = c2.date_input("Fim", date.today())
            
            if st.button("Gerar Relatório Excel"):
                df1 = get_dataframe("SELECT * FROM estamparia_apontamentos WHERE ativo=1 AND data::date BETWEEN %s AND %s", (d1, d2))
                df2 = get_dataframe("SELECT * FROM estamparia_paradas_reg WHERE ativo=1 AND data::date BETWEEN %s AND %s", (d1, d2))
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    if not df1.empty: df1.to_excel(writer, sheet_name="Producao", index=False)
                    if not df2.empty: df2.to_excel(writer, sheet_name="Paradas", index=False)
                
                st.download_button("⬇️ Baixar", output.getvalue(), f"Estamparia_{d1}_{d2}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
