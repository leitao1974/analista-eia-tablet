import streamlit as st
import pandas as pd
import numpy as np

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Diagnóstico Cloud", layout="centered")
st.title("☁️ DIAGNÓSTICO: Streamlit Cloud")

# --- DEFINIÇÃO DE FERIADOS (Manual) ---
# Isto garante que não há lixo de outras bibliotecas
feriados_nacionais = [
    "2025-06-10", "2025-06-19", "2025-08-15", 
    "2025-10-05", "2025-11-01", "2025-12-01", 
    "2025-12-08", "2025-12-25", "2026-01-01"
]
feriados_np = np.array(feriados_nacionais, dtype='datetime64[D]')

# --- TESTE DO DIA 26 DE DEZEMBRO ---
st.write("A verificar o calendário do servidor...")
dia_teste = np.datetime64("2025-12-26") # Sexta-feira
eh_util = np.is_busday(dia_teste, weekmask='1111100', holidays=feriados_np)

st.divider()

if eh_util:
    st.success("✅ SUCESSO: O dia 26/12/2025 é DIA ÚTIL.")
    st.markdown("""
    **O que isto significa:**
    O ambiente está limpo. Se calcularmos 150 dias agora, vai dar 08/01/2026.
    """)
else:
    st.error("❌ ERRO: O dia 26/12/2025 está marcado como FERIADO.")
    st.markdown("""
    **O que isto significa:**
    O servidor da Streamlit Cloud tem alguma configuração que está a forçar férias judiciais.
    """)
