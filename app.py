import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta

st.set_page_config(page_title="Comparador AIA", layout="wide")

st.title("Simulador de Prazos AIA")
st.markdown("### Comparação: Cenário Ideal vs. Cenário Real")

# --- 1. DEFINIÇÃO ESTRITA DE FERIADOS (SEM FÉRIAS JUDICIAIS) ---
# Esta lista garante que o Natal NÃO para o relógio (exceto dia 25 e dia 1)
feriados_nacionais = [
    "2025-06-10", "2025-06-19", "2025-08-15", 
    "2025-10-05", "2025-11-01", "2025-12-01", 
    "2025-12-08", "2025-12-25", # Apenas dia 25
    "2026-01-01", # Apenas dia 1
    "2026-04-03", "2026-04-25", "2026-05-01"
]
feriados_np = np.array(feriados_nacionais, dtype='datetime64[D]')

# --- 2. INPUTS ---
with st.sidebar:
    st.header("Configuração")
    data_inicio = st.date_input("Data de Início", value=date(2025, 6, 3))
    prazo_legal = st.number_input("Prazo Legal (Dias Úteis)", value=150)
    
    st.subheader("Suspensões (Cenário Real)")
    suspensao_corridos = st.number_input("Suspensão Aditamentos (Dias Corridos)", value=45)
    suspensao_uteis = st.number_input("Suspensão Audiência (Dias Úteis)", value=10)
    
    # Momento em que as suspensões ocorrem (Simplificação baseada no seu relatório)
    # No seu relatório, a suspensão de 45 dias ocorre após ~60 dias úteis de trabalho
    # A suspensão de 10 dias ocorre após mais ~20 dias úteis.
    # Total dias gastos antes do final = 80 dias. Restam 70.

# --- 3. CÁLCULO A: DATA TEÓRICA (SEM SUSPENSÕES) ---
# Objetivo: 08/01/2026
try:
    fim_teorico_np = np.busday_offset(
        np.datetime64(data_inicio), 
        prazo_legal, 
        roll='forward', 
        weekmask='1111100', 
        holidays=feriados_np
    )
    data_teorica = pd.to_datetime(fim_teorico_np).date()
except Exception as e:
    st.error(f"Erro cálculo teórico: {e}")
    st.stop()

# --- 4. CÁLCULO B: DATA REAL (COM SUSPENSÕES) ---
# Objetivo: 06/03/2026 (Baseado no fluxo do relatório)

# Passo 1: Primeiros 60 dias úteis (até Aditamentos)
cursor = np.busday_offset(np.datetime64(data_inicio), 60, roll='forward', weekmask='1111100', holidays=feriados_np)

# Passo 2: Suspensão 45 dias corridos
cursor_dt = pd.to_datetime(cursor).date() + timedelta(days=suspensao_corridos)

# Passo 3: Mais 20 dias úteis (até Audiência)
cursor = np.busday_offset(np.datetime64(cursor_dt), 20, roll='forward', weekmask='1111100', holidays=feriados_np)

# Passo 4: Suspensão 10 dias úteis (Audiência)
# Nota: Como é suspensão, o prazo não anda, mas o calendário sim.
cursor = np.busday_offset(cursor, suspensao_uteis, roll='forward', weekmask='1111100', holidays=feriados_np)

# Passo 5: Restante do prazo (150 - 60 - 20 = 70 dias)
dias_restantes = prazo_legal - 80
fim_real_np = np.busday_offset(cursor, dias_restantes, roll='forward', weekmask='1111100', holidays=feriados_np)
data_real = pd.to_datetime(fim_real_np).date()


# --- 5. VISUALIZAÇÃO DOS RESULTADOS ---
col1, col2, col3 = st.columns(3)

# Data Real
with col1:
    st.subheader("DATA LIMITE (REAL)")
    st.metric(label="Com Suspensões", value=data_real.strftime("%d/%m/%Y"))
    if data_real.strftime("%d/%m/%Y") == "06/03/2026":
        st.success("✅ Confere com Relatório")

# Data Teórica
with col2:
    st.subheader("DATA LIMITE (TEÓRICA)")
    st.metric(label="Sem qualquer suspensão", value=data_teorica.strftime("%d/%m/%Y"))
    
    if data_teorica.strftime("%d/%m/%Y") == "08/01/2026":
        st.success("✅ Cálculo Puro (Correto)")
    elif data_teorica.strftime("%d/%m/%Y") == "22/01/2026":
        st.error("❌ Erro: Inclui Natal")
        st.caption("O sistema ainda está a contar férias judiciais.")
    else:
        st.warning("Verifique Data Início")

# Impacto
with col3:
    st.subheader("Impacto Temporal")
    diff = (data_real - data_teorica).days
    st.metric(label="Diferença (Dias Corridos)", value=f"+ {diff} dias")

st.divider()

# --- 6. QUADRO RESUMO ---
st.write("### Detalhe do Cálculo")
st.markdown(f"""
1.  **Cálculo Teórico:**
    * Início: 03/06/2025
    * Soma: 150 dias úteis consecutivos (ignorando apenas fins de semana e feriados nacionais).
    * Resultado Esperado: **08/01/2026**
    * *(Se der 22/01, é porque contou o intervalo 22/Dez-03/Jan como paragem, o que está ERRADO para o teórico).*

2.  **Cálculo Real (Projeto Solar):**
    * Inclui paragem de {suspensao_corridos} dias corridos (Aditamentos).
    * Inclui paragem de {suspensao_uteis} dias úteis (Audiência).
    * Resultado Esperado: **06/03/2026**
""")
