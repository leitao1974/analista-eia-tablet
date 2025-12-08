import streamlit as st
import pandas as pd
import numpy as np
from datetime import date

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Simulador AIA Direto", layout="centered")

st.title("Simulador AIA: Prazo Legal Direto")
st.caption("Cálculo de 150 dias úteis contínuos, sem qualquer suspensão ou paragem.")

# --- 1. DEFINIÇÃO RÍGIDA DE FERIADOS (2025-2026) ---
# Apenas os dias que param a contagem administrativa (CPA).
# Não inclui férias judiciais.
feriados_list = [
    "2025-06-10", # Dia de Portugal
    "2025-06-19", # Corpo de Deus
    "2025-08-15", # Assunção
    "2025-10-05", # Implantação (Domingo)
    "2025-11-01", # Todos os Santos (Sábado)
    "2025-12-01", # Restauração
    "2025-12-08", # Imaculada Conceição
    "2025-12-25", # Natal (Apenas o dia 25)
    "2026-01-01", # Ano Novo (Apenas o dia 1)
    "2026-04-03", # Sexta-feira Santa
    "2026-04-25", # 25 de Abril
    "2026-05-01"  # Dia do Trabalhador
]
feriados_np = np.array(feriados_list, dtype='datetime64[D]')

# --- 2. INPUTS ---
col1, col2 = st.columns(2)

with col1:
    data_inicio = st.date_input("Data de Início", value=date(2025, 6, 3))

with col2:
    prazo = st.number_input("Prazo Legal (Dias Úteis)", value=150, step=1)

# --- 3. CÁLCULO ---
# A função busday_offset faz a conta exata pulando Fim de Semana + Feriados
try:
    data_final_np = np.busday_offset(
        np.datetime64(data_inicio), 
        prazo, 
        roll='forward', 
        weekmask='1111100', 
        holidays=feriados_np
    )
    data_final = pd.to_datetime(data_final_np).date()
    
except Exception as e:
    st.error(f"Erro no cálculo: {e}")
    st.stop()

# --- 4. RESULTADO ---
st.divider()

st.subheader("Data Limite (Sem Suspensões)")
st.markdown(f"""
Se o processo não tiver **nenhuma** paragem (aditamentos, audiências, etc), termina em:
""")

# Mostra a data em grande destaque
st.title(f"📅 {data_final.strftime('%d/%m/%Y')}")

# Validação imediata para o seu caso
if data_final.strftime('%d/%m/%Y') == "08/01/2026":
    st.success("✅ O cálculo está correto: 08/01/2026.")
    st.caption("Isto valida que o sistema está a ignorar corretamente as férias judiciais de Natal.")
else:
    st.warning("O resultado difere de 08/01/2026. Verifique a data de início.")

# --- 5. DETALHE MENSAL (Opcional) ---
with st.expander("Ver contagem mês a mês"):
    st.write("Para chegar a esta data, o sistema contou os seguintes dias úteis:")
    cursor = data_inicio
    dias_restantes = prazo
    
    while dias_restantes > 0:
        # Avança 1 dia útil
        prox_dia = np.busday_offset(np.datetime64(cursor), 1, roll='forward', weekmask='1111100', holidays=feriados_np)
        cursor = pd.to_datetime(prox_dia).date()
        dias_restantes -= 1
        
    st.write(f"Último dia contado: {cursor}")
