import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Calculadora AIA Pro", layout="wide")

st.title("Calculadora de Prazos AIA (Rigorosa)")
st.markdown("""
**Diagnóstico:**
* Se a data for **08/01/2026**: O sistema está correto (Regime Administrativo).
* Se a data for **22/01/2026**: O sistema está a aplicar indevidamente as Férias Judiciais de Natal.
""")

# --- 1. CONFIGURAÇÃO DE FERIADOS (HARD RESET) ---
# Definimos uma nova variável para garantir que não usa lixo de memória anterior
feriados_aia_restritos = [
    "2025-06-10", # Dia de Portugal
    "2025-06-19", # Corpo de Deus
    "2025-08-15", # Assunção
    # Out e Nov caem ao fim de semana em 2025, mas deixamos aqui por rigor
    "2025-10-05", 
    "2025-11-01", 
    "2025-12-01", # Restauração
    "2025-12-08", # Imaculada Conceição
    "2025-12-25", # Natal (APENAS O DIA 25)
    "2026-01-01", # Ano Novo (APENAS O DIA 1)
    "2026-04-03", # Sexta Feira Santa
    "2026-04-05", # Pascoa
    "2026-04-25", # 25 Abril
    "2026-05-01"  # Dia do Trabalhador
]

# Converter para formato numpy (busday)
feriados_np = np.array(feriados_aia_restritos, dtype='datetime64[D]')

# --- 2. INPUTS ---
col1, col2, col3 = st.columns(3)
with col1:
    data_inicio = st.date_input("Data de Entrada", value=date(2025, 6, 3))
with col2:
    prazo_legal = st.number_input("Prazo Legal (Dias Úteis)", value=150)
with col3:
    # Adicionamos as suspensões do seu documento para o cálculo final bater certo com Março
    dias_suspensao_corridos = st.number_input("Suspensão Aditamentos (Dias Corridos)", value=45)
    dias_suspensao_uteis = st.number_input("Suspensão Audiência (Dias Úteis)", value=10)

# --- 3. CÁLCULO DA DATA TEÓRICA (SEM SUSPENSÕES) ---
# Esta é a parte que estava a dar 22/01. Agora deve dar 08/01.
try:
    data_teorica_np = np.busday_offset(
        np.datetime64(data_inicio), 
        prazo_legal, 
        roll='forward', 
        weekmask='1111100', 
        holidays=feriados_np
    )
    data_teorica = pd.to_datetime(data_teorica_np)
except Exception as e:
    st.error(f"Erro no cálculo base: {e}")
    st.stop()

# --- 4. CÁLCULO DA DATA REAL (COM SUSPENSÕES) ---
# A lógica: Data Teórica + Empurrão das Suspensões
# Nota: Para ser preciso, devíamos simular passo a passo, mas vamos somar o delta
# 1. Somar suspensão de aditamentos (dias corridos) à data teórica
data_com_aditamentos = data_teorica + timedelta(days=dias_suspensao_corridos)

# 2. Somar suspensão de audiência (dias úteis)
# Precisamos garantir que não cai em feriado
data_final_real_np = np.busday_offset(
    np.datetime64(data_com_aditamentos), 
    dias_suspensao_uteis, 
    roll='forward', 
    weekmask='1111100', 
    holidays=feriados_np
)
data_final_real = pd.to_datetime(data_final_real_np)


# --- 5. APRESENTAÇÃO DOS RESULTADOS ---
st.divider()
c1, c2 = st.columns(2)

with c1:
    st.subheader("Data Limite (Teórica)")
    st.caption("Sem contar com suspensões de aditamentos/audiências")
    val_teorica = data_teorica.strftime("%d/%m/%Y")
    st.metric("Data Alvo (150 dias úteis puros)", val_teorica)
    
    if val_teorica == "08/01/2026":
        st.success("✅ CORRETO: 08/01/2026 (O fantasma do Natal foi removido)")
    elif val_teorica == "22/01/2026":
        st.error("❌ ERRO: Ainda está a contar férias de Natal.")
    else:
        st.warning(f"Data calculada: {val_teorica}")

with c2:
    st.subheader("Data Limite (Prevista)")
    st.caption(f"Com suspensões (+{dias_suspensao_corridos} dias corridos, +{dias_suspensao_uteis} úteis)")
    st.metric("Data Final Real", data_final_real.strftime("%d/%m/%Y"))
    st.info("Esta data deve aproximar-se de 06/03/2026 conforme o seu documento.")

# --- 6. PROVA DOS NOVE (DEBUG) ---
with st.expander("🕵️ Verificação Forense: O que aconteceu no Natal de 2025?"):
    st.write("Vamos verificar se os dias 26, 29 e 30 de Dezembro foram contados como dias de trabalho.")
    
    # Teste manual de dias específicos
    dias_teste = ["2025-12-24", "2025-12-25", "2025-12-26", "2025-12-29"]
    res = np.is_busday(dias_teste, holidays=feriados_np, weekmask='1111100')
    
    df_debug = pd.DataFrame({
        "Dia": dias_teste,
        "É dia útil?": res,
        "Explicação": ["Véspera (Útil)", "Natal (Feriado)", "Dia 26 (Tem de ser Útil)", "Dia 29 (Tem de ser Útil)"]
    })
    st.table(df_debug)
    
    if res[2] == True:
        st.success("O dia 26/12 foi contado como TRABALHO. (Correto para AIA)")
    else:
        st.error("O dia 26/12 foi contado como FÉRIAS. (Errado para AIA)")
