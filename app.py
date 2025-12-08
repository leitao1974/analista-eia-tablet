import streamlit as st
import pandas as pd
import datetime
from datetime import timedelta, date
import holidays
import io
from docx import Document
from docx.shared import Pt, RGBColor

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Simulador AIA (Calibrado)", page_icon="📊", layout="wide")

st.title("📊 Simulador de Prazos AIA (Calibrado c/ Excel)")
st.markdown("""
Modelo afinado com base nos dados reais do ficheiro **Processo_PrazosV6**.
Define marcos intermédios críticos: **Envio do PTF** e **Início da Audiência de Interessados**.
""")

# --- FUNÇÕES UTILITÁRIAS ---
def obter_feriados_pt(anos):
    return holidays.PT(years=anos)

def eh_dia_util(data_check, lista_feriados):
    if data_check.weekday() >= 5: return False
    if data_check in lista_feriados: return False
    return True

def proximo_dia_util(data_ref, lista_feriados):
    data_calc = data_ref
    while not eh_dia_util(data_calc, lista_feriados):
        data_calc += timedelta(days=1)
    return data_calc

def somar_dias_uteis(data_inicio, dias_a_adicionar, lista_feriados):
    data_atual = data_inicio
    dias_adicionados = 0
    while dias_adicionados < dias_a_adicionar:
        data_atual += timedelta(days=1)
        if eh_dia_util(data_atual, lista_feriados):
            dias_adicionados += 1
    return data_atual

# --- REGRAS CALIBRADAS (COM BASE NO SEU EXCEL) ---
# A lógica aqui é: Conformidade + Prep CP + CP + (Analise Técnica) = Data PTF
# Depois: Data PTF + (Revisão) = Data Audiência
# Depois: Data Audiência + 10 dias CPA + (Decisão) = Data Final
REGRAS = {
    "Cenário Geral (150 Dias)": {
        "prazo_global": 150,
        "fase_conformidade": 30,      # Excel: Limite Conformidade (30 dias)
        "prep_cp": 5,                 # Excel: Até 5 dias após conf.
        "consulta_publica": 30,       # Lei
        "analise_pos_cp": 20,         # Ajuste para bater no Dia 85 (Envio PTF)
        "revisao_interna": 15,        # Ajuste para bater no Dia 100 (Início Audiência)
        "audiencia_prazo": 10,        # CPA
        "prazo_final_decisao": 40,    # O que sobra para o Dia 150
        "desc": "Projetos Infraestruturas/Serviços. Marcos: PTF ao dia 85; Audiência ao dia 100."
    },
    "Cenário Indústria/PIN (90 Dias)": {
        "prazo_global": 90,
        "fase_conformidade": 20,      # Excel: Limite Conformidade (20 dias)
        "prep_cp": 5,
        "consulta_publica": 30,
        "analise_pos_cp": 10,         # Ajuste para bater no Dia 65 (Envio PTF)
        "revisao_interna": 5,         # Ajuste para bater no Dia 70 (Início Audiência)
        "audiencia_prazo": 10,
        "prazo_final_decisao": 10,    # O que sobra para o Dia 90
        "desc": "Projetos SIR/PIN. Marcos: PTF ao dia 65; Audiência ao dia 70."
    }
}

# --- GERADOR DE RELATÓRIO WORD ---
def gerar_relatorio_word(cronograma, nome_projeto, regra_nome, data_final):
    doc = Document()
    style = doc.styles['Title']
    style.font.size = Pt(16)
    
    doc.add_heading(f'Cronograma AIA: {nome_projeto}', 0)
    doc.add_paragraph(f"Cenário Base: {regra_nome}")
    
    p = doc.add_paragraph()
    run = p.add_run(f"DATA LIMITE PREVISTA: {data_final}")
    run.bold = True
    run.font.color.rgb = RGBColor(200, 0, 0)
    
    # Tabela no Word
    table = doc.add_table(rows=1, cols=4)
    table.style = 'Table Grid'
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = 'Data'
    hdr_cells[1].text = 'Dia (Admin)'
    hdr_cells[2].text = 'Fase'
    hdr_cells[3].text = 'Responsável'
    
    for item in cronograma:
        row_cells = table.add_row().cells
        row_cells[0].text = item['Data Estimada'].strftime('%d/%m/%Y')
        row_cells[1].text = str(item['Dia Admin'])
        row_cells[2].text = item['Fase']
        row_cells[3].text = item['Responsável']
        
    doc.add_paragraph("\nNota: Os prazos indicados como 'SUSPENSO' referem-se a períodos da responsabilidade do proponente ou trâmites externos.")
    return doc

# --- MOTOR DE CÁLCULO ---
def calcular_cronograma(data_inicio, regra, dias_suspensao, feriados):
    cronograma = []
    data_atual = data_inicio
    dias_admin = 0
    
    # Função interna de registo
    def add_line(fase, resp, desc, dias, tipo="UTIL", destaque=False):
        nonlocal data_atual, dias_admin
        
        cronograma.append({
            "Data Estimada": data_atual,
            "Dia Admin": dias_admin if resp != "PROMOTOR" else "SUSPENSO",
            "Fase": fase,
            "Responsável": resp,
            "Descrição": desc,
            "Duração": f"{dias} dias ({'Uteis' if tipo=='UTIL' else 'Corridos'})",
            "Destaque": destaque
        })
        
        if tipo == "UTIL":
            data_atual = somar_dias_uteis(data_atual, dias, feriados)
            if resp != "PROMOTOR": dias_admin += dias
        else:
            data_fim = data_atual + timedelta(days=dias)
            data_atual = proximo_dia_util(data_fim, feriados)

    # --- EXECUÇÃO PASSO A PASSO (Igual ao Excel) ---
    
    # 0. Início
    add_line("0. Entrada", "Promotor", "Submissão", 0)
    
    # 1. Conformidade (Calibrado: 30 ou 20 dias)
    add_line("1. Conformidade", "Autoridade", "Instrução e Reunião CA", regra['fase_conformidade'])
    
    # 2. Prep CP
    add_line("2. Prep. CP", "Autoridade", "Até 5 dias após conformidade", regra['prep_cp'])
    
    # 3. Consulta Pública
    add_line("3. Consulta Pública", "Autoridade", "Período Legal", regra['consulta_publica'])
    
    # 4. Suspensão (Aditamentos) - Inserida aqui por ser o padrão, mas ajustável
    add_line("4. Suspensão (Aditamentos)", "PROMOTOR", "Resposta a Pedido de Elementos", dias_suspensao, tipo="CORRIDO")
    
    # 5. Análise Técnica (Até ao PTF)
    # A soma até aqui deve dar o dia do PTF (85 ou 65)
    add_line("5. Análise Técnica", "Comissão", "Análise Pós-CP", regra['analise_pos_cp'])
    
    # MARCO: ENVIO DO PTF
    target_ptf = 85 if regra['prazo_global'] == 150 else 65
    cronograma.append({
        "Data Estimada": data_atual, 
        "Dia Admin": dias_admin, 
        "Fase": f"🎯 MARCO: ENVIO PTF (Dia {dias_admin})", 
        "Responsável": "Comissão", 
        "Descrição": f"Meta do Excel: Dia {target_ptf}", 
        "Duração": "-", "Destaque": True
    })
    
    # 6. Revisão Interna (Até à Audiência)
    add_line("6. Validação PTF", "Autoridade", "Validação Interna", regra['revisao_interna'])
    
    # MARCO: AUDIÊNCIA
    target_aud = 100 if regra['prazo_global'] == 150 else 70
    cronograma.append({
        "Data Estimada": data_atual, 
        "Dia Admin": dias_admin, 
        "Fase": f"📢 MARCO: AUDIÊNCIA (Dia {dias_admin})", 
        "Responsável": "Autoridade", 
        "Descrição": f"Meta do Excel: Dia {target_aud}", 
        "Duração": "-", "Destaque": True
    })
    
    # 7. Audiência Prévia (Suspensão Admin)
    # Nota: No seu Excel, a Audiência conta para os dias úteis globais (linha 16: "Audiência de interessados (100 dias)").
    # Mas juridicamente o CPA suspende a decisão. Vou manter a contagem de prazo global para bater com os 150/90,
    # mas marcando como fase de interação com promotor.
    add_line("7. Audiência Prévia", "PROMOTOR", "Prazo CPA (10 dias)", regra['audiencia_prazo'], tipo="UTIL")
    
    # 8. Decisão Final
    add_line("8. Emissão da DIA", "Autoridade", "Assinatura e Publicação", regra['prazo_final_decisao'])
    
    return cronograma, data_atual

# ==============================================================================
# INTERFACE
# ==============================================================================
with st.sidebar:
    st.header("1. Configuração")
    data_entrada = st.date_input("Data de Entrada", date.today())
    
    tipo_cenario = st.selectbox("Tipologia", list(REGRAS.keys()))
    regra_escolhida = REGRAS[tipo_cenario]
    st.caption(regra_escolhida['desc'])
    
    st.header("2. Suspensões")
    dias_suspensao = st.number_input("Dias de Resposta (Promotor)", value=45, min_value=0)

# ==============================================================================
# EXECUÇÃO
# ==============================================================================
anos = [data_entrada.year + i for i in range(3)]
feriados = obter_feriados_pt(anos)

if not eh_dia_util(data_entrada, feriados):
    data_inicio = proximo_dia_util(data_entrada, feriados)
    st.warning(f"⚠️ Data de entrada ajustada para dia útil: {data_inicio.strftime('%d/%m/%Y')}")
else:
    data_inicio = data_entrada

if st.button("Calcular com Calibragem Excel", type="primary"):
    
    cronograma, data_final = calcular_cronograma(data_inicio, regra_escolhida, dias_suspensao, feriados)
    
    # --- MÉTRICAS ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Data Limite DIA", data_final.strftime("%d/%m/%Y"))
    c2.metric("Prazo Admin", f"{regra_escolhida['prazo_global']} dias úteis")
    c3.metric("Suspensão Promotor", f"{dias_suspensao} dias corridos")
    
    # --- TABELA VISUAL ---
    df = pd.DataFrame(cronograma)
    
    # Formatação Visual da Tabela
    def highlight_milestones(row):
        if row['Destaque'] == True:
            return ['background-color: #d1e7dd; font-weight: bold'] * len(row)
        if "Suspensão" in row['Fase']:
            return ['background-color: #fff3cd'] * len(row)
        if "Emissão da DIA" in row['Fase']:
            return ['background-color: #f8d7da; font-weight: bold'] * len(row)
        return [''] * len(row)

    # Preparar DF para display (remover colunas técnicas)
    df_show = df.drop(columns=['Destaque'])
    df_show['Data Estimada'] = df_show['Data Estimada'].apply(lambda x: x.strftime("%d/%m/%Y"))
    
    st.table(df_show.style.apply(highlight_milestones, axis=1))
    
    # --- DOWNLOADS ---
    col1, col2 = st.columns(2)
    
    # Excel
    buffer_xls = io.BytesIO()
    with pd.ExcelWriter(buffer_xls, engine='xlsxwriter') as writer:
        df_show.to_excel(writer, index=False)
    with col1:
        st.download_button("📥 Baixar Excel", buffer_xls, "Cronograma_Calibrado.xlsx")
        
    # Word
    doc = gerar_relatorio_word(cronograma, "Projeto AIA", tipo_cenario, data_final.strftime("%d/%m/%Y"))
    buffer_word = io.BytesIO()
    doc.save(buffer_word)
    buffer_word.seek(0)
    with col2:
        st.download_button("📄 Baixar Relatório", buffer_word, "Relatorio.docx")
