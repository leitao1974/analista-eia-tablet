import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta

st.set_page_config(page_title="Calculadora AIA - Detalhada", layout="wide")

st.title("Calculadora AIA: Cronograma Detalhado")
st.markdown("""
Esta calculadora replica a lógica da **Memória Justificativa**, separando o tempo em:
* **Contagem:** Abate aos 150 dias do prazo legal.
* **Suspensão:** Empurra a data final mas mantém o saldo de dias.
""")

# --- 1. CONFIGURAÇÃO DE FERIADOS ---
feriados_pt = [
    "2025-06-10", "2025-06-19", "2025-08-15", 
    "2025-10-05", "2025-11-01", "2025-12-01", 
    "2025-12-08", "2025-12-25", "2026-01-01",
    "2026-04-03", "2026-04-05", "2026-04-25", "2026-05-01" 
]
feriados_np = np.array(feriados_pt, dtype='datetime64[D]')

# --- 2. FUNÇÕES AUXILIARES ---
def add_business_days(start_date, days, holidays):
    return np.busday_offset(
        np.datetime64(start_date), 
        days, 
        roll='forward', 
        weekmask='1111100', 
        holidays=holidays
    )

def add_calendar_days(start_date, days):
    return pd.to_datetime(start_date) + timedelta(days=days)

# --- 3. INPUTS DO UTILIZADOR ---
with st.sidebar:
    st.header("Parâmetros")
    data_inicio = st.date_input("Data de Entrada", value=date(2025, 6, 3))
    prazo_legal_total = st.number_input("Prazo Legal Total (Dias Úteis)", value=150)
    
    st.markdown("---")
    st.subheader("Configuração das Etapas")
    
    # Etapas baseadas no seu documento
    # Etapa 1
    dias_conf = st.number_input("1. Conformidade (Dias Úteis)", value=10)
    # Etapa 2
    dias_cp = st.number_input("2. Consulta Pública (Dias Úteis)", value=35)
    # Etapa 3
    dias_analise = st.number_input("3. Análise I (Dias Úteis)", value=15)
    
    st.markdown("**Suspensões (Param o relógio)**")
    # Etapa 4 - Suspensão
    dias_aditamentos = st.number_input("4. Aditamentos (Dias CORRIDOS - Suspensão)", value=45)
    
    # Etapa 5
    dias_parecer = st.number_input("5. Avaliação Técnica (Dias Úteis)", value=20)
    
    # Etapa 6 - Suspensão
    dias_audiencia = st.number_input("6. Audiência Prévia (Dias ÚTEIS - Suspensão)", value=10)

# --- 4. MOTOR DE CÁLCULO (ETAPA A ETAPA) ---
# Inicialização
data_atual = data_inicio
saldo_dias = prazo_legal_total
log_calculo = []

# --- ETAPA 1: Conformidade (Consome Prazo) ---
fim_conf = add_business_days(data_atual, dias_conf, feriados_np)
log_calculo.append({"Etapa": "1. Conformidade", "Início": data_atual, "Fim": pd.to_datetime(fim_conf), "Tipo": "Consome Prazo", "Duração": dias_conf})
data_atual = pd.to_datetime(fim_conf)
saldo_dias -= dias_conf

# --- ETAPA 2: Consulta Pública (Consome Prazo) ---
# Nota: No seu doc, começa logo a seguir. Às vezes há gap de publicitação, mas vamos seguir o fluxo contínuo.
fim_cp = add_business_days(data_atual, dias_cp, feriados_np)
log_calculo.append({"Etapa": "2. Consulta Pública", "Início": data_atual, "Fim": pd.to_datetime(fim_cp), "Tipo": "Consome Prazo", "Duração": dias_cp})
data_atual = pd.to_datetime(fim_cp)
saldo_dias -= dias_cp

# --- ETAPA 3: Análise I (Consome Prazo) ---
fim_analise = add_business_days(data_atual, dias_analise, feriados_np)
log_calculo.append({"Etapa": "3. Análise I", "Início": data_atual, "Fim": pd.to_datetime(fim_analise), "Tipo": "Consome Prazo", "Duração": dias_analise})
data_atual = pd.to_datetime(fim_analise)
saldo_dias -= dias_analise

# --- ETAPA 4: Aditamentos (SUSPENSÃO - Dias Corridos) ---
# Aqui o saldo NÃO muda, mas a data avança.
fim_adit = add_calendar_days(data_atual, dias_aditamentos)
log_calculo.append({"Etapa": "4. Aditamentos (Suspensão)", "Início": data_atual, "Fim": fim_adit, "Tipo": "SUSPENSÃO (Dias Corridos)", "Duração": dias_aditamentos})
data_atual = fim_adit # Avançamos no calendário
# saldo_dias mantém-se igual

# --- ETAPA 5: Avaliação Técnica (Consome Prazo) ---
# Cuidado: Se a suspensão acabou num Sábado/Domingo, a contagem útil começa na 2ª feira seguinte?
# O busday_offset com roll='forward' resolve isso se passarmos 0 dias primeiro para alinhar.
data_atual_util = pd.to_datetime(add_business_days(data_atual, 0, feriados_np)) 

fim_tec = add_business_days(data_atual_util, dias_parecer, feriados_np)
log_calculo.append({"Etapa": "5. Avaliação Técnica", "Início": data_atual_util, "Fim": pd.to_datetime(fim_tec), "Tipo": "Consome Prazo", "Duração": dias_parecer})
data_atual = pd.to_datetime(fim_tec)
saldo_dias -= dias_parecer

# --- ETAPA 6: Audiência Prévia (SUSPENSÃO - Dias Úteis) ---
# O doc diz que dura 10 dias úteis e o estado é "SUSPENSO".
fim_audiencia = add_business_days(data_atual, dias_audiencia, feriados_np)
log_calculo.append({"Etapa": "6. Audiência Prévia (Suspensão)", "Início": data_atual, "Fim": pd.to_datetime(fim_audiencia), "Tipo": "SUSPENSÃO (Dias Úteis)", "Duração": dias_audiencia})
data_atual = pd.to_datetime(fim_audiencia)
# saldo_dias mantém-se igual

# --- CÁLCULO FINAL: O SALDO RESTANTE ---
# Quanto tempo falta para acabar os 150 dias?
log_calculo.append({"Etapa": "---", "Início": "---", "Fim": "---", "Tipo": "---", "Duração": "---"})

data_final_termo = add_business_days(data_atual, saldo_dias, feriados_np)
data_final_str = pd.to_datetime(data_final_termo).strftime("%d/%m/%Y")

# --- 5. APRESENTAÇÃO ---
col1, col2 = st.columns([1, 2])

with col1:
    st.metric(label="Dias Consumidos", value=f"{150 - saldo_dias} / 150")
    st.metric(label="Dias Restantes (Final)", value=saldo_dias)
    st.markdown("### Data Limite Prevista:")
    st.success(f"## {data_final_str}")
    
    if data_final_str == "06/03/2026":
        st.caption("✅ Confere com a Memória Justificativa!")
    else:
        st.caption("⚠️ Diferente do documento original.")

with col2:
    st.subheader("Cronograma Detalhado")
    df_log = pd.DataFrame(log_calculo)
    
    # Formatação para a tabela ficar bonita
    def format_date(x):
        if isinstance(x, (pd.Timestamp, date)):
            return x.strftime("%d/%m/%Y")
        return x

    df_display = df_log.copy()
    df_display['Início'] = df_display['Início'].apply(format_date)
    df_display['Fim'] = df_display['Fim'].apply(format_date)
    
    st.table(df_display)
