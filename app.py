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
st.set_page_config(page_title="Analista EIA (Format Fix)", page_icon="📝", layout="wide")

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

def reset_app():
    st.session_state.uploader_key += 1

# --- Interface ---
st.title("📝 Analista EIA Pro (Formatação Corrigida)")
st.markdown("Relatórios Técnicos com correção automática de texto (remove maiúsculas excessivas e negritos indevidos).")

with st.sidebar:
    st.header("🔐 Configuração")
    api_key = st.text_input("Google API Key", type="password")
    
    selected_model = None
    if api_key:
        try:
            genai.configure(api_key=api_key)
            models_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            if models_list:
                st.success(f"Chave válida! {len(models_list)} modelos.")
                # Tenta pré-selecionar o Flash
                index_flash = next((i for i, m in enumerate(models_list) if 'flash' in m), 0)
                selected_model = st.selectbox("Escolha o Modelo:", models_list, index=index_flash)
            else:
                st.error("Chave válida mas sem modelos.")
        except Exception as e:
            st.error(f"Erro na Chave: {str(e)}")

uploaded_file = st.file_uploader("Carregue o PDF", type=['pdf'], key=f"uploader_{st.session_state.uploader_key}")

# --- MATRIZ JURÍDICA ---
legal_refs = {
    "RJAIA (DL 151-B/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-116043164",
    "REDE NATURA (DL 140/99)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/1999-34460975",
    "RUÍDO (DL 9/2007)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2007-34526556",
    "ÁGUA (Lei 58/2005)": "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2005-34563267"
}
legal_context_str = "\n".join([f"- {k}: {v}" for k, v in legal_refs.items()])

# --- PROMPT REFORÇADO ---
default_prompt = f"""
Atua como Perito Sénior em Engenharia do Ambiente e Jurista.
Realiza uma auditoria técnica e legal ao EIA.

CONTEXTO LEGISLATIVO:
{legal_context_str}

REGRAS ESTRITAS DE FORMATAÇÃO:
1. Escreve em "Sentence case" (apenas a primeira letra da frase em maiúscula).
2. PROIBIDO USAR MAIÚSCULAS EM FRASES INTEIRAS.
3. PROIBIDO Capitalizar Todas As Palavras (Title Case).
4. NÃO uses negrito (`**`) nos capítulos 6 e 7.

Estrutura o relatório EXATAMENTE nestes 7 Capítulos:

## 1. ENQUADRAMENTO LEGAL E CONFORMIDADE
## 2. PRINCIPAIS IMPACTES (Técnico)
## 3. MEDIDAS DE MITIGAÇÃO PROPOSTAS
## 4. ANÁLISE CRÍTICA E BENCHMARKING
## 5. FUNDAMENTAÇÃO (Pág. X)
## 6. CITAÇÕES RELEVANTES (Texto normal, entre aspas)
## 7. CONCLUSÕES (Texto normal)

Tom: Formal, Técnico e Jurídico.
"""
instructions = st.text_area("Instruções:", value=default_prompt, height=300)

# --- Funções Técnicas ---
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

# ==========================================
# --- NOVO: FUNÇÃO DE LIMPEZA DE TEXTO ---
# ==========================================
def clean_ai_formatting(text):
    """
    Remove formatações agressivas da IA (Caps Lock, Title Case, Negritos excessivos)
    """
    # 1. Remove marcadores de negrito da IA (**)
    text = text.replace('**', '') 
    
    # 2. Corrige ALL CAPS (se a frase for longa e toda maiúscula)
    if len(text) > 40 and text.isupper():
        return text.capitalize() # Converte para apenas a 1ª letra maiúscula
    
    # 3. Corrige Title Case (Se mais de 70% das palavras começarem por maiúscula)
    words = text.split()
    if len(words) > 6:
        upper_starts = sum(1 for w in words if w and w[0].isupper())
        if upper_starts / len(words) > 0.7:
            return text.capitalize()
            
    return text

# --- Helpers Word ---
def format_bold_runs(paragraph, text):
    parts = re.split(r'(\*\*.*?\*\*)', text)
    for part in parts:
        if part.startswith('**') and part.endswith('**'):
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        else:
            paragraph.add_run(part)

def parse_markdown_to_docx(doc, markdown_text):
    # Flags para saber em que secção estamos
    in_critical_section = False 
    
    for line in markdown_text.split('\n'):
        line = line.strip()
        if not line: continue
        
        # Detetar Títulos
        if line.startswith('## ') or re.match(r'^\d+\.\s', line):
            clean = re.sub(r'^(##\s|\d+\.\s)', '', line).replace('*', '')
            doc.add_heading(clean.title(), level=1)
            
            # Ativa modo de limpeza extra para secções 6 e 7
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
            # Se estivermos nas secções críticas, limpamos a formatação
            if in_critical_section:
                clean_line = clean_ai_formatting(clean_line)
                p.add_run(clean_line) # Adiciona sem negritos
            else:
                format_bold_runs(p, clean_line)
        else:
            p = doc.add_paragraph()
            # Se estivermos nas secções críticas, limpamos a formatação
            if in_critical_section:
                clean_line = clean_ai_formatting(line)
                p.add_run(clean_line) # Adiciona sem negritos
            else:
                format_bold_runs(p, line)

def create_professional_word_doc(content, legal_links):
    doc = Document()
    style_normal = doc.styles['Normal']
    style_normal.font.name = 'Calibri'
    style_normal.font.size = Pt(11)
    
    style_h1 = doc.styles['Heading 1']
    style_h1.font.name = 'Cambria'
    style_h1.font.size = Pt(14)
    style_h1.font.bold = True
    style_h1.font.color.rgb = RGBColor(0, 51, 102)

    title = doc.add_heading('PARECER TÉCNICO EIA', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f'Data: {datetime.now().strftime("%d/%m/%Y")}').alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph('---')

    parse_markdown_to_docx(doc, content)
    
    doc.add_page_break()
    doc.add_heading('ANEXO: Legislação (Links DRE)', level=1)
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

if st.button("🚀 Gerar Relatório Profissional", type="primary", use_container_width=True):
    if not api_key:
        st.error("⚠️ Insira a API Key.")
    elif not selected_model:
        st.error("⚠️ Nenhum modelo selecionado.")
    elif not uploaded_file:
        st.warning("⚠️ Carregue o PDF.")
    else:
        with st.spinner(f"A processar com {selected_model}..."):
            pdf_text = extract_text_pypdf(uploaded_file)
            result = analyze_ai(pdf_text, instructions, api_key, selected_model)
            
            if "Erro" in result and len(result) < 200:
                st.error(result)
            else:
                st.success("✅ Sucesso!")
                with st.expander("Ver Texto"):
                    st.write(result)
                word_file = create_professional_word_doc(result, legal_refs)
                st.download_button("⬇️ Download Word", word_file.getvalue(), "Parecer_Tecnico.docx", on_click=reset_app, type="primary")
