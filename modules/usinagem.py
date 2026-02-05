import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
from datetime import datetime, date, time, timedelta

# ==============================================================================
# 1. CONEXÃO E BANCO DE DADOS (COM CACHE DE PERFORMANCE)
# ==============================================================================

# O cache segura a conexão aberta por 1 hora (3600s) para não reconectar toda hora
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
        st.error(f"Erro de Conexão: {e}")
        return None

def run_query(query, params=(), fetch=False, commit=False):
    conn = init_connection()
    if not conn: return None
    result = None
    try:
        # Criamos um cursor novo, mas usamos a MESMA conexão cacheada
        with conn.cursor() as cur:
            cur.execute(query, params)
            if commit:
                conn.commit()
                result = "OK"
            if fetch:
                result = cur.fetchall()
        # NÃO fechamos a conexão aqui (conn.close) pois ela está no cache!
        return result
    except Exception as e:
        st.error(f"Erro SQL: {e}")
        conn.rollback() # Em caso de erro, desfazemos a transação atual
        return None

def get_dataframe(query, params=None):
    conn = init_connection()
    if not conn: return pd.DataFrame()
    try:
        # O pandas usa a conexão cacheada
        df = pd.read_sql(query, conn, params=params)
        return df
    except Exception as e:
        st.error(f"Erro ao gerar tabela: {e}")
        return pd.DataFrame()

# ... (O resto do código: get_list, render_app, etc., continua igual)

def get_list(table_name, col_name="nome"):
    # Agora aceita 'col_name', mas usa 'nome' como padrão se não informarmos nada
    res = run_query(f"SELECT {col_name} FROM {table_name} WHERE ativo = 1 ORDER BY {col_name}", fetch=True)
    return [r[0] for r in res] if res else []

# ==============================================================================
# 2. APLICAÇÃO PRINCIPAL (ENVELOPE)
# ==============================================================================
def render_app():
    # --- BARRA LATERAL (ORIGINAL RESTAURADA) ---
    st.sidebar.divider()
    st.sidebar.title("⚙️ Controle CNC")
    
    # Menu Lateral Original
    menu = st.sidebar.radio("Navegação", [
        "📝 Apontamento Produção",
        "📊 Dashboard OEE",
        "🛑 Registro de Paradas",
        "🔧 Manutenção",
        "⚙️ Cadastros Gerais",
        "📂 Histórico & Exportar"
    ])
    
    # --- SENHA DE SUPERVISOR (Recuperada) ---
    autenticado = False
    areas_restritas = ["⚙️ Cadastros Gerais", "📂 Histórico & Exportar"]

    if menu in areas_restritas:
        st.sidebar.markdown("---")
        st.sidebar.subheader("🔒 Acesso Supervisor")
        senha = st.sidebar.text_input("Senha", type="password")
        if senha == "1234":
            autenticado = True
        else:
            st.warning("Insira a senha para acessar esta área.")
            return # Para a execução aqui se não tiver senha

    # ==========================================================================
    # 1. APONTAMENTO PRODUÇÃO
    # ==========================================================================
    if menu == "📝 Apontamento Produção":
        st.header("📝 Registro de Produção (CNC)")
        
        if "confirma_producao" not in st.session_state:
            st.session_state.confirma_producao = None
        
        ops = get_list("usinagem_operadores")
        maqs = get_list("usinagem_maquinas")
        
        if not ops or not maqs:
            st.warning("⚠️ Atenção: Cadastre Operadores e Máquinas (em Cadastros Gerais) antes de apontar.")
        else:
            # MODO FORMULÁRIO
            if st.session_state.confirma_producao is None:
                with st.form("f_prod", clear_on_submit=False):
                    st.subheader("1. Dados do Processo")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        data_reg = st.date_input("Data", date.today())
                        maquina = st.selectbox("Torno / Centro Usinagem", maqs)
                        operador = st.selectbox("Operador", ops)
                    with c2:
                        desc_pc = st.text_input("Nome da Peça / Produto")
                        cod_prog = st.text_input("Código do Programa (Opcional)", placeholder="Ex: O0554")
                    with c3:
                        tempo_c = st.number_input("Ciclo (Segundos/Peça)", value=30.0, step=0.5, min_value=1.0)
                        cliente = st.text_input("Cliente / Ordem Produção")

                    st.markdown("---")
                    st.subheader("2. Quantidades e Tempos")
                    c4, c5, c6 = st.columns(3)
                    with c4:
                        qtd_p = st.number_input("Peças Boas", min_value=0)
                        refugo = st.number_input("Refugo / Sucata", min_value=0)
                    with c5:
                        h_i = st.time_input("Início do Lote", time(7, 0))
                        h_f = st.time_input("Fim do Lote", time(17, 0))
                    with c6:
                        setup = st.number_input("Tempo Setup (min)", value=0)

                    submitted = st.form_submit_button("🔍 Revisar Apontamento")
                    
                    if submitted:
                        dt_i = datetime.combine(data_reg, h_i)
                        dt_f = datetime.combine(data_reg, h_f)
                        if h_f < h_i: dt_f += timedelta(days=1)
                        horas_trabalhadas = (dt_f - dt_i).total_seconds() / 3600
                        
                        if horas_trabalhadas <= 0:
                            st.error("❌ Tempo de produção inválido.")
                        else:
                            st.session_state.confirma_producao = {
                                "data": data_reg, "cliente": cliente, "descricao_pc": desc_pc,
                                "cod_programa": cod_prog, "maquina": maquina,
                                "tempo_c": tempo_c, "operador": operador, "setup": setup,
                                "h_i": h_i, "h_f": h_f, "qtd_p": qtd_p, "refugo": refugo,
                                "horas_trab": horas_trabalhadas
                            }
                            st.rerun()

            # MODO CONFIRMAÇÃO
            else:
                dados = st.session_state.confirma_producao
                st.info("✋ **CONFIRMAÇÃO DE DADOS**")
                
                with st.container(border=True):
                    k1, k2, k3, k4 = st.columns(4)
                    k1.metric("Peça", dados['descricao_pc'])
                    k2.metric("Total Produzido", f"{dados['qtd_p'] + dados['refugo']} pçs")
                    k3.metric("Tempo Apontado", f"{dados['horas_trab']:.2f} h")
                    ciclo_real_seg = ((dados['horas_trab'] * 3600) - (dados['setup']*60)) / (dados['qtd_p'] + dados['refugo']) if (dados['qtd_p'] + dados['refugo']) > 0 else 0
                    k4.metric("Ciclo Real (Médio)", f"{ciclo_real_seg:.1f} s", delta=f"{dados['tempo_c'] - ciclo_real_seg:.1f}s vs Padrão")

                col_confirma, col_cancela = st.columns(2)
                
                if col_confirma.button("✅ GRAVAR APONTAMENTO"):
                    sql = """INSERT INTO usinagem_apontamentos (data_registro, cliente, descricao_pc, cod_programa, 
                                maquina, tempo_ciclo_seg, operador, setup_min, inicio_prod, fim_prod,
                                qtd_produzida, refugo, ativo)
                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1)"""
                    
                    run_query(sql, (dados['data'], dados['cliente'], dados['descricao_pc'], dados['cod_programa'],
                                    dados['maquina'], dados['tempo_c'], dados['operador'], dados['setup'],
                                    dados['h_i'], dados['h_f'], dados['qtd_p'], dados['refugo']), commit=True)
                    
                    # Atualiza horímetro
                    run_query("UPDATE usinagem_maquinas SET horimetro_total = horimetro_total + %s WHERE nome = %s",
                            (dados['horas_trab'], dados['maquina']), commit=True)
                    
                    st.success("🎉 Produção registrada com sucesso!")
                    st.session_state.confirma_producao = None
                    st.rerun()
                
                if col_cancela.button("❌ CORRIGIR"):
                    st.session_state.confirma_producao = None
                    st.rerun()

        st.divider()
        st.markdown("### 🕒 Últimos Registros")
        df_ultimos = get_dataframe('SELECT id, fim_prod as "Fim", maquina, descricao_pc as "Peca", qtd_produzida as "Boas" FROM usinagem_apontamentos WHERE ativo = 1 ORDER BY id DESC LIMIT 5')
        st.dataframe(df_ultimos, use_container_width=True, hide_index=True)

    # ==========================================================================
    # 2. DASHBOARD OEE
    # ==========================================================================
    elif menu == "📊 Dashboard OEE":
        st.header("📊 Inteligência de Usinagem")
        
        c_filtro1, c_filtro2 = st.columns(2)
        data_filtro = c_filtro1.date_input("Filtrar Data", date.today())
        
        df_prod = get_dataframe(f"SELECT * FROM usinagem_apontamentos WHERE ativo = 1 AND data_registro = '{data_filtro}'")
        df_parada = get_dataframe(f"SELECT * FROM usinagem_paradas_reg WHERE ativo = 1 AND data_registro = '{data_filtro}'")
        
        if df_prod.empty and df_parada.empty:
            st.info(f"Sem dados para a data: {data_filtro.strftime('%d/%m/%Y')}")
        else:
            # Tratamento de Datas para Cálculo
            if not df_prod.empty:
                df_prod['dt_ini'] = pd.to_datetime(df_prod['data_registro'].astype(str) + ' ' + df_prod['inicio_prod'].astype(str))
                df_prod['dt_fim'] = pd.to_datetime(df_prod['data_registro'].astype(str) + ' ' + df_prod['fim_prod'].astype(str))
                df_prod.loc[df_prod['dt_fim'] < df_prod['dt_ini'], 'dt_fim'] += pd.Timedelta(days=1)
                tempo_apontado_min = ((df_prod['dt_fim'] - df_prod['dt_ini']).dt.total_seconds() / 60).sum()
            else:
                tempo_apontado_min = 0

            tempo_parado_min = 0
            if not df_parada.empty:
                df_parada['dt_ini'] = pd.to_datetime(df_parada['data_registro'].astype(str) + ' ' + df_parada['inicio'].astype(str))
                df_parada['dt_fim'] = pd.to_datetime(df_parada['data_registro'].astype(str) + ' ' + df_parada['fim'].astype(str))
                df_parada.loc[df_parada['dt_fim'] < df_parada['dt_ini'], 'dt_fim'] += pd.Timedelta(days=1)
                tempo_parado_min = ((df_parada['dt_fim'] - df_parada['dt_ini']).dt.total_seconds() / 60).sum()
            
            # Métricas OEE
            tempo_operando_min = tempo_apontado_min - tempo_parado_min
            
            disponibilidade = (tempo_operando_min / tempo_apontado_min * 100) if tempo_apontado_min > 0 else 0
            
            total_pecas = df_prod['qtd_produzida'].sum() + df_prod['refugo'].sum() if not df_prod.empty else 0
            
            # Performance baseada na média ponderada
            tempo_teorico_total = 0
            if not df_prod.empty:
                df_prod['teorico_linha'] = ((df_prod['qtd_produzida'] + df_prod['refugo']) * df_prod['tempo_ciclo_seg']) / 60
                tempo_teorico_total = df_prod['teorico_linha'].sum()
            
            performance = (tempo_teorico_total / tempo_operando_min * 100) if tempo_operando_min > 0 else 0
            if performance > 100: performance = 100 
            
            pecas_boas = df_prod['qtd_produzida'].sum() if not df_prod.empty else 0
            qualidade = (pecas_boas / total_pecas * 100) if total_pecas > 0 else 0
            
            oee = (disponibilidade * performance * qualidade) / 10000
            
            col_gauge, col_kpi = st.columns([1, 2])
            with col_gauge:
                fig = go.Figure(go.Indicator(
                    mode = "gauge+number", value = oee, title = {'text': "OEE DO DIA"},
                    gauge = {'axis': {'range': [None, 100]}, 'bar': {'color': "#2E86C1"},
                        'steps': [{'range': [0, 60], 'color': "#E74C3C"}, {'range': [60, 85], 'color': "#F4D03F"}, {'range': [85, 100], 'color': "#2ECC71"}]}
                ))
                fig.update_layout(height=250, margin=dict(l=20,r=20,t=30,b=20))
                st.plotly_chart(fig, use_container_width=True)
                
            with col_kpi:
                st.markdown("#### Detalhamento dos Indicadores")
                k1, k2, k3 = st.columns(3)
                k1.metric("Disponibilidade", f"{disponibilidade:.1f}%", delta=f"-{tempo_parado_min:.0f} min Parado", delta_color="inverse")
                k2.metric("Performance", f"{performance:.1f}%")
                k3.metric("Qualidade", f"{qualidade:.1f}%", delta=f"{df_prod['refugo'].sum() if not df_prod.empty else 0} Refugos", delta_color="inverse")

            st.divider()
            c1, c2 = st.columns(2)
            if not df_prod.empty:
                with c1:
                    st.subheader("Produção por Máquina")
                    fig_bar = px.bar(df_prod, x="maquina", y="qtd_produzida", title="Peças Boas", text_auto=True)
                    st.plotly_chart(fig_bar, use_container_width=True)
            
            if not df_parada.empty:
                with c2:
                    st.subheader("Pareto de Paradas")
                    df_parada['duracao'] = ((df_parada['dt_fim'] - df_parada['dt_ini']).dt.total_seconds() / 60)
                    gf_par = df_parada.groupby("motivo")[["duracao"]].sum().reset_index().sort_values("duracao", ascending=False)
                    fig_pie = px.bar(gf_par, x="duracao", y="motivo", orientation='h', text_auto='.0f')
                    st.plotly_chart(fig_pie, use_container_width=True)

    # ==========================================================================
    # 3. REGISTRO DE PARADAS
    # ==========================================================================
    elif menu == "🛑 Registro de Paradas":
        st.header("🛑 Registro de Paradas")
        maqs = get_list("usinagem_maquinas")
        list_paradas = get_list("usinagem_motivos_parada", "motivo")
        
        if not maqs:
            st.warning("Cadastre máquinas primeiro.")
        else:
            with st.form("f_parada", clear_on_submit=True):
                c1, c2 = st.columns(2)
                d_p = c1.date_input("Data da Ocorrência", date.today())
                m_p = c1.selectbox("Máquina Parada", maqs)
                motivo = c1.selectbox("Motivo Principal", list_paradas)
                
                h_i_p = c2.time_input("Hora Início", time(10,0))
                h_f_p = c2.time_input("Hora Fim / Retorno", time(10,15))
                obs = c2.text_area("Observação")
                
                if st.form_submit_button("🚨 Registrar Parada"):
                    if h_f_p <= h_i_p:
                        st.error("A hora final deve ser maior que a inicial.")
                    else:
                        run_query("""INSERT INTO usinagem_paradas_reg (data_registro, maquina, motivo, inicio, fim, observacao, ativo)
                                    VALUES (%s,%s,%s,%s,%s,%s,1)""",
                                (d_p, m_p, motivo, h_i_p, h_f_p, obs), commit=True)
                        st.success("Parada registrada!")
            
            st.subheader("Histórico de Paradas do Dia")
            df_hj = get_dataframe(f"SELECT id, maquina, inicio, fim, motivo, observacao FROM usinagem_paradas_reg WHERE data_registro = '{date.today()}' AND ativo = 1 ORDER BY id DESC")
            st.dataframe(df_hj, use_container_width=True)

    # ==========================================================================
    # 4. MANUTENÇÃO
    # ==========================================================================
    elif menu == "🔧 Manutenção":
        st.header("🔧 Gestão de Manutenção")
        tab_status, tab_prontuario = st.tabs(["📊 Status & Horímetros", "🛠️ Prontuário Técnico"])
        
        with tab_status:
            df_m = get_dataframe("SELECT * FROM usinagem_maquinas WHERE ativo = 1 ORDER BY nome")
            if not df_m.empty:
                col_cards = st.columns(3)
                for index, row in df_m.iterrows():
                    with col_cards[index % 3]:
                        st.container(border=True).markdown(f"""
                        ### {row['nome']}
                        **Horímetro:** {row['horimetro_total']:.1f} h / Meta: {row['meta_manutencao']:.0f} h
                        """)
                        perc = (row['horimetro_total'] / row['meta_manutencao']) if row['meta_manutencao'] > 0 else 0
                        st.progress(min(perc, 1.0))
        
        with tab_prontuario:
            maqs = get_list("usinagem_maquinas")
            with st.form("f_manut"):
                c1, c2 = st.columns(2)
                d = c1.date_input("Data", date.today())
                m = c1.selectbox("Máquina", maqs)
                tp = c2.selectbox("Tipo", ["Preventiva", "Corretiva", "Preditiva"])
                tec = c2.text_input("Técnico")
                pecas = st.text_area("Peças Trocadas")
                zerar = st.checkbox("Zerar Horímetro?")
                
                if st.form_submit_button("Salvar Histórico"):
                    run_query("INSERT INTO usinagem_manutencoes (data_manut, maquina, tipo_manut, pecas_trocadas, tecnico, ativo) VALUES (%s,%s,%s,%s,%s,1)",
                             (d, m, tp, pecas, tec), commit=True)
                    if zerar:
                        run_query("UPDATE usinagem_maquinas SET horimetro_total = 0 WHERE nome = %s", (m,), commit=True)
                    st.success("Salvo!")

    # ==========================================================================
    # 5. CADASTROS GERAIS
    # ==========================================================================
    elif menu == "⚙️ Cadastros Gerais" and autenticado:
        st.header("⚙️ Configurações do Sistema")
        tab_op, tab_mq, tab_par = st.tabs(["👥 Operadores", "🏗️ Máquinas", "🛑 Motivos Parada"])
        
        def gerenciar_cadastro(tabela, label_singular, key_suf):
            c1, c2 = st.columns([3, 1])
            novo = c1.text_input(f"Novo(a) {label_singular}", key=f"n_{key_suf}")
            if c2.button("Adicionar", key=f"a_{key_suf}"):
                if novo:
                    run_query(f"INSERT INTO {tabela} (nome, ativo) VALUES (%s, 1)", (novo.upper(),), commit=True)
                    st.success("Adicionado!")
                    st.rerun()
            
            df = get_dataframe(f"SELECT * FROM {tabela} WHERE ativo = 1 ORDER BY nome")
            for _, row in df.iterrows():
                col_a, col_b = st.columns([4, 1])
                col_a.write(row['nome'])
                if col_b.button("🗑️", key=f"del_{key_suf}_{row['id']}"):
                    run_query(f"UPDATE {tabela} SET ativo = 0 WHERE id = %s", (row['id'],), commit=True)
                    st.rerun()

        with tab_op: gerenciar_cadastro("usinagem_operadores", "Operador", "oper")
        with tab_mq: 
            # Cadastro de Máquinas precisa ser customizado por causa do horímetro
            c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
            n_mq = c1.text_input("Nome (Ex: CNC-01)")
            mod_mq = c2.text_input("Modelo")
            meta_mq = c3.number_input("Meta Manut. (h)", value=500)
            if c4.button("Salvar Máquina"):
                if n_mq:
                    run_query("INSERT INTO usinagem_maquinas (nome, modelo, meta_manutencao, ativo) VALUES (%s,%s,%s,1)",
                             (n_mq.upper(), mod_mq, meta_mq), commit=True)
                    st.rerun()
            
            df_mq = get_dataframe("SELECT * FROM usinagem_maquinas WHERE ativo = 1")
            st.dataframe(df_mq[['nome', 'modelo', 'meta_manutencao']])

        with tab_par: 
            # Motivos de Parada (Campo é 'motivo' e não 'nome', adaptação necessária)
            c1, c2 = st.columns([3, 1])
            novo = c1.text_input(f"Novo Motivo")
            if c2.button("Adicionar Motivo"):
                if novo:
                    run_query(f"INSERT INTO usinagem_motivos_parada (motivo, ativo) VALUES (%s, 1)", (novo.upper(),), commit=True)
                    st.rerun()
            
            df = get_dataframe(f"SELECT * FROM usinagem_motivos_parada WHERE ativo = 1 ORDER BY motivo")
            for _, row in df.iterrows():
                col_a, col_b = st.columns([4, 1])
                col_a.write(row['motivo'])
                if col_b.button("🗑️", key=f"del_mot_{row['id']}"):
                    run_query(f"UPDATE usinagem_motivos_parada SET ativo = 0 WHERE id = %s", (row['id'],), commit=True)
                    st.rerun()

    # ==========================================================================
    # 6. HISTÓRICO & EXPORTAR
    # ==========================================================================
    elif menu == "📂 Histórico & Exportar" and autenticado:
        st.header("📂 Gerenciamento de Dados")
        
        st.subheader("Registros de Produção Ativos")
        df_a = get_dataframe("SELECT id, data_registro, maquina, operador, descricao_pc, qtd_produzida FROM usinagem_apontamentos WHERE ativo = 1 ORDER BY id DESC")
        st.dataframe(df_a, use_container_width=True)
        
        with st.expander("🗑️ Excluir Registro (Correção)"):
            c_id, c_btn = st.columns([1, 4])
            del_id = c_id.number_input("ID para Excluir", min_value=0, step=1)
            if c_btn.button("Solicitar Exclusão"):
                run_query("UPDATE usinagem_apontamentos SET ativo = 0 WHERE id = %s", (del_id,), commit=True)
                st.success("Registro excluído.")
                st.rerun()

        st.divider()
        st.subheader("📥 Exportação para Excel")
        
        if st.button("Baixar Banco de Dados Completo (.xlsx)"):
            try:
                out = io.BytesIO()
                with pd.ExcelWriter(out, engine='openpyxl') as w:
                    get_dataframe("SELECT * FROM usinagem_apontamentos WHERE ativo=1").to_excel(w, index=False, sheet_name='Producao')
                    get_dataframe("SELECT * FROM usinagem_paradas_reg WHERE ativo=1").to_excel(w, index=False, sheet_name='Paradas')
                    get_dataframe("SELECT * FROM usinagem_manutencoes WHERE ativo=1").to_excel(w, index=False, sheet_name='Manutencao')
                
                st.download_button("Clique aqui para baixar", out.getvalue(), "relatorio_usinagem_cnc.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception as e:
                st.error(f"Erro ao gerar Excel: {e}")
