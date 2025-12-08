import streamlit as st
import pandas as pd
import datetime
from datetime import timedelta, date
import holidays
import io
from docx import Document
from docx.shared import Pt, RGBColor

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Simulador AIA (Final)", page_icon="📅", layout="wide")

st.title("📊 Simulador de Prazos AIA (Versão Final)")
st.markdown("""
Esta ferramenta calcula os prazos do Regime Jurídico de AIA (RJAIA) considerando dias úteis (exclui fins de semana e feriados nacionais).
""")

# --- FUNÇÕES UTILITÁRIAS ---
@st.cache_data
def obter_feriados_pt(anos):
    # Carrega feriados de Portugal para os anos indicados
    return holidays.PT(years=anos)

def eh_dia_util(data_check, lista_feriados):
    # 0=Segunda... 5=Sábado, 6=Domingo
    if data_check.weekday() >= 5: return False
    if data_check in lista_feriados: return False
    return True

def proximo_dia_util(data_ref, lista_feriados):
    data_calc = data_ref
    # Se cair num fds ou feriado, avança até ser útil
    while not eh_dia_util(data_calc, lista_feriados):
        data_calc += timedelta(days=1)
    return data_calc

def somar_dias_uteis(data_inicio, dias_a_adicionar, lista_feriados):
    # Lógica CPA: A contagem do prazo inicia-se no dia útil seguinte
    data_atual = data_inicio
    dias_adicionados = 0
    while dias_adicionados < dias_a_adicionar:
        data_atual += timedelta(days=1)
        if eh_dia_util(data_atual, lista_feriados):
            dias_adicionados += 1
    return data_atual

# --- REGRAS DO PROCESSO (CALIBRAGEM) ---
REGRAS = {
    "Cenário Geral (150 Dias)": {
        "prazo_global": 150,
        "fase_conformidade": 30,
        "prep_cp": 5,
        "consulta_publica": 30,
        "analise_pos_cp": 20, 
        "revisao_interna": 15,
        "audiencia_prazo": 10,
        "prazo_final_decisao": 40,
        "desc": "Projetos Infraestruturas/Serviços. (PTF ~Dia 85 | Audiência ~Dia 100)"
    },
    "Cenário Indústria/PIN (90 Dias)": {
        "prazo_global": 90,
        "fase_conformidade": 20,
        "prep_cp": 5,
        "consulta_publica": 30,
        "analise_pos_cp": 10,
        "revisao_interna": 5,
        "audiencia_prazo": 10,
        "prazo_final_decisao": 10,
        "desc": "Projetos SIR/PIN. (PTF ~Dia 65 | Audiência ~Dia 70)"
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
    run.font.color.rgb = RGBColor(200, 0, 0) # Vermelho
    
    # Tabela
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
        
    doc.add_paragraph("\nNota: Cálculo baseado em dias úteis (excluindo Feriados Nacionais e Fins de Semana).")
    return doc

# --- MOTOR DE CÁLCULO ---
def calcular_cronograma(data_inicio, regra, dias_suspensao, feriados):
    cronograma = []
    data_atual = data_inicio
    dias_admin = 0
    
    def add_line(fase, resp, desc, dias, tipo="UTIL", destaque=False):
        nonlocal data_atual, dias_admin
        
        # Só adiciona a linha se a duração for > 0 ou for um marco importante
        if dias == 0 and "Suspensão" in fase:
            return

        cronograma.append({
            "Data Estimada": data_atual,
            "Dia Admin": dias_admin if resp != "PROMOTOR" else "PAUSA",
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
            # Suspensão (dias corridos)
            data_fim = data_atual + timedelta(days=dias)
            data_atual = proximo_dia_util(data_fim, feriados)

    # 0. Início
    add_line("0. Entrada do Processo", "Promotor", "Submissão", 0)
    
    # 1. Conformidade
    add_line("1. Verificação Conformidade", "Autoridade", "Análise inicial", regra['fase_conformidade'])
    
    # 2. Prep CP
    add_line("2. Preparação CP", "Autoridade", "Preparação Editais", regra['prep_cp'])
    
    # 3. Consulta Pública
    add_line("3. Consulta Pública", "Autoridade", "Período legal", regra['consulta_publica'])
    
    # 4. Suspensão (Se houver)
    if dias_suspensao > 0:
        add_line("4. Suspensão (Aditamentos)", "PROMOTOR", "Paragem do relógio", dias_suspensao, tipo="CORRIDO")
    
    # 5. Análise Técnica
    add_line("5. Análise Técnica Pós-CP", "Comissão", "Avaliação", regra['analise_pos_cp'])
    
    # MARCO: ENVIO DO PTF
    target_ptf = 85 if regra['prazo_global'] == 150 else 65
    cronograma.append({
        "Data Estimada": data_atual, 
        "Dia Admin": dias_admin, 
        "Fase": f"🎯 MARCO: ENVIO PTF (Dia {dias_admin})", 
        "Responsável": "Comissão", 
        "Descrição": f"Meta Ideal: Dia {target_ptf}", 
        "Duração": "-", "Destaque": True
    })
    
    # 6. Revisão Interna
    add_line("6. Validação PTF", "Autoridade", "Validação", regra['revisao_interna'])
    
    # MARCO: AUDIÊNCIA
    target_aud = 100 if regra['prazo_global'] == 150 else 70
    cronograma.append({
        "Data Estimada": data_atual, 
        "Dia Admin": dias_admin, 
        "Fase": f"📢 MARCO: AUDIÊNCIA (Dia {dias_admin})", 
        "Responsável": "Autoridade", 
        "Descrição": f"Meta Ideal: Dia {target_aud}", 
        "Duração": "-", "Destaque": True
    })
    
    # 7. Audiência Prévia (CPA)
    add_line("7. Audiência Prévia (CPA)", "PROMOTOR", "Pronúncia do interessado", regra['audiencia_prazo'], tipo="UTIL")
    
    # 8. Decisão Final
    add_line("8. Emissão da DIA", "Autoridade", "Decisão Final", regra['prazo_final_decisao'])
    
    return cronograma, data_atual

# ==============================================================================
# INTERFACE
# ==============================================================================
with st.sidebar:
    st.header("1. Dados do Projeto")
    # CORREÇÃO 1: Definir data padrão para 6 Junho 2025 para teste imediato
    data_entrada = st.date_input("Data de Entrada", date(2025, 6, 6))
    
    tipo_cenario = st.selectbox("Tipologia", list(REGRAS.keys()))
    regra_escolhida = REGRAS[tipo_cenario]
    
    st.divider()
    st.header("2. Suspensões")
    # CORREÇÃO 2: Valor padrão alterado de 45 para 0
    dias_suspensao = st.number_input("Dias de Suspensão (Promotor)", value=0, min_value=0, help="Dias de paragem do relógio (aditamentos).")

# ==============================================================================
# EXECUÇÃO E RESULTADOS
# ==============================================================================

# Gerar feriados para o intervalo de anos provável
anos = [data_entrada.year, data_entrada.year + 1]
feriados = obter_feriados_pt(anos)

# Ajuste inicial se entrada for fim de semana
if not eh_dia_util(data_entrada, feriados):
    data_inicio = proximo_dia_util(data_entrada, feriados)
    aviso_data = f"⚠️ Entrada a {data_entrada} (Fim de semana/Feriado). Contagem inicia a: {data_inicio}"
else:
    data_inicio = data_entrada
    aviso_data = None

# Botão principal
if st.button("Calcular Prazos", type="primary"):
    
    if aviso_data:
        st.warning(aviso_data)
        
    cronograma, data_final = calcular_cronograma(data_inicio, regra_escolhida, dias_suspensao, feriados)
    
    # --- MÉTRICAS DE TOPO ---
    c1, c2, c3 = st.columns(3)
    c1.metric("🏁 Data Final (DIA)", data_final.strftime("%d/%m/%Y"), help="Data estimada de emissão da decisão")
    c2.metric("📅 Prazo Admin Consumido", f"{regra_escolhida['prazo_global']} dias úteis")
    c3.metric("⏸️ Suspensão", f"{dias_suspensao} dias corridos")
    
    # --- TABELA DETALHADA ---
    st.subheader("Cronograma Detalhado")
    df = pd.DataFrame(cronograma)
    
    def highlight_rows(row):
        if row['Destaque']:
            return ['background-color: #e8f5e9; font-weight: bold; color: #2e7d32'] * len(row)
        if "Suspensão" in row['Fase'] or "PAUSA" in str(row['Dia Admin']):
            return ['background-color: #fff3e0; color: #e65100'] * len(row)
        if "Emissão da DIA" in row['Fase']:
            return ['background-color: #ffebee; font-weight: bold; color: #c62828'] * len(row)
        return [''] * len(row)

    df_display = df.drop(columns=['Destaque'])
    # Formatação de data
    df_display['Data Estimada'] = df_display['Data Estimada'].apply(lambda x: x.strftime("%d/%m/%Y"))
    
    st.dataframe(df_display.style.apply(highlight_rows, axis=1), use_container_width=True, hide_index=True)
    
    # --- SECÇÃO DE DOWNLOADS ---
    st.divider()
    col_d1, col_d2 = st.columns(2)
    
    # Excel
    buffer_xls = io.BytesIO()
    with pd.ExcelWriter(buffer_xls, engine='xlsxwriter') as writer:
        df_display.to_excel(writer, index=False, sheet_name="Cronograma")
    col_d1.download_button("📥 Baixar Cronograma (Excel)", buffer_xls, "Cronograma_AIA.xlsx", mime="application/vnd.ms-excel")
    
    # Word
    doc = gerar_relatorio_word(cronograma, "Projeto AIA", tipo_cenario, data_final.strftime("%d/%m/%Y"))
    buffer_word = io.BytesIO()
    doc.save(buffer_word)
    buffer_word.seek(0)
    col_d2.download_button("📄 Baixar Relatório (Word)", buffer_word, "Relatorio_AIA.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    # --- DEBUGGING / CHECK DE FERIADOS ---
    with st.expander("🔍 Verificar Feriados Considerados"):
        st.write("O sistema considerou os seguintes feriados nacionais entre a data de início e a data final:")
        feriados_intervalo = [d for d in feriados if data_entrada <= d <= data_final]
        feriados_intervalo.sort()
        for f in feriados_intervalo:
            st.text(f"• {f.strftime('%d/%m/%Y')} ({f.strftime('%A')})")
        st.caption("Nota: Se o seu Excel não considerar algum destes feriados (ex: Corpo de Deus, Carnaval se for tolerância), a data final terá uma diferença de 1 dia por cada feriado.")
