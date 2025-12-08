import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta

st.set_page_config(page_title="Auditoria de Prazos AIA", layout="wide")

st.title("🛡️ Calculadora AIA: Auditoria de Calendário")

# --- 1. DEFINIÇÃO BLINDADA DE FERIADOS ---
# Definimos isto DENTRO da função para garantir que não há cache
def get_feriados_apenas_nacionais():
    return [
        "2025-06-10", "2025-06-19", "2025-08-15", 
        "2025-10-05", "2025-11-01", "2025-12-01", 
        "2025-12-08", 
        "2025-12-25", # <--- ÚNICO dia parado no Natal
        "2026-01-01", 
        "2026-04-03", "2026-04-25", "2026-05-01"
    ]

feriados_lista = get_feriados_apenas_nacionais()
feriados_np = np.array(feriados_lista, dtype='datetime64[D]')

# --- 2. INPUTS ---
col1, col2, col3 = st.columns(3)
with col1:
    data_inicio = st.date_input("Início", value=date(2025, 6, 3))
with col2:
    prazo = st.number_input("Prazo (Dias Úteis)", value=150)
with col3:
    # Dados para bater certo com o seu relatório (Real)
    suspensao_corrida = 45
    suspensao_util = 10

# --- 3. CÁLCULO TEÓRICO (PROVA DOS NOVE) ---
# Vamos forçar o Numpy a ignorar tudo o que não seja fds ou a lista acima
try:
    # busday_offset conta X dias úteis para a frente
    dia_final_teorico_np = np.busday_offset(
        np.datetime64(data_inicio), 
        prazo, 
        roll='forward', 
        weekmask='1111100', 
        holidays=feriados_np
    )
    data_teorica = pd.to_datetime(dia_final_teorico_np).date()
except Exception as e:
    st.error(f"Erro de cálculo: {e}")
    st.stop()

# --- 4. CÁLCULO REAL (BASEADO NO RELATÓRIO) ---
# Lógica: 150 úteis + 45 corridos de paragem + 10 úteis de paragem
# Aproximação sequencial conforme o seu PDF
# 1. Avança 60 dias úteis
step1 = np.busday_offset(np.datetime64(data_inicio), 60, roll='forward', weekmask='1111100', holidays=feriados_np)
# 2. Pára 45 dias corridos
step2 = pd.to_datetime(step1).date() + timedelta(days=suspensao_corrida)
# 3. Avança 20 dias úteis
step3 = np.busday_offset(np.datetime64(step2), 20, roll='forward', weekmask='1111100', holidays=feriados_np)
# 4. Pára 10 dias úteis (Audiência)
step4 = np.busday_offset(step3, suspensao_util, roll='forward', weekmask='1111100', holidays=feriados_np)
# 5. Termina os restantes 70 dias (150 - 60 - 20 = 70)
final_real_np = np.busday_offset(step4, 70, roll='forward', weekmask='1111100', holidays=feriados_np)
data_real = pd.to_datetime(final_real_np).date()


# --- 5. RESULTADOS ---
st.divider()
c1, c2, c3 = st.columns(3)

with c1:
    st.subheader("Data Real (Com Suspensões)")
    st.metric("Prevista", data_real.strftime("%d/%m/%Y"))
    if data_real.strftime("%d/%m/%Y") == "06/03/2026":
        st.success("✅ Igual ao Relatório PDF")

with c2:
    st.subheader("Data Teórica (Sem Suspensões)")
    val_teorica = data_teorica.strftime("%d/%m/%Y")
    st.metric("150 dias úteis diretos", val_teorica)
    
    if val_teorica == "08/01/2026":
        st.success("✅ CORRETO (08/01/2026)")
    elif val_teorica == "22/01/2026":
        st.error("❌ ERRO CRÍTICO: 22/01/2026")
        st.markdown("**Diagnóstico:** O sistema está a contar férias judiciais.")

with c3:
    st.subheader("Derrapagem")
    diff = (data_real - data_teorica).days
    st.metric("Impacto Temporal", f"+ {diff} dias")

# --- 6. AUDITORIA VISUAL (A PROVA) ---
st.write("---")
st.header("🕵️ Auditoria Forense: O Natal de 2025")
st.write("Verifique abaixo se o sistema está a marcar os dias 26, 29 e 30 de Dezembro como 'Trabalho' ou 'Feriado'.")

# Criar calendário de Dezembro 2025 para verificar
dias_audit = pd.date_range(start="2025-12-20", end="2026-01-05", freq='D')
audit_data = []

for d in dias_audit:
    dia_np = np.datetime64(d)
    eh_fds = pd.to_datetime(d).weekday() >= 5
    eh_feriado_lista = d.strftime("%Y-%m-%d") in feriados_lista
    # O busday verifica se é dia útil
    eh_util = np.is_busday(dia_np, weekmask='1111100', holidays=feriados_np)
    
    status = "✅ TRABALHO"
    if eh_fds: status = "⏹️ Fim de Semana"
    if eh_feriado_lista: status = "🔴 Feriado Nacional"
    if not eh_util and not eh_fds and not eh_feriado_lista:
        status = "⚠️ SUSPENSÃO JUDICIAL (O ERRO ESTÁ AQUI)"
    
    audit_data.append({
        "Data": d.strftime("%d/%m/%Y"),
        "Dia da Semana": d.strftime("%A"),
        "Status no Sistema": status
    })

df_audit = pd.DataFrame(audit_data)

# Aplicar cor para destacar o erro
def color_coding(row):
    val = row['Status no Sistema']
    if "SUSPENSÃO" in val:
        return ['background-color: red; color: white'] * len(row)
    elif "TRABALHO" in val:
        return ['background-color: #d4edda; color: green'] * len(row)
    elif "Feriado" in val:
        return ['background-color: #f8d7da; color: darkred'] * len(row)
    return [''] * len(row)

st.table(df_audit.style.apply(color_coding, axis=1))

st.info("Se vir linhas vermelhas a dizer 'SUSPENSÃO JUDICIAL' entre o dia 22 e 31 de Dezembro, significa que existe alguma biblioteca ou configuração oculta a forçar feriados.")
