import streamlit as st
import pandas as pd
import numpy as np
from datetime import date

# Configuração da Página
st.set_page_config(page_title="Calculadora AIA", layout="centered")

st.title("Calculadora de Prazos AIA")
st.warning("⚠️ Modo Estrito: Apenas Dias Úteis (Sem Férias Judiciais)")

# --- 1. ENTRADAS (INPUTS) ---
col1, col2 = st.columns(2)

with col1:
    # Fixamos o valor default em 03/06/2025 conforme o seu caso real
    data_inicial = st.date_input("Data Inicial", value=date(2025, 6, 3))

with col2:
    prazo = st.number_input("Prazo (dias)", value=150, step=1)

# --- 2. DEFINIÇÃO DOS FERIADOS (Apenas os dias vermelhos) ---
# Se houver algum intervalo (tipo range de natal) aqui, REMOVA.
# Abaixo estão APENAS os feriados nacionais pontuais.
feriados_list = [
    "2025-06-10", # Dia de Portugal
    "2025-06-19", # Corpo de Deus
    "2025-08-15", # Assunção
    "2025-10-05", # Implantação (Domingo)
    "2025-11-01", # Todos os Santos (Sábado)
    "2025-12-01", # Restauração
    "2025-12-08", # Imaculada Conceição
    "2025-12-25", # Natal (Apenas o dia 25!)
    "2026-01-01", # Ano Novo (Apenas o dia 1!)
    "2026-04-03"  # Sexta-feira Santa (exemplo futuro)
]

# Converter para formato numpy
feriados_np = np.array(feriados_list, dtype='datetime64[D]')

# --- 3. CÁLCULO DIRETO (SEM SUSPENSÕES) ---
# A função busday_offset conta dias úteis saltando APENAS fins de semana e a lista acima.
try:
    data_final_np = np.busday_offset(
        np.datetime64(data_inicial), 
        prazo, 
        roll='forward', 
        weekmask='1111100', 
        holidays=feriados_np
    )
    data_final = pd.to_datetime(data_final_np)
    
except Exception as e:
    st.error(f"Erro no cálculo: {e}")
    st.stop()

# --- 4. RESULTADO ---
st.divider()

col_res1, col_res2 = st.columns(2)

with col_res1:
    st.metric(label="Data Final Calculada", value=data_final.strftime("%d/%m/%Y"))

with col_res2:
    # Verificação de Prova
    if data_final.strftime("%d/%m/%Y") == "08/01/2026":
        st.success("✅ O valor está CORRETO (08/01/2026)")
    elif data_final.strftime("%d/%m/%Y") == "22/01/2026":
        st.error("❌ ERRO CRÍTICO: O sistema ainda está a aplicar suspensão de Natal.")
    else:
        st.warning(f"O valor difere do esperado.")

# --- 5. TABELA DE DEBUG (Para ver por que dias ele passou) ---
with st.expander("Verificar Calendário (Debug)"):
    st.write("A contar dias úteis a partir de:", data_inicial)
    st.write("Feriados considerados:", feriados_list)
