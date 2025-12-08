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
st.set_page_config(page_title="Analista EIA (Legislativo Dinâmico)", page_icon="⚖️", layout="wide")

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

def reset_app():
    st.session_state.uploader_key += 1

# ==========================================
# --- 1. BASE DE DADOS LEGISLATIVA (O CÉREBRO JURÍDICO) ---
# ==========================================

# Leis que se aplicam a TODOS os projetos
COMMON_LAWS = {
    "RJAIA (DL 151-B/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-116043164",
    "REDE NATURA (DL 140/99)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/1999-34460975",
    "RUÍDO (RGR - DL 9/2007)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2007-34526556",
    "ÁGUA (Lei 58/2005)": "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2005-34563267"
}

# Leis específicas por TIPOLOGIA
SPECIFIC_LAWS = {
    "Pedreiras e Minas": {
        "MASSAS MINERAIS (DL 270/2001)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2001-34449875",
        "RESÍDUOS DE EXTRAÇÃO (DL 10/2010)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2010-34658745",
        "SEGURANÇA MINAS (DL 162/90)": "https://diariodarepublica.pt/dr/detalhe/decreto-lei/162-1990-417937"
    },
    "Energia Renovável (Eólica/Solar)": {
        "SISTEMA ELÉTRICO (DL 15/2022)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2022-177343687",
        "SERVIDÕES AERONÁUTICAS (DL 48/2022)": "https://diariodarepublica.pt/dr/detalhe/decreto-lei/48-2022-185799345",
        "REN (DL 166/2008 - RJREN)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2008-34484789"
    },
    "Indústria Geral": {
        "EMISSÕES INDUSTRIAIS (DL 127/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-34789569",
        "LICENCIAMENTO INDUSTRIAL (SIR)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2015-106567543",
        "RESÍDUOS (RGGR - DL 102-D/2020)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2020-150917243"
    },
    "Urbanismo e Loteamentos": {
        "RJUE (Urbanização - DL 555/99)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/1999-34563452",
        "ACESSIBILIDADES (DL 163/2006)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2006-34524456",
        "RESÍDUOS CONSTRUÇÃO (DL 46/2008)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2008-34460567"
    },
    "Agropecuária": {
        "ATIVIDADE PECUÁRIA (NREAP)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2008-34480678",
        "GESTÃO DE EFLUENTES (Portaria 631/2009)": "https://diariodarepublica.pt/dr/detalhe/portaria/631-2009-518868"
    }
}

# ==========================================
# --- 2. INTERFACE E LÓGICA ---
# ==========================================

st.title("⚖️ Analista EIA Pro (Contexto Legislativo Adaptável)")
st.markdown("O sistema adapta a legislação de referência consoante a tipologia do projeto selecionado.")

with st.sidebar:
    st.header("🔐 1. Configuração")
    api_key = st.text_input("Google API Key", type="password")
    
    # SELEÇÃO DO MODELO
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
    
    # SELEÇÃO DA TIPOLOGIA (AQUI ACONTECE A MAGIA)
    st.header("🏗️ 2. Tipologia do Projeto")
    project_type = st.selectbox(
        "Selecione o tipo de projeto:",
        ["Pedreiras e Minas", "Energia Renovável (Eólica/Solar)", "Indústria Geral", "Urbanismo e Loteamentos", "Agropecuária", "Outro (Apenas Geral)"]
    )
    
    # Construção dinâmica da lista de leis
    active_laws = COMMON_LAWS.copy() # Começa com as gerais
    if project_type in SPECIFIC_LAWS:
        active_laws.update(SPECIFIC_LAWS[project_type]) # Adiciona as específicas
        st.caption(f"✅ Legislação específica de '{project_type}' carregada.")

uploaded_file = st.file_uploader("Carregue o PDF", type=['pdf'], key=f"uploader_{st.session_state.uploader_key}")

# Converter o dicionário de leis ativas para texto para o Prompt
legal_context_str = "\n".join([f"- {k}: {v}" for k, v in active_laws.items()])

# --- PROMPT ---
default_prompt = f"""
Atua como Perito Sénior em Engenharia do Ambiente e Jurista.
Realiza uma auditoria técnica e legal ao EIA de um projeto de tipologia: {project_type.upper()}.

CONTEXTO LEGISLATIVO APLICÁVEL (Versões Consolidadas):
{legal_context_str}

REGRAS DE FORMATAÇÃO:
1. "Sentence case" apenas. PROIBIDO MAIÚSCULAS em frases inteiras.
2. Não uses negrito (`**`) nas conclusões.

Estrutura o relatório EXATAMENTE nestes 7 Capítulos:

## 1. ENQUADRAMENTO LEGAL E CONFORMIDADE ({project_type})
   - O projeto enquadra-se no RJAIA?
   - Cita a legislação específica listada acima?

## 2. PRINCIPAIS IMPACTES (Técnico)
   - Análise por descritor.

## 3. MEDIDAS DE MITIGAÇÃO PROPOSTAS

## 4. ANÁLISE CRÍTICA E BENCHMARKING
   - Verifica conformidade com a legislação listada.
   - Compara com boas práticas do setor {project_type}.

## 5. FUNDAMENTAÇÃO (Pág. X)

## 6. CITAÇÕES RELEVANTES

## 7. CONCLUSÕES

Tom: Formal, Técnico e Jurídico.
"""
instructions = st.text_area("Instruções:", value=default_prompt, height=300)

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

    title = doc.add_heading(f'PARECER TÉCNICO EIA - {project_type.upper()}', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f'Data: {datetime.now().strftime("%d/%m/%Y")}').alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph('---')

    parse_markdown_to_docx(doc, content)
    
    doc.add_page_break()
    doc.add_heading('ANEXO: Legislação Aplicável (Links DRE)', level=1)
    doc.add_paragraph(f'Legislação específica considerada para a tipologia: {project_type}')
    
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
                # Passamos também o project_type para o título do Word
                word_file = create_professional_word_doc(result, active_laws, project_type)
                st.download_button("⬇️ Download Word", word_file.getvalue(), f"Parecer_{project_type[:10]}.docx", on_click=reset_app, type="primary")
