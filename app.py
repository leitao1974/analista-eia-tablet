import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta

# --- 1. CONFIGURAÇÃO DA PÁGINA (Tem de ser a primeira linha) ---
st.set_page_config(page_title="Auditoria AIA", layout="wide")

st.title("🛡️ Calculadora e Auditoria AIA")

# --- 2. DEFINIÇÃO DE FERIADOS (SEM NATAL) ---
feriados_nacionais = [
    "2025-06-10", "2025-06-19", "2025-08-15", 
    "2025-10-05", "2025-11-01", "2025-12-01", 
    "2025-12-08", "2025-12-25", # Só dia 25
    "2026-01-01", # Só dia 1
    "2026-04-03", "2026-04-25", "2026-05-01"
]
feriados_np = np.array(feriados_nacionais, dtype='datetime64[D]')

# --- 3. INPUTS ---
col_in1, col_in2 = st.columns(2)
with col_in1:
    data_inicio = st.date_input("Data de Início", value=date(2025, 6, 3))
with col_in2:
    prazo = st.number_input("Prazo Legal (Dias Úteis)", value=150)

st.divider()

# --- 4. AUDITORIA FORENSE (AGORA NO TOPO) ---
st.header("1. Auditoria do Calendário (Natal 2025)")
st.caption("Verifique aqui se o Natal está a ser contado como Férias ou Trabalho.")

# Criar calendário de teste (22 Dez a 2 Jan)
dias_teste = pd.date_range(start="2025-12-22", end="2026-01-02", freq='D')
audit_data = []

for d in dias_teste:
    dia_np = np.datetime64(d)
    eh_fds = d.weekday() >= 5 # 5=Sábado, 6=Domingo
    eh_feriado = d.strftime("%Y-%m-%d") in feriados_nacionais
    
    # O busday verifica se é dia útil para o cálculo
    eh_util_calculo = np.is_busday(dia_np, weekmask='1111100', holidays=feriados_np)
    
    status = "✅ TRABALHO (Conta)"
    cor = "background-color: #d4edda; color: green" # Verde
    
    if eh_fds: 
        status = "⏹️ Fim de Semana"
        cor = "background-color: #e2e3e5; color: black" # Cinza
    elif eh_feriado: 
        status = "🔴 Feriado Nacional"
        cor = "background-color: #f8d7da; color: darkred" # Vermelho
    elif not eh_util_calculo:
        # Se não é FDS nem Feriado, mas o sistema diz que NÃO é útil -> ERRO!
        status = "⚠️ SUSPENSÃO (ERRO)"
        cor = "background-color: red; color: white; font-weight: bold"
    
    audit_data.append({
        "Data": d.strftime("%d/%m/%Y"),
        "Dia da Semana": d.strftime("%A"),
        "Status": status,
        "_style": cor 
    })

df_audit = pd.DataFrame(audit_data)

# Função para pintar a tabela
def style_audit(row):
    return [row['_style']] * len(row)

# Mostrar tabela
st.dataframe(df_audit.style.apply(style_audit, axis=1), use_container_width=True)

# --- 5. RESULTADOS DO CÁLCULO ---
st.header("2. Cálculo do Prazo Final")

# Cálculo Teórico
try:
    fim_np = np.busday_offset(
        np.datetime64(data_inicio), 
        prazo, 
        roll='forward', 
        weekmask='1111100', 
        holidays=feriados_np
    )
    data_final = pd.to_datetime(fim_np).date()
    
    st.subheader(f"Data Limite (Sem Suspensões): {data_final.strftime('%d/%m/%Y')}")
    
    if data_final.strftime('%d/%m/%Y') == "08/01/2026":
        st.success("✅ O resultado está CORRETO (08/01/2026).")
    else:
        st.error(f"❌ O resultado {data_final.strftime('%d/%m/%Y')} está ERRADO.")
        if "SUSPENSÃO" in df_audit['Status'].values:
            st.warning("O erro deve-se às linhas vermelhas na tabela acima (Férias Judiciais ativas).")

except Exception as e:
    st.error(f"Erro: {e}")
