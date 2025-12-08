import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Cronograma RJAIA Simplex", layout="wide", page_icon="📅")

# --- 1. BASE DE DADOS DE FERIADOS (2025-2027) ---
# Apenas Feriados Nacionais (Dias em que a APA fecha).
# NÃO INCLUI: Férias Judiciais (Natal, Páscoa, Verão).
feriados_nacionais = [
    # 2025
    "2025-01-01", "2025-04-18", "2025-04-20", "2025-04-25", "2025-05-01",
    "2025-06-10", "2025-06-19", "2025-08-15", "2025-10-05", "2025-11-01",
    "2025-12-01", "2025-12-08", "2025-12-25",
    # 2026
    "2026-01-01", "2026-04-03", "2026-04-05", "2026-04-25", "2026-05-01",
    "2026-06-04", "2026-06-10", "2026-08-15", "2026-10-05", "2026-11-01",
    "2026-12-01", "2026-12-08", "2026-12-25",
    # 2027 (Previsão)
    "2027-01-01", "2027-03-26", "2027-03-28", "2027-04-25", "2027-05-01",
    "2027-05-27", "2027-06-10", "2027-08-15", "2027-10-05", "2027-11-01",
    "2027-12-01", "2027-12-08", "2027-12-25"
]
feriados_np = np.array(feriados_nacionais, dtype='datetime64[D]')

# --- 2. FUNÇÕES DE CÁLCULO ---
def somar_dias_uteis(data_inicio, dias, feriados):
    """Soma dias úteis (salta sáb, dom e feriados)."""
    return np.busday_offset(
        np.datetime64(data_inicio), 
        dias, 
        roll='forward', 
        weekmask='1111100', 
        holidays=feriados
    )

def formatar_data(np_date):
    """Converte numpy datetime para string PT."""
    return pd.to_datetime(np_date).strftime("%d/%m/%Y")

# --- 3. INTERFACE E INPUTS ---
st.title("📅 Cronograma RJAIA (Simplex)")
st.markdown("""
Calculadora de prazos de Avaliação de Impacte Ambiental de acordo com o **RJAIA** e **CPA**.
* **Regra de Contagem:** Dias Úteis (Segunda a Sexta).
* **Suspensões:** Apenas Feriados Nacionais (Não suspende em férias judiciais).
""")

st.sidebar.header("Configuração do Processo")

# A. Definição do Tipo de Processo
tipo_processo = st.sidebar.radio(
    "Tipologia do Processo:",
    options=["AIA Geral / Estudo Impacte Ambiental", "AIA Simplificado / Estudo Prévio"],
    index=0
)

# Define o "Plafond" de dias com base na escolha
if "Geral" in tipo_processo:
    PRAZO_MAXIMO = 150
    st.sidebar.info(f"Prazo Legal: **{PRAZO_MAXIMO} dias úteis**")
else:
    PRAZO_MAXIMO = 90
    st.sidebar.info(f"Prazo Legal: **{PRAZO_MAXIMO} dias úteis**")

# B. Data de Início
data_entrada = st.sidebar.date_input("Data de Submissão/Entrada", value=date(2025, 6, 3))

st.sidebar.markdown("---")
st.sidebar.subheader("Duração das Fases (Dias Úteis)")

# C. Inputs das Fases (Valores default ajustados à prática comum)
dias_conformidade = st.sidebar.number_input("1. Conformidade/Instrução", value=10, min_value=0)
dias_consulta = st.sidebar.number_input("2. Consulta Pública", value=30, min_value=0, help="Mínimo legal habitual é 30 dias úteis")
# O tempo de análise técnica é o "miolo" do processo
dias_analise = st.sidebar.number_input("3. Análise Técnica", value=60, min_value=0)
dias_audiencia = st.sidebar.number_input("4. Audiência de Interessados (CPA)", value=10, min_value=0)
dias_decisao = st.sidebar.number_input("5. Emissão da DIA", value=PRAZO_MAXIMO - (dias_conformidade+dias_consulta+dias_analise+dias_audiencia), help="O sistema calcula o restante, mas pode ajustar manual.")

# D. Suspensões (Paragens de Relógio)
st.sidebar.markdown("---")
st.sidebar.subheader("Suspensões (Paragens)")
st.sidebar.caption("Períodos em que o prazo administrativo 'congela' (ex: espera por aditamentos).")
suspensao_dias_uteis = st.sidebar.number_input("Total Dias de Suspensão (Úteis)", value=0, min_value=0)

# --- 4. MOTOR DE CÁLCULO (LINHA DO TEMPO) ---

# Inicialização
cronograma = []
cursor_data = data_entrada
dias_consumidos = 0

# Lista de Etapas para iterar
etapas = [
    ("1. Conformidade", dias_conformidade),
    ("2. Consulta Pública", dias_consulta),
    ("3. Análise Técnica", dias_analise),
    ("4. Audiência Prévia", dias_audiencia),
    ("5. Emissão da DIA", dias_decisao)
]

# Processamento das Etapas Normais
for nome, duracao in etapas:
    inicio_fase = cursor_data
    # Calcula data fim da fase
    fim_fase_np = somar_dias_uteis(inicio_fase, duracao, feriados_np)
    fim_fase = pd.to_datetime(fim_fase_np).date()
    
    cronograma.append({
        "Fase": nome,
        "Duração (Dias Úteis)": duracao,
        "Início": formatar_data(inicio_fase),
        "Fim": formatar_data(fim_fase),
        "Tipo": "Consome Prazo"
    })
    
    # Atualiza cursor e acumulador
    cursor_data = fim_fase
    dias_consumidos += duracao

# Processamento da Suspensão (se existir)
# Adicionamos a suspensão no final para simplificar a visualização do "Impacto na Data Final",
# ou podíamos intercalar. Aqui assumimos que a suspensão empurra a data final.
data_final_sem_suspensao = cursor_data

if suspensao_dias_uteis > 0:
    inicio_susp = cursor_data
    fim_susp_np = somar_dias_uteis(inicio_susp, suspensao_dias_uteis, feriados_np)
    fim_susp = pd.to_datetime(fim_susp_np).date()
    
    cronograma.append({
        "Fase": "⏸️ PERÍODO DE SUSPENSÃO (Aditamentos, etc)",
        "Duração (Dias Úteis)": suspensao_dias_uteis,
        "Início": formatar_data(inicio_susp),
        "Fim": formatar_data(fim_susp),
        "Tipo": "Não conta para o Prazo"
    })
    cursor_data = fim_susp

# Data Final Real
data_final_real = cursor_data

# --- 5. APRESENTAÇÃO DE RESULTADOS ---

# A. Métricas de Topo
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Prazo Legal", f"{PRAZO_MAXIMO} Dias Úteis")

with col2:
    saldo = PRAZO_MAXIMO - dias_consumidos
    label_saldo = "Saldo Disponível"
    if saldo < 0:
        label_saldo = "⚠️ Ultrapassagem de Prazo"
        st.metric(label_saldo, f"{saldo} Dias", delta_color="inverse")
    else:
        st.metric(label_saldo, f"{saldo} Dias")

with col3:
    st.metric("Data Final Estimada (DIA)", formatar_data(data_final_real))

# B. Barra de Progresso Visual
progresso = min(dias_consumidos / PRAZO_MAXIMO, 1.0)
st.progress(progresso, text=f"Ocupação do Prazo Legal: {dias_consumidos} de {PRAZO_MAXIMO} dias utilizados")

# C. Tabela Detalhada (Cronograma)
st.subheader("Cronograma Detalhado")
df_crono = pd.DataFrame(cronograma)

# Styling da tabela para destacar a suspensão
def highlight_suspension(row):
    if "SUSPENSÃO" in row['Fase']:
        return ['background-color: #ffcccc; color: black'] * len(row)
    else:
        return [''] * len(row)

st.dataframe(
    df_crono.style.apply(highlight_suspension, axis=1), 
    use_container_width=True, 
    hide_index=True
)

# D. Validação CPA
st.markdown("---")
with st.expander("ℹ️ Detalhes Legais e Validação"):
    st.markdown(f"""
    * **Data de Início:** {formatar_data(data_entrada)}
    * **Contagem:** Efetuada nos termos do art.º 87.º do CPA (apenas dias úteis).
    * **Feriados Considerados:** Apenas feriados nacionais oficiais.
    * **Férias Judiciais:** Ignoradas (conforme regime RJAIA/Administrativo).
    * **Nota:** Se houver suspensão do prazo (ex: pedido de elementos adicionais ao promotor), a data final desliza, mas o contador dos {PRAZO_MAXIMO} dias para.
    """)
