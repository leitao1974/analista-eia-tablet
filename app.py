import streamlit as st
import pandas as pd
from datetime import timedelta, date
import holidays
import io

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Memória de Cálculo AIA", page_icon="📝", layout="wide")

st.title("📝 Gerador de Memória de Cálculo: RJAIA")
st.markdown("""
Este simulador replica a estrutura da **Memória de Cálculo**.
O cálculo é feito somando os dias gastos e projetando o **saldo restante** dos 150 dias no final.
""")

# --- MOTOR DE CÁLCULO ---
def obter_feriados(anos, incluir_lisboa=True):
    pt_holidays = holidays.PT(years=anos)
    # Para bater certo com o seu exemplo (03/06 a 18/06 = 10 dias úteis), 
    # é necessário excluir o 13 de Junho (Santo António) e o 10 (Portugal).
    if incluir_lisboa:
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
    
    # Se forem 0 dias, retorna a própria data
    if dias == 0: return data_atual

    if tipo == "CORRIDO":
        return inicio + timedelta(days=dias)
    
    # Lógica de Dias Úteis
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

# --- FUNÇÃO PRINCIPAL ---
def calcular_memoria(inicio, cfg, feriados):
    log = []
    
    # Variáveis de Estado
    data_cursor = inicio
    saldo_total = 150
    dias_consumidos = 0
    
    # 0. Entrada
    log.append({
        "Data": inicio,
        "Etapa": "0. Entrada",
        "Desc": "Submissão do Pedido",
        "Duracao": 0,
        "Tipo": "UTIL",
        "Status": "Ativo"
    })
    
    # 1. Conformidade (Consome Prazo)
    log.append({
        "Data": data_cursor,
        "Etapa": "1. Conformidade",
        "Desc": "Verificação Liminar da Instrução",
        "Duracao": cfg['conf'],
        "Tipo": "UTIL",
        "Status": "Ativo"
    })
    # Avança cursor
    data_cursor = somar_dias(data_cursor, cfg['conf'], feriados, "UTIL")
    dias_consumidos += cfg['conf']

    # 2. Consulta Pública (Consome Prazo)
    # Inicia no dia seguinte à conformidade? No seu exemplo: 
    # Entrada 03/06 -> Fim Conf 17/06 (10 dias) -> Início CP 18/06.
    # O cursor já está em 17/06. Se CP começa a 18/06, é +1 dia se for sequencial imediato.
    # Vamos assumir sequencial imediato (Next Business Day se necessário)
    
    # No seu texto: 18/06. O meu cursor (somar 10 uteis a 03/06) dá 18/06 se contar 13/06 como feriado.
    # Se somar_dias retorna o último dia do prazo ou o dia alvo? Retorna o dia alvo.
    
    log.append({
        "Data": data_cursor,
        "Etapa": "2. Consulta Pública",
        "Desc": "Publicitação e Período de Consulta",
        "Duracao": cfg['cp'],
        "Tipo": "UTIL",
        "Status": "Ativo"
    })
    data_cursor = somar_dias(data_cursor, cfg['cp'], feriados, "UTIL")
    dias_consumidos += cfg['cp']
    
    # 3. Análise I (Consome Prazo)
    log.append({
        "Data": data_cursor,
        "Etapa": "3. Análise I",
        "Desc": "Análise Pós-CP e Pedido de AI",
        "Duracao": cfg['analise1'],
        "Tipo": "UTIL",
        "Status": "Ativo"
    })
    data_cursor = somar_dias(data_cursor, cfg['analise1'], feriados, "UTIL")
    dias_consumidos += cfg['analise1']
    
    # 4. Aditamentos (SUSPENSO - Dias Corridos)
    # Nota: No seu exemplo a data avança (29/08 -> 13/10) mas o prazo admin (dias uteis do RJAIA) congela.
    log.append({
        "Data": data_cursor,
        "Etapa": "4. Aditamentos",
        "Desc": "Resposta ao Pedido de Elementos",
        "Duracao": cfg['aditamentos'],
        "Tipo": "CORRIDO",
        "Status": "SUSPENSO"
    })
    # Avança data cronológica mas NÃO incrementa dias_consumidos
    data_fim_suspensao = somar_dias(data_cursor, cfg['aditamentos'], feriados, "CORRIDO")
    # O dia de reinício deve ser um dia útil
    data_cursor = proximo_dia_util(data_fim_suspensao, feriados)
    
    # 5. Avaliação Técnica (Consome Prazo)
    log.append({
        "Data": data_cursor,
        "Etapa": "5. Avaliação Técnica",
        "Desc": "Elaboração do Parecer Final",
        "Duracao": cfg['aval_tec'],
        "Tipo": "UTIL",
        "Status": "Ativo"
    })
    data_cursor = somar_dias(data_cursor, cfg['aval_tec'], feriados, "UTIL")
    dias_consumidos += cfg['aval_tec']
    
    # 6. Audiência Prévia (SUSPENSO - Dias Úteis CPA)
    # O CPA suspende o prazo de decisão durante a audiência.
    log.append({
        "Data": data_cursor,
        "Etapa": "6. Audiência Prévia",
        "Desc": "Pronúncia em sede de CPA",
        "Duracao": cfg['audiencia'],
        "Tipo": "UTIL",
        "Status": "SUSPENSO"
    })
    data_cursor = somar_dias(data_cursor, cfg['audiencia'], feriados, "UTIL")
    # Não soma a dias_consumidos (está suspenso)
    
    # 7. TERMO DO PRAZO (O Saldo)
    saldo_restante = saldo_total - dias_consumidos
    
    # Calcular data final
    data_final = somar_dias(data_cursor, saldo_restante, feriados, "UTIL")
    
    log.append({
        "Data": data_cursor,
        "Etapa": "7. TERMO DO PRAZO (DIA)",
        "Desc": "Data Limite para Emissão da Decisão",
        "Duracao": saldo_restante,
        "Tipo": "UTIL",
        "Status": "Ativo"
    })
    
    return log, data_final

# --- INTERFACE ---
with st.sidebar:
    st.header("1. Dados do Projeto")
    data_entrada = st.date_input("Data de Entrada", date(2025, 6, 3))
    
    st.header("2. Durações (Dias Úteis)")
    d_conf = st.number_input("1. Conformidade", value=10)
    d_cp = st.number_input("2. Consulta Pública", value=35)
    d_analise1 = st.number_input("3. Análise I", value=15)
    
    st.header("3. Suspensões")
    d_adit = st.number_input("4. Aditamentos (Dias Corridos)", value=45)
    d_aval = st.number_input("5. Avaliação Técnica (Dias Úteis)", value=20)
    d_aud = st.number_input("6. Audiência Prévia (Dias Úteis)", value=10)

    st.markdown("---")
    feriados_lisboa = st.checkbox("Incluir Feriado Lisboa (13 Jun)", value=True, help="Essencial para bater certo com o exemplo do dia 18/06")

# --- EXECUÇÃO ---
anos = [data_entrada.year, data_entrada.year + 1]
feriados = obter_feriados(anos, feriados_lisboa)

cfg = {
    'conf': d_conf, 'cp': d_cp, 'analise1': d_analise1,
    'aditamentos': d_adit, 'aval_tec': d_aval, 'audiencia': d_aud
}

if st.button("Gerar Memória de Cálculo", type="primary"):
    
    logs, data_final = calcular_memoria(data_entrada, cfg, feriados)
    
    # --- VISUALIZAÇÃO TEXTO PURO (Igual ao seu exemplo) ---
    st.subheader("Resultado Gerado")
    
    # Construção do Texto
    texto_final = f"""Memória de Cálculo de Prazos: Simulação
Exemplo
Data de Simulação: {date.today().strftime('%d/%m/%Y')}
DATA LIMITE PREVISTA (DIA): {data_final.strftime('%d/%m/%Y')}

1. Enquadramento Legal
A presente calendarização foi elaborada considerando o prazo global de 150 dias úteis...
(Suspensão aos fins de semana, feriados e períodos do promotor).

2. Detalhe das Etapas
"""
    for item in logs:
        tipo_str = "Uteis" if item['Tipo'] == "UTIL" else "Corridos"
        status_line = ""
        if item['Status'] == "SUSPENSO":
            status_line = "\nEstado do Prazo Administrativo: SUSPENSO"
            
        bloco = f"""
{item['Data'].strftime('%d/%m/%Y')} - {item['Etapa']}
Descrição: {item['Desc']}
Duração considerada: {item['Duracao']} dias ({tipo_str}){status_line}
--------------------"""
        texto_final += bloco

    # Exibir texto copiável
    st.text_area("Copie o resultado abaixo:", value=texto_final, height=600)
    
    # --- VISUALIZAÇÃO TABELA ---
    with st.expander("Ver Tabela Resumo"):
        df = pd.DataFrame(logs)
        df['Data'] = df['Data'].apply(lambda x: x.strftime('%d/%m/%Y'))
        st.table(df[['Data', 'Etapa', 'Duracao', 'Status']])
