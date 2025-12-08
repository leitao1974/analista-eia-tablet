import streamlit as st
import pandas as pd
from datetime import timedelta, date
import holidays
import io
from docx import Document
from docx.shared import Pt, RGBColor, Cm

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Cronograma AIA 150 Dias", page_icon="📅", layout="wide")

st.title("📅 Calculadora AIA - Regime Geral (150 Dias)")
st.markdown("""
Este modelo reflete o cálculo misto do RJAIA:
1.  **Fases Iniciais:** Calculadas sequencialmente a partir da entrada.
2.  **Parecer Técnico Final (PTF):** Calculado regressivamente (40 dias antes do fim).
3.  **Data Limite (DIA):** Calculada aos 150 dias úteis globais.
""")

# --- UTILITÁRIOS DE TEMPO ---
@st.cache_data
def obter_feriados(anos):
    # Feriados Nacionais PT
    return holidays.PT(years=anos)

def eh_dia_util(data, feriados):
    # Fim de semana (5=Sab, 6=Dom) ou Feriado
    if data.weekday() >= 5: return False
    if data in feriados: return False
    return True

def proximo_dia_util(data, feriados):
    d = data
    while not eh_dia_util(d, feriados):
        d += timedelta(days=1)
    return d

def somar_dias_uteis(inicio, dias, feriados):
    # Regra CPA: O prazo conta-se a partir do dia útil seguinte
    # Mas para calcular datas "corridas" de fases, somamos dia a dia
    data_atual = inicio
    dias_adicionados = 0
    
    while dias_adicionados < dias:
        data_atual += timedelta(days=1)
        if eh_dia_util(data_atual, feriados):
            dias_adicionados += 1
    return data_atual

def subtrair_dias_uteis(fim, dias, feriados):
    data_atual = fim
    dias_subtraidos = 0
    
    while dias_subtraidos < dias:
        data_atual -= timedelta(days=1)
        if eh_dia_util(data_atual, feriados):
            dias_subtraidos += 1
    return data_atual

# --- MOTOR DE CÁLCULO ---
def calcular_cronograma_150(data_entrada, feriados):
    cronograma = []
    
    # 1. DEFINIÇÃO DOS MARCOS GLOBAIS
    # Data Limite: 150 dias úteis a contar da entrada (CPA: dia 1 é o seguinte)
    data_limite_dia = somar_dias_uteis(data_entrada, 150, feriados)
    
    # PTF: 40 dias úteis ANTES da data limite
    data_ptf = subtrair_dias_uteis(data_limite_dia, 40, feriados)
    
    # 2. CÁLCULO DAS FASES (Sequencial)
    
    # FASE 0: Entrada
    cronograma.append({
        "Fase": "0. Entrada",
        "Início": data_entrada,
        "Fim": data_entrada,
        "Duração": "0 dias",
        "Obs": "Submissão"
    })
    
    # FASE 1: Conformidade (30 dias úteis)
    inicio_conf = proximo_dia_util(data_entrada + timedelta(days=1), feriados)
    fim_conf = somar_dias_uteis(data_entrada, 30, feriados) # Conta 30 a partir da entrada
    cronograma.append({
        "Fase": "1. Conformidade",
        "Início": inicio_conf,
        "Fim": fim_conf,
        "Duração": "30 dias úteis",
        "Obs": "Verificação e Declaração de Conformidade"
    })
    
    # FASE 2: Preparação Consulta (Est. 5 dias úteis)
    inicio_prep = proximo_dia_util(fim_conf + timedelta(days=1), feriados)
    fim_prep = somar_dias_uteis(inicio_prep, 5, feriados, )
    cronograma.append({
        "Fase": "2. Prep. Consulta Pública",
        "Início": inicio_prep,
        "Fim": fim_prep,
        "Duração": "~5 dias úteis",
        "Obs": "Publicação de Editais"
    })
    
    # FASE 3: Consulta Pública (30 dias úteis)
    inicio_cp = proximo_dia_util(fim_prep + timedelta(days=1), feriados)
    fim_cp = somar_dias_uteis(inicio_cp, 30, feriados) # Atenção: conta o próprio dia se for útil? CPA diz seguinte. Vamos somar 30.
    cronograma.append({
        "Fase": "3. Consulta Pública",
        "Início": inicio_cp,
        "Fim": fim_cp,
        "Duração": "30 dias úteis",
        "Obs": "Participação pública (Mínimo legal)",
        "Destaque": True
    })
    
    # FASE 4: Análise Técnica (O intervalo)
    # Começa depois da CP e acaba antes do PTF
    inicio_analise = proximo_dia_util(fim_cp + timedelta(days=1), feriados)
    fim_analise = subtrair_dias_uteis(data_ptf, 1, feriados)
    
    cronograma.append({
        "Fase": "4. Análise Técnica",
        "Início": inicio_analise,
        "Fim": fim_analise,
        "Duração": "Variável",
        "Obs": "Avaliação e possíveis pedidos de Aditamentos",
    })
    
    # FASE 5: PTF (Marco)
    cronograma.append({
        "Fase": "5. Proposta PTF",
        "Início": data_ptf,
        "Fim": data_ptf,
        "Duração": "Marco",
        "Obs": "40 dias antes da Decisão Final",
        "Destaque": True
    })
    
    # FASE 6: Audiência Prévia (10 dias)
    inicio_aud = proximo_dia_util(data_ptf + timedelta(days=1), feriados)
    fim_aud = somar_dias_uteis(inicio_aud, 10, feriados)
    cronograma.append({
        "Fase": "6. Audiência Prévia",
        "Início": inicio_aud,
        "Fim": fim_aud,
        "Duração": "10 dias úteis",
        "Obs": "CPA (Pronúncia do Promotor)"
    })
    
    # FASE 7: Decisão (Marco Final)
    cronograma.append({
        "Fase": "7. Emissão da DIA",
        "Início": data_limite_dia,
        "Fim": data_limite_dia,
        "Duração": "Marco",
        "Obs": "Dia 150 (Limite Legal)",
        "Destaque": True
    })
    
    return cronograma

# --- INTERFACE ---
with st.sidebar:
    st.header("Configuração")
    # DATA FIXA DO SEU EXEMPLO
    data_entrada = st.date_input("Data de Entrada", date(2025, 6, 6))
    
    st.info("""
    **Parâmetros:**
    * Prazo Global: 150 dias úteis
    * Feriados: Nacionais (Portugal)
    * Cálculo PTF: Regressivo
    """)

# Execução
anos = [data_entrada.year, data_entrada.year + 1]
feriados = obter_feriados(anos)

# Aviso de Fim de Semana
aviso = ""
if not eh_dia_util(data_entrada, feriados):
    aviso = "⚠️ A data selecionada é fim de semana/feriado. A contagem inicia no 1º dia útil seguinte."

if st.button("Calcular Cronograma", type="primary"):
    if aviso: st.warning(aviso)
    
    dados = calcular_cronograma_150(data_entrada, feriados)
    
    # DATAFRAME
    df = pd.DataFrame(dados)
    
    # FORMATAR DATAS PARA STRING
    df_show = df.copy()
    df_show['Início'] = df_show['Início'].apply(lambda x: x.strftime('%d/%m/%Y'))
    df_show['Fim'] = df_show['Fim'].apply(lambda x: x.strftime('%d/%m/%Y'))
    
    # Remove coluna Destaque para exibição
    cols_to_show = ['Fase', 'Início', 'Fim', 'Duração', 'Obs']
    
    # VISUALIZAÇÃO
    st.subheader(f"Cronograma Estimado (Entrada: {data_entrada.strftime('%d/%m/%Y')})")
    
    # Estilização da Tabela
    def highlight_rows(row):
        if row.get('Destaque'):
            return ['background-color: #e3f2fd; font-weight: bold'] * len(row)
        if "Análise Técnica" in row['Fase']:
            return ['background-color: #fff3e0'] * len(row) # Laranja claro
        return [''] * len(row)

    st.dataframe(
        df_show[cols_to_show].style.apply(highlight_rows, axis=1), 
        use_container_width=True,
        hide_index=True
    )
    
    # EXCEL DOWNLOAD
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df_show.drop(columns=['Destaque'], errors='ignore').to_excel(writer, index=False)
    
    st.download_button("📥 Baixar Excel", buffer, "Cronograma_150dias.xlsx")
    
    # VISUALIZAÇÃO TEXTUAL RÁPIDA
    st.divider()
    c1, c2, c3 = st.columns(3)
    
    # Extrair datas chave
    dia_ptf = df[df['Fase'] == '5. Proposta PTF']['Início'].values[0]
    dia_fim = df[df['Fase'] == '7. Emissão da DIA']['Início'].values[0]
    dia_conf = df[df['Fase'] == '1. Conformidade']['Fim'].values[0]
    
    c1.metric("Fim Conformidade", pd.to_datetime(dia_conf).strftime('%d/%m/%Y'))
    c2.metric("Proposta PTF", pd.to_datetime(dia_ptf).strftime('%d/%m/%Y'), delta="Conta de trás para a frente")
    c3.metric("Data Limite (DIA)", pd.to_datetime(dia_fim).strftime('%d/%m/%Y'), delta="Dia 150")

    # VERIFICAÇÃO DE FERIADOS
    with st.expander("Ver Feriados Considerados"):
        feriados_range = [f for f in feriados if data_entrada <= f <= pd.to_datetime(dia_fim).date()]
        for f in sorted(feriados_range):
            st.write(f"- {f.strftime('%d/%m/%Y')} ({f.strftime('%A')})")
