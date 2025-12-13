import streamlit as st
from pypdf import PdfReader
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import google.generativeai as genai
import io
from datetime import datetime
import re
import time

# --- Configuração ---
st.set_page_config(page_title="Análise", page_icon="⚖️", layout="wide")

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

def reset_app():
    st.session_state.uploader_key += 1

# ==========================================
# --- 1. BASE DE DADOS LEGISLATIVA (RJAIA COMPLETO) ---
# ==========================================

# Leis Transversais (Aplicam-se a tudo)
COMMON_LAWS = {
    "RJAIA (DL 151-B/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-116043164",
    "REDE NATURA (DL 140/99)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/1999-34460975",
    "RUÍDO (RGR - DL 9/2007)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2007-34526556",
    "ÁGUA (Lei 58/2005)": "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2005-34563267"
}

# Leis Específicas por Setor (Baseado nos Anexos do RJAIA)
SPECIFIC_LAWS = {
    "1. Agricultura, Silvicultura e Aquicultura": {
        "ATIVIDADE PECUÁRIA (NREAP)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2008-34480678",
        "GESTÃO EFLUENTES (Port. 631/2009)": "https://diariodarepublica.pt/dr/detalhe/portaria/631-2009-518868",
        "FLORESTAS (DL 16/2009 - PGF)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2009-34488356"
    },
    "2. Indústria Extrativa (Minas e Pedreiras)": {
        "MASSAS MINERAIS (DL 270/2001)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2001-34449875",
        "RESÍDUOS DE EXTRAÇÃO (DL 10/2010)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2010-34658745",
        "SEGURANÇA MINAS (DL 162/90)": "https://diariodarepublica.pt/dr/detalhe/decreto-lei/162-1990-417937"
    },
    "3. Indústria Energética": {
        "SISTEMA ELÉTRICO (DL 15/2022)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2022-177343687",
        "EMISSÕES INDUSTRIAIS (DL 127/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-34789569",
        "REFINAÇÃO/COMBUSTÍVEIS": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2012-34589012"
    },
    "4. Produção e Transformação de Metais": {
        "EMISSÕES INDUSTRIAIS (DL 127/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-34789569",
        "LICENCIAMENTO INDUSTRIAL (SIR)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2015-106567543"
    },
    "5. Indústria Mineral e Química": {
        "PREVENÇÃO ACIDENTES GRAVES (SEVESO - DL 150/2015)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2015-106558967",
        "EMISSÕES (DL 127/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-34789569"
    },
    "6. Infraestruturas (Rodovias, Ferrovias, Aeroportos)": {
        "ESTATUTO ESTRADAS (Lei 34/2015)": "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2015-34585678",
        "SERVIDÕES AERONÁUTICAS (DL 48/2022)": "https://diariodarepublica.pt/dr/detalhe/decreto-lei/48-2022-185799345",
        "RUÍDO GRANDES INFRAESTRUTURAS": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2007-34526556"
    },
    "7. Projetos de Engenharia Hidráulica (Barragens, Portos)": {
        "SEGURANÇA BARRAGENS (DL 21/2018)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2018-114833256",
        "DOMÍNIO HÍDRICO (Lei 54/2005)": "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2005-34563267"
    },
    "8. Tratamento de Resíduos e Águas Residuais": {
        "RESÍDUOS (RGGR - DL 102-D/2020)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2020-150917243",
        "ÁGUAS RESIDUAIS URBANAS (DL 152/97)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/1997-34512345",
        "ATERROS (DL 102-D/2020)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2020-150917243"
    },
    "9. Projetos Urbanos, Turísticos e Outros": {
        "RJUE (Urbanização - DL 555/99)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/1999-34563452",
        "EMPREENDIMENTOS TURÍSTICOS (RJET)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2008-34460567",
        "ACESSIBILIDADES (DL 163/2006)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2006-34524456"
    }
}

# ==========================================
# --- 2. INTERFACE E LÓGICA ---
# ==========================================

st.title("⚖️ Análise")
st.markdown("Análise Técnica e Legal adaptada aos setores definidos nos Anexos I e II do DL 151-B/2013.")

with st.sidebar:
    st.header("🔐 1. Configuração")
    
    # === ÁREA PARA COLOCAR A CHAVE FIXA ===
    # Se quiser fixar, coloque a chave dentro das aspas abaixo:
    CHAVE_FIXA = "" 
    # ======================================

    if CHAVE_FIXA:
        api_key = CHAVE_FIXA
        st.success(f"🔑 Chave API Carregada")
    else:
        api_key = st.text_input("Google API Key", type="password")
    
    selected_model = None
    if api_key:
        try:
            genai.configure(api_key=api_key)
            models_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            if models_list:
                st.success(f"Chave válida!")
                index_flash = next((i for i, m in enumerate(models_list) if 'flash' in m), 0)
                selected_model = st.selectbox("Modelo IA:", models_list, index=index_flash)
            else:
                st.error("Chave válida mas sem modelos.")
        except:
            st.error("Chave inválida.")

    st.divider()
    
    # SELEÇÃO DA TIPOLOGIA (Lista Completa)
    st.header("🏗️ 2. Tipologia (Anexos RJAIA)")
    project_type = st.selectbox(
        "Selecione o setor de atividade:",
        list(SPECIFIC_LAWS.keys()) + ["Outra Tipologia"]
    )
    
    # Construção dinâmica da lista de leis
    active_laws = COMMON_LAWS.copy() 
    if project_type in SPECIFIC_LAWS:
        active_laws.update(SPECIFIC_LAWS[project_type])
        st.caption(f"✅ Legislação específica carregada.")
        with st.expander("Ver leis aplicáveis"):
            st.write(active_laws)

uploaded_file = st.file_uploader("Carregue o PDF", type=['pdf'], key=f"uploader_{st.session_state.uploader_key}")

legal_context_str = "\n".join([f"- {k}: {v}" for k, v in active_laws.items()])

# --- PROMPT ATUALIZADO (INVISÍVEL NA APP) ---
instructions = f"""
Atua como Perito Sénior em Engenharia do Ambiente e Jurista.
Realiza uma auditoria técnica e legal ao EIA de um projeto do setor: {project_type.upper()}.

CONTEXTO LEGISLATIVO (Prioritário):
{legal_context_str}

REGRAS DE FORMATAÇÃO:
1. "Sentence case" apenas. PROIBIDO MAIÚSCULAS em frases inteiras.
2. Não uses negrito (`**`) nas conclusões.

Estrutura o relatório EXATAMENTE nestes 7 Capítulos:

## 1. ENQUADRAMENTO LEGAL E CONFORMIDADE
   - O projeto enquadra-se corretamente no RJAIA (Anexo I ou II)?
   - Verifica o cumprimento da legislação específica listada acima.

## 2. PRINCIPAIS IMPACTES (Técnico)
   - Análise por descritor ambiental.

## 3. MEDIDAS DE MITIGAÇÃO PROPOSTAS
   - Lista as medidas.

## 4. ANÁLISE CRÍTICA E DETEÇÃO DE ERROS (FOCO ESPECÍFICO)
   - **Plantas de Localização:** Verifica no texto referências a escalas adequadas (1:25.000 ou superior), sistema de coordenadas oficial (PT-TM06/ETRS89) e menção a sobreposições com servidões (REN, RAN, Rede Natura). Aponta se faltarem legendas descritivas claras.
   - **Ruído (Ambiente Sonoro):** Verifica se o estudo cumpre o RGR (DL 9/2007). Confirma se foram usados os indicadores corretos (Lden e Ln) e se existe identificação clara de "Recetores Sensíveis". Aponta falta de monitorização de base se detetada.
   - **Geral:** As medidas são suficientes face à lei e melhores práticas do setor {project_type}?

## 5. FUNDAMENTAÇÃO
   - Explicação técnica das falhas detetadas.

## 6. CITAÇÕES RELEVANTES

## 7. CONCLUSÕES
   - Parecer Final fundamentado.

Tom: Formal, Técnico e Jurídico.
"""

# ==========================================
# --- 3. FUNÇÕES TÉCNICAS (LIMPEZA E WORD) ---
# ==========================================

def extract_text_pypdf(file):
    text = ""
    try:
        reader = PdfReader(file)
        for i, page in enumerate(reader.pages):
            content = page.extract_text()
            if content:
                text += f"\n\n--- PÁGINA {i+1} ---\n{content}"
    except Exception as e:
        return f"ERRO: {str(e)}"
    return text

def analyze_ai(text, prompt, key, model_name):
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel(model_name)
        safe_text = text[:800000]
        response = model.generate_content(f"{prompt}\n\nDADOS DO PDF:\n{safe_text}")
        return response.text
    except Exception as e:
        return f"Erro IA: {str(e)}"

def clean_ai_formatting(text):
    text = text.replace('**', '') 
    if len(text) > 40 and text.isupper():
        return text.capitalize()
    words = text.split()
    if len(words) > 6:
        upper_starts = sum(1 for w in words if w and w[0].isupper())
        if upper_starts / len(words) > 0.7:
            return text.capitalize()
    return text

# Helpers Word
def format_bold_runs(paragraph, text):
    parts = re.split(r'(\*\*.*?\*\*)', text)
    for part in parts:
        if part.startswith('**') and part.endswith('**'):
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        else:
            paragraph.add_run(part)

def parse_markdown_to_docx(doc, markdown_text):
    in_critical_section = False
    for line in markdown_text.split('\n'):
        line = line.strip()
        if not line: continue
        
        if line.startswith('## ') or re.match(r'^\d+\.\s', line):
            clean = re.sub(r'^(##\s|\d+\.\s)', '', line).replace('*', '')
            doc.add_heading(clean.title(), level=1)
            if "CITAÇÕES" in clean.upper() or "CONCLUSÕES" in clean.upper():
                in_critical_section = True
            else:
                in_critical_section = False
        elif line.startswith('### '):
            clean = line[4:].replace('*', '')
            doc.add_heading(clean, level=2)
        elif line.startswith('- ') or line.startswith('* '):
            p = doc.add_paragraph(style='List Bullet')
            clean_line = line[2:]
            if in_critical_section:
                p.add_run(clean_ai_formatting(clean_line))
            else:
                format_bold_runs(p, clean_line)
        else:
            p = doc.add_paragraph()
            if in_critical_section:
                p.add_run(clean_ai_formatting(line))
            else:
                format_bold_runs(p, line)

def create_professional_word_doc(content, legal_links, project_type):
    doc = Document()
    style_normal = doc.styles['Normal']
    style_normal.font.name = 'Calibri'
    style_normal.font.size = Pt(11)
    
    style_h1 = doc.styles['Heading 1']
    style_h1.font.name = 'Cambria'
    style_h1.font.size = Pt(14)
    style_h1.font.bold = True
    style_h1.font.color.rgb = RGBColor(0, 51, 102)

    title = doc.add_heading(f'PARECER TÉCNICO EIA', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f'Setor: {project_type}').alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f'Data: {datetime.now().strftime("%d/%m/%Y")}').alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph('---')

    parse_markdown_to_docx(doc, content)
    
    doc.add_page_break()
    doc.add_heading('ANEXO: Legislação Aplicável (Links DRE)', level=1)
    
    for name, url in legal_links.items():
        p = doc.add_paragraph(style='List Bullet')
        p.add_run(name + ": ").bold = True
        run = p.add_run(url)
        run.font.color.rgb = RGBColor(0, 0, 255)
        run.font.underline = True

    bio = io.BytesIO()
    doc.save(bio)
    return bio

# --- BOTÃO ---
st.markdown("---")

if st.button("🚀 Gerar Relatório", type="primary", use_container_width=True):
    if not api_key:
        st.error("⚠️ Insira a API Key.")
    elif not selected_model:
        st.error("⚠️ Nenhum modelo selecionado.")
    elif not uploaded_file:
        st.warning("⚠️ Carregue o PDF.")
    else:
        with st.spinner(f"A processar EIA de {project_type}..."):
            pdf_text = extract_text_pypdf(uploaded_file)
            result = analyze_ai(pdf_text, instructions, api_key, selected_model)
            
            if "Erro" in result and len(result) < 200:
                st.error(result)
            else:
                st.success("✅ Sucesso!")
                with st.expander("Ver Texto"):
                    st.write(result)
                word_file = create_professional_word_doc(result, active_laws, project_type)
                st.download_button("⬇️ Download Word", word_file.getvalue(), f"Parecer_EIA.docx", on_click=reset_app, type="primary")
