import streamlit as st
import pandas as pd
from datetime import timedelta, date
import holidays
import io
from docx import Document
from docx.shared import Pt, RGBColor

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Simulador AIA (Afinado)", page_icon="⚖️", layout="wide")

st.title("⚖️ Simulador AIA - Modelo Afinado (Art. 19º)")
st.markdown("""
Este modelo utiliza a lógica legal estrita:
1. **Conformidade:** Contagem a partir do início.
2. **Data Final (DIA):** Contagem global (150 dias).
3. **PTF:** Contagem regressiva (40 dias antes da data final).
""")

# --- MOTOR DE CÁLCULO ---
def obter_feriados(anos):
    # Feriados Nacionais de Portugal
    pt_holidays = holidays.PT(years=anos)
    # Nota: Se precisar de feriados locais (ex: 13 Junho Lisboa), adicione aqui:
    # pt_holidays.append("2025-06-13") 
    return pt_holidays

def eh_dia_util(data, feriados):
    return data.weekday() < 5 and data not in feriados

def somar_dias_uteis(inicio, dias, feriados):
    data = inicio
    contador = 0
    while contador < dias:
        data += timedelta(days=1)
        if eh_dia_util(data, feriados):
            contador += 1
    return data

def subtrair_dias_uteis(fim, dias, feriados):
    data = fim
    contador = 0
    while contador < dias:
        data -= timedelta(days=1)
        if eh_dia_util(data, feriados):
            contador += 1
    return data

# --- GERAR DADOS ---
def calcular_cronograma_real(data_entrada, feriados):
    cronograma = []
    
    # Se a entrada for sexta ou fds, a contagem legal começa no próximo dia útil
    # Mas para "Nomeação" e "Reunião", muitas vezes conta-se o calendário corrido da gestão.
    # Vamos assumir a regra do CPA: Prazo conta a partir do dia seguinte.
    
    # 1. DATA FINAL (O Marco Zero do Fim)
    # Art. 19: 150 dias úteis
    prazo_global = 150
    data_final = somar_dias_uteis(data_entrada, prazo_global, feriados)
    
    # 2. CÁLCULOS INTERMÉDIOS
    
    # A. Nomeação (3 dias úteis após notificação/entrada)
    data_nomeacao = somar_dias_uteis(data_entrada, 3, feriados)
    cronograma.append({
        "Ação": "Nomeação dos representantes",
        "Data": data_nomeacao,
        "Tempo/Regra": "3 dias úteis após receção",
        "Obs": "Nº 5 do artigo 14.º"
    })
    
    # B. Reunião da CA (Estimativa operacional baseada no seu exemplo)
    # No seu exemplo: 06/06 -> 17/06 (aprox 6 dias úteis)
    data_reuniao = somar_dias_uteis(data_entrada, 6, feriados) 
    cronograma.append({
        "Ação": "Reunião da CA",
        "Data": data_reuniao,
        "Tempo/Regra": "Definido por agendamento (est. Dia 6)",
        "Obs": "n.º 6 do Artigo 14.º (Exemplo: 10:30h)"
    })

    # C. Prazo Pedido Elementos
    # No seu exemplo: 20/06 (aprox 9 dias úteis)
    data_pedidos = somar_dias_uteis(data_entrada, 9, feriados)
    cronograma.append({
        "Ação": "Prazo para envio pedido elementos",
        "Data": data_pedidos,
        "Tempo/Regra": "Definido pela CA (est. Dia 9)",
        "Obs": "Em função do prazo da conformidade"
    })

    # D. Decisão Conformidade (30 dias úteis)
    data_conformidade = somar_dias_uteis(data_entrada, 30, feriados)
    cronograma.append({
        "Ação": "Decisão da CA sobre conformidade",
        "Data": data_conformidade,
        "Tempo/Regra": "30 dias úteis",
        "Obs": "n.º 7 do Artigo 14.º"
    })
    
    # E. Proposta PTF (CÁLCULO REGRESSIVO)
    # 40 dias antes da data final
    data_ptf = subtrair_dias_uteis(data_final, 40, feriados)
    cronograma.append({
        "Ação": "Proposta do parecer técnico final (PTF)",
        "Data": data_ptf,
        "Tempo/Regra": "40 dias ANTES do prazo final",
        "Obs": "Art. 19º n.º 2 (Cálculo Inverso)"
    })
    
    # F. Emissão DIA (Data Final)
    cronograma.append({
        "Ação": "Emissão de DIA (Data Limite)",
        "Data": data_final,
        "Tempo/Regra": "150 dias úteis",
        "Obs": "Alínea a) do n.º 2 do artigo 19º",
        "Destaque": True
    })
    
    return cronograma, data_final

# --- INTERFACE ---
with st.sidebar:
    st.header("Parâmetros")
    data_input = st.date_input("Data de Entrada", date(2025, 6, 6))
    st.info("Para testar o seu exemplo, mantenha 6 de Junho de 2025.")

# Execução
anos = [data_input.year, data_input.year + 1]
feriados = obter_feriados(anos)

# Cálculo
cronograma, data_fim = calcular_cronograma_real(data_input, feriados)

# --- VISUALIZAÇÃO ---
st.subheader(f"Cronograma Calculado (Entrada: {data_input.strftime('%d/%m/%Y')})")

df = pd.DataFrame(cronograma)

# Formatação para exibição
def style_table(row):
    if row.get("Destaque"):
        return ['background-color: #ffcccc; font-weight: bold'] * len(row)
    if "PTF" in row["Ação"]:
        return ['background-color: #e6f7ff; font-weight: bold'] * len(row)
    return [''] * len(row)

# Ajuste datas para string
df_show = df.copy()
df_show['Data'] = df_show['Data'].apply(lambda x: x.strftime('%d/%m/%Y'))
df_show = df_show.drop(columns=['Destaque'], errors='ignore')

st.table(df.style.apply(style_table, axis=1).format({"Data": lambda t: t.strftime("%d/%m/%Y")}))

# --- CHECK DE VALIDAÇÃO ---
st.divider()
c1, c2 = st.columns(2)
with c1:
    st.markdown("### 🔍 Verificação do seu Exemplo")
    ptf_row = next(item for item in cronograma if "PTF" in item["Ação"])
    dia_row = next(item for item in cronograma if "Emissão de DIA" in item["Ação"])
    
    st.write(f"**PTF (Calculado):** {ptf_row['Data'].strftime('%d/%m/%Y')}")
    st.write(f"**DIA (Calculada):** {dia_row['Data'].strftime('%d/%m/%Y')}")
    
    st.caption("*Nota: Pequenas divergências de 1-2 dias podem ocorrer devido a feriados locais (ex: Santo António a 13/Jun) que o sistema nacional não conta por defeito.*")

with c2:
    # Exportar Word
    def criar_word(dados):
        doc = Document()
        doc.add_heading('Cronograma RJAIA', 0)
        
        table = doc.add_table(rows=1, cols=3)
        table.style = 'Table Grid'
        hdr = table.rows[0].cells
        hdr[0].text = 'Ação'
        hdr[1].text = 'Data'
        hdr[2].text = 'Observações'
        
        for item in dados:
            row = table.add_row().cells
            row[0].text = item['Ação']
            row[1].text = item['Data'].strftime('%d/%m/%Y')
            row[2].text = item['Obs']
        return doc

    btn_word = io.BytesIO()
    doc = criar_word(cronograma)
    doc.save(btn_word)
    btn_word.seek(0)
    
    st.download_button("📄 Baixar Tabela em Word", btn_word, "Cronograma_Afinado.docx")
