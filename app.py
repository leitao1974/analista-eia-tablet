import streamlit as st
import pandas as pd
import numpy as np

# 1. Configuração Básica
st.set_page_config(page_title="Diagnóstico Natal", layout="centered")

st.title("⚠️ DIAGNÓSTICO DE CALENDÁRIO")
st.write("Se está a ler isto, o código carregou corretamente.")

# 2. Definição dos Feriados (Sem Intervalos de Natal)
feriados_nacionais = [
    "2025-06-10", "2025-06-19", "2025-08-15", 
    "2025-10-05", "2025-11-01", "2025-12-01", 
    "2025-12-08", "2025-12-25", "2026-01-01"
]
feriados_np = np.array(feriados_nacionais, dtype='datetime64[D]')

# 3. Teste Específico: 26 de Dezembro de 2025
dia_teste = np.datetime64("2025-12-26") # Sexta-feira
eh_util = np.is_busday(dia_teste, weekmask='1111100', holidays=feriados_np)

st.divider()
st.header("Teste Crítico: 26 de Dezembro de 2025")

if eh_util:
    st.success("✅ O dia 26/12/2025 é considerado DIA ÚTIL.")
    st.write("Conclusão: O sistema NÃO está a aplicar férias judiciais.")
else:
    st.error("❌ O dia 26/12/2025 é considerado FERIADO/SUSPENSÃO.")
    st.write("Conclusão: Algo no seu ambiente Python está a forçar as férias judiciais.")

# 4. Tabela Simples dos Dias de Natal
st.divider()
st.header("Verificação Visual (22 Dez a 02 Jan)")

dias = pd.date_range(start="2025-12-22", end="2026-01-02", freq='D')
dados = []

for d in dias:
    dia_np = np.datetime64(d)
    # Verifica se é dia útil para o numpy
    status_util = np.is_busday(dia_np, weekmask='1111100', holidays=feriados_np)
    
    # Verifica se é fim de semana
    fds = d.weekday() >= 5
    
    estado = "Trabalho"
    if fds: estado = "Fim de Semana"
    elif not status_util: 
        # Se não é FDS e não é útil, é Feriado ou Suspensão
        if str(d.date()) in feriados_nacionais:
            estado = "Feriado Nacional"
        else:
            estado = "ERRO: SUSPENSÃO ATIVA"
            
    dados.append({
        "Data": d.strftime("%d/%m/%Y"),
        "Dia da Semana": d.strftime("%A"),
        "Estado": estado,
        "É Útil?": "Sim" if status_util else "Não"
    })

df = pd.DataFrame(dados)
st.table(df)
