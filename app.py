import streamlit as st
import pandas as pd
from datetime import timedelta, date
import holidays
import io
from docx import Document
from docx.shared import Pt, RGBColor

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Simulador AIA (Simplex)", page_icon="⚡", layout="wide")

st.title("⚡ Simulador AIA - RJAIA Simplex")
st.markdown("""
Configurado com os prazos do **Simplex Ambiental**:
* **Conformidade (Instrução Liminar):** 10 dias úteis.
* **Consulta Pública:** 35 dias úteis.
""")

# --- FUNÇÕES DE TEMPO ---
@st.cache_data
def obter_feriados(anos):
    # Feriados Nacionais PT
    return holidays.PT(years=anos)

def eh_dia_util(data_check, lista_feriados):
    # Retorna True se for dia útil (seg-sex e não feriado)
    if data_check.weekday() >= 5: return False
    if data_check in lista_feriados: return False
    return True

def proximo_dia_util(data_ref, lista_feriados):
    # Avança até encontrar um dia útil
    d = data_ref
    while not eh_dia_util(d, lista_feriados):
        d += timedelta(days=1)
    return d

def somar_dias_uteis(inicio, dias, lista_feriados, incluir_inicio=False):
    data_atual = inicio
    dias_contados = 0
    
    # Se quisermos contar o próprio dia de início como Dia 1 (opcional)
    if incluir_inicio and eh_dia_util(data_atual, lista_feriados):
        dias_contados = 1
    
    while dias_contados < dias:
        data_atual += timedelta(days=1)
        if eh_dia_util(data_atual, lista_feriados):
            dias_contados += 1
    return data_atual

# --- MOTOR DE CÁLCULO ---
def calcular_simplex(inicio, cfg, feriados):
    cronograma = []
    
    # 0. ENTRADA
    cronograma.append({
        "Data": inicio,
        "Etapa": "0. Entrada",
        "Descrição": "Submissão do Pedido",
        "Duração": "0 dias"
    })
    
    # 1. CONFORMIDADE (10 dias)
    # A contagem começa no dia seguinte à entrada (regra geral CPA)
    fim_conformidade = somar_dias_uteis(inicio, cfg['conf'], feriados)
    
    cronograma.append({
        "Data": inicio, # Visualmente aparece na data de início da fase
        "Etapa": "1. Conformidade",
        "Descrição": "Verificação Liminar da Instrução",
        "Duração": f"{cfg['conf']} dias (Uteis)",
        "Fim Previsto": fim_conformidade
    })
    
    # 2. CONSULTA PÚBLICA (35 dias)
    # Inicia no dia útil seguinte ao fim da conformidade
    inicio_cp = proximo_dia_util(fim_conformidade + timedelta(days=1), feriados)
    fim_cp = somar_dias_uteis(inicio_cp, cfg['cp'], feriados)
    
    cronograma.append({
        "Data": inicio_cp,
        "Etapa": "2. Consulta Pública",
        "Descrição": "Publicitação e Período de Consulta",
        "Duração": f"{cfg['cp']} dias (Uteis)",
        "Fim Previsto": fim_cp
    })
    
    # 3. PÓS-CONSULTA E DECISÃO (Restante até aos 150 dias globais, se aplicável)
    # No Simplex, o foco é cumprir os parciais, mas vamos projetar o final.
    # Prazo global do Art 19 pode ser 150 (geral) ou menos.
    # Vamos assumir o cálculo sequencial para os passos seguintes.
    
    # Análise Técnica (ex: 20 dias após CP)
    inicio_analise = proximo_dia_util(fim_cp + timedelta(days=1), feriados)
    fim_analise = somar_dias_uteis(inicio_analise, 20, feriados) # Estimativa Simplex
    
    cronograma.append({
        "Data": inicio_analise,
        "Etapa": "3. Análise Técnica",
        "Descrição": "Apreciação técnica e PTF",
        "Duração": "20 dias (Estimado)",
        "Fim Previsto": fim_analise
    })

    # Decisão Final (DIA) - Estimativa para fechar perto dos 100-120 dias no total Simplex
    inicio_decisao = proximo_dia_util(fim_analise + timedelta(days=1), feriados)
    fim_decisao = somar_dias_uteis(inicio_decisao, 15, feriados)
    
    cronograma.append({
        "Data": fim_decisao,
        "Etapa": "4. Decisão Final (DIA)",
        "Descrição": "Emissão da DIA",
        "Duração": "-",
        "Fim Previsto": fim_decisao,
        "Destaque": True
    })

    return cronograma

# --- INTERFACE ---
with st.sidebar:
    st.header("Parâmetros Simplex")
    # DATA CORRIGIDA PARA O SEU EXEMPLO (03/06/2025)
    data_entrada = st.date_input("Data de Entrada", date(2025, 6, 3))
    
    st.subheader("Durações (Dias Úteis)")
    dias_conf = st.number_input("1. Conformidade", value=10, step=1)
    dias_cp = st.number_input("2. Consulta Pública", value=35, step=1)
    
    st.markdown("---")
    st.caption("O Simplex (DL 11/2023) reduz conformidade para 10 dias e ajusta a CP.")

# Execução
anos = [data_entrada.year, data_entrada.year + 1]
feriados = obter_feriados(anos)

# Ajuste se entrada for feriado/fds
if not eh_dia_util(data_entrada, feriados):
    st.warning("A data de entrada selecionada não é um dia útil.")

if st.button("Calcular Cronograma Simplex", type="primary"):
    
    cfg = {'conf': dias_conf, 'cp': dias_cp}
    dados = calcular_simplex(data_entrada, cfg, feriados)
    
    # Exibir como o seu exemplo de texto
    st.subheader("2. Detalhe das Etapas (Simulação)")
    
    for etapa in dados:
        cor = "blue" if "Conformidade" in etapa['Etapa'] else "green" if "Consulta" in etapa['Etapa'] else "black"
        bg = "#f0f2f6"
        
        if etapa.get("Destaque"):
            bg = "#ffebee"
            cor = "red"
            
        data_show = etapa['Data'].strftime('%d/%m/%Y')
        
        with st.container():
            st.markdown(f"""
            <div style="background-color: {bg}; padding: 10px; border-radius: 5px; margin-bottom: 10px; border-left: 5px solid {cor}">
                <strong>{data_show} - {etapa['Etapa']}</strong><br>
                <span style="color: #555;">Descrição: {etapa['Descrição']}</span><br>
                <span style="color: #555;">Duração considerada: <strong>{etapa['Duração']}</strong></span>
            </div>
            """, unsafe_allow_html=True)
            
            # Se quiser mostrar a data de fim da etapa também
            if "Fim Previsto" in etapa and etapa['Etapa'] != "0. Entrada" and not etapa.get("Destaque"):
                st.caption(f"Termina a: {etapa['Fim Previsto'].strftime('%d/%m/%Y')}")

    # Tabela Simples para Download
    df = pd.DataFrame(dados)
    df['Data'] = df['Data'].apply(lambda x: x.strftime('%d/%m/%Y'))
    if 'Fim Previsto' in df.columns:
        df['Fim Previsto'] = df['Fim Previsto'].apply(lambda x: x.strftime('%d/%m/%Y') if not pd.isnull(x) else "")
    
    st.divider()
    # Excel Download
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
        
    st.download_button("📥 Baixar Tabela Excel", buffer, "Cronograma_Simplex.xlsx")
