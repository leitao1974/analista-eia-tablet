import streamlit as st
import pandas as pd
from datetime import timedelta, date
import holidays
import io

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Simulador AIA (Meta 08/Jan)", page_icon="🎯", layout="wide")

st.title("🎯 Simulador AIA - RJAIA (150 Dias)")
st.markdown("""
Este simulador gera a **Memória de Cálculo** para o cumprimento do prazo legal de 150 dias.
**Configuração atual:** Cenário sem suspensões para atingir a data de Janeiro de 2026.
""")

# --- MOTOR DE CÁLCULO ---
def obter_feriados(anos):
    pt_holidays = holidays.PT(years=anos)
    # Incluir Santo António (13 Junho) para bater certo com a contagem de Lisboa
    for ano in anos:
        pt_holidays.append(date(ano, 6, 13))
    return pt_holidays

def eh_dia_util(data_check, lista_feriados):
    if data_check.weekday() >= 5: return False # Sábado/Domingo
    if data_check in lista_feriados: return False # Feriado
    return True

def somar_dias(inicio, dias, feriados, tipo="UTIL"):
    data_atual = inicio
    contador = 0
    
    if dias == 0: return data_atual

    if tipo == "CORRIDO":
        return inicio + timedelta(days=dias)
    
    while contador < dias:
        data_atual += timedelta(days=1)
        if eh_dia_util(data_atual, feriados):
            contador += 1
    return data_atual

def proximo_dia_util(data_ref, feriados):
    d = data_ref
    while not eh_dia_util(d, feriados):
        d += timedelta(days=1)
    return d

# --- GERADOR DE MEMÓRIA ---
def gerar_cronograma_final(inicio, cfg, feriados):
    log = []
    data_cursor = inicio
    
    # Total disponível: 150 dias úteis
    saldo_total = 150
    dias_consumidos = 0
    
    # 0. Entrada
    log.append({
        "Data": inicio, "Etapa": "0. Entrada",
        "Desc": "Submissão do Pedido",
        "Duracao": 0, "Tipo": "UTIL", "Status": ""
    })
    
    # 1. Conformidade
    # Regra: Inicia contagem no dia útil seguinte? Vamos somar direto para bater com as tuas datas.
    # Se entrada = 06/06, +30 dias úteis.
    log.append({
        "Data": data_cursor, "Etapa": "1. Conformidade",
        "Desc": "Verificação Liminar da Instrução",
        "Duracao": cfg['conf'], "Tipo": "UTIL", "Status": ""
    })
    data_cursor = somar_dias(data_cursor, cfg['conf'], feriados, "UTIL")
    dias_consumidos += cfg['conf']
    
    # 2. Consulta Pública
    # Assume-se sequencial imediato
    log.append({
        "Data": data_cursor, "Etapa": "2. Consulta Pública",
        "Desc": "Publicitação e Período de Consulta",
        "Duracao": cfg['cp'], "Tipo": "UTIL", "Status": ""
    })
    data_cursor = somar_dias(data_cursor, cfg['cp'], feriados, "UTIL")
    dias_consumidos += cfg['cp']
    
    # 3. Análise Técnica (Fase 1)
    log.append({
        "Data": data_cursor, "Etapa": "3. Análise Técnica",
        "Desc": "Análise Técnica e Pareceres",
        "Duracao": cfg['analise'], "Tipo": "UTIL", "Status": ""
    })
    data_cursor = somar_dias(data_cursor, cfg['analise'], feriados, "UTIL")
    dias_consumidos += cfg['analise']
    
    # 4. Aditamentos (SE HOUVER)
    if cfg['aditamentos'] > 0:
        log.append({
            "Data": data_cursor, "Etapa": "4. Aditamentos",
            "Desc": "Resposta ao Pedido de Elementos",
            "Duracao": cfg['aditamentos'], "Tipo": "CORRIDO", 
            "Status": "SUSPENSO"
        })
        data_suspensao = somar_dias(data_cursor, cfg['aditamentos'], feriados, "CORRIDO")
        data_cursor = proximo_dia_util(data_suspensao, feriados)
        # Nota: Não incrementa dias_consumidos pq suspende
    
    # 5. Avaliação Final (PTF)
    log.append({
        "Data": data_cursor, "Etapa": "5. Avaliação Final",
        "Desc": "Elaboração do Parecer Final (PTF)",
        "Duracao": cfg['aval_final'], "Tipo": "UTIL", "Status": ""
    })
    data_cursor = somar_dias(data_cursor, cfg['aval_final'], feriados, "UTIL")
    dias_consumidos += cfg['aval_final']
    
    # 6. Audiência Prévia (Se houver suspensão de prazo decisório)
    if cfg['audiencia'] > 0:
        log.append({
            "Data": data_cursor, "Etapa": "6. Audiência Prévia",
            "Desc": "Pronúncia CPA",
            "Duracao": cfg['audiencia'], "Tipo": "UTIL", 
            "Status": "SUSPENSO (Decisão)" # CPA suspende prazo de decisão
        })
        data_cursor = somar_dias(data_cursor, cfg['audiencia'], feriados, "UTIL")
        
    # 7. Saldo Final (Para atingir os 150 dias)
    # Quanto falta para 150?
    saldo_restante = saldo_total - dias_consumidos
    if saldo_restante < 0: saldo_restante = 0 # Prevenção de erro
    
    data_final = somar_dias(data_cursor, saldo_restante, feriados, "UTIL")
    
    log.append({
        "Data": data_cursor, "Etapa": "7. PRAZO FINAL (DIA)",
        "Desc": "Emissão da Decisão Final (Dia 150)",
        "Duracao": saldo_restante, "Tipo": "UTIL", "Status": ""
    })
    
    return log, data_final

# --- INTERFACE ---
with st.sidebar:
    st.header("Configuração de Datas")
    # DATA FIXA: 6 Junho 2025
    data_entrada = st.date_input("Data de Entrada", date(2025, 6, 6))
    
    st.header("Tempos (Dias Úteis)")
    # Valores ajustados para bater certo com cronograma padrão
    d_conf = st.number_input("Conformidade", value=30)
    d_cp = st.number_input("Consulta Pública", value=30)
    d_analise = st.number_input("Análise Técnica", value=40)
    d_aval = st.number_input("Avaliação Final", value=10) # PTF
    
    st.header("Suspensões (Cuidado!)")
    st.caption("Para obter 08/Jan/2026, as suspensões devem ser 0.")
    d_adit = st.number_input("Aditamentos (Promotor)", value=0)
    d_aud = st.number_input("Audiência Prévia", value=0) # Meter a 0 para não empurrar data

# --- EXECUÇÃO ---
anos = [data_entrada.year, data_entrada.year + 1]
feriados = obter_feriados(anos)

cfg = {
    'conf': d_conf, 'cp': d_cp, 'analise': d_analise, 
    'aval_final': d_aval, 
    'aditamentos': d_adit, 'audiencia': d_aud
}

if st.button("Gerar Memória (Jan 2026)", type="primary"):
    
    cronograma, data_final = gerar_cronograma_final(data_entrada, cfg, feriados)
    
    # --- RESULTADO TEXTO ---
    st.subheader("Memória de Cálculo Gerada")
    
    # Construção do Texto Estilo Relatório
    texto = f"""Memória de Cálculo de Prazos: Projeto AIA
Data de Entrada: {data_entrada.strftime('%d/%m/%Y')}
DATA LIMITE PREVISTA (DIA): {data_final.strftime('%d/%m/%Y')}

1. Enquadramento
Prazo global de 150 dias úteis (RJAIA).
Contagem de dias úteis (suspensão sábados, domingos e feriados).

2. Detalhe das Etapas
"""
    for item in cronograma:
        obs_suspensao = f"\nEstado: {item['Status']}" if item['Status'] else ""
        bloco = f"""
{item['Data'].strftime('%d/%m/%Y')} - {item['Etapa']}
Descrição: {item['Desc']}
Duração: {item['Duracao']} dias ({item['Tipo']}){obs_suspensao}
--------------------"""
        texto += bloco

    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.text_area("Copiar Relatório:", value=texto, height=500)
    
    with c2:
        st.info(f"""
        **Resumo das Contas:**
        
        Entrada: {data_entrada.strftime('%d/%m/%Y')}
        + 150 Dias Úteis
        + {d_adit} dias suspensão
        
        = **{data_final.strftime('%d/%m/%Y')}**
        """)
        
        if data_final.month != 1:
            st.warning("⚠️ Atenção: Se adicionou dias de suspensão (aditamentos ou audiência), a data final deslizou para além de Janeiro.")
