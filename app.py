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
st.set_page_config(page_title="Analista EIA (Flash)", page_icon="⚡", layout="wide")

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

def reset_app():
    st.session_state.uploader_key += 1

# --- Interface ---
st.title("⚡ Analista EIA Pro (Versão Rápida)")
st.markdown("Usa o modelo **Gemini 1.5 Flash** para evitar erros de quota e analisar documentos longos rapidamente.")

with st.sidebar:
    st.header("🔐 Configuração")
    api_key = st.text_input("Google API Key", type="password")
    
uploaded_file = st.file_uploader("Carregue o PDF", type=['pdf'], key=f"uploader_{st.session_state.uploader_key}")

# --- MATRIZ JURÍDICA ---
legal_refs = {
    "RJAIA (DL 151-B/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-116043164",
    "REDE NATURA (DL 140/99)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/1999-34460975",
    "RUÍDO (DL 9/2007)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2007-34526556",
    "ÁGUA (Lei 58/2005)": "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2005-34563267"
}
legal_context_str = "\n".join([f"- {k}: {v}" for k, v in legal_refs.items()])

# --- PROMPT ---
default_prompt = f"""
Atua como Perito Sénior em Engenharia do Ambiente e Jurista.
Realiza uma auditoria técnica e legal ao EIA.

CONTEXTO LEGISLATIVO:
{legal_context_str}

Usa Markdown para formatar:
- `## TÍTULO` para capítulos.
- `**negrito**` para destaques.
- Listas com `-`.

Estrutura o relatório EXATAMENTE nestes 7 Capítulos:

## 1. ENQUADRAMENTO LEGAL E CONFORMIDADE
   - O projeto enquadra-se no RJAIA?

## 2. PRINCIPAIS IMPACTES (Técnico)
   - Análise por descritor.

## 3. MEDIDAS DE MITIGAÇÃO PROPOSTAS
   - Lista as medidas.

## 4. ANÁLISE CRÍTICA E BENCHMARKING
   - As medidas cumprem os limites legais? Comparação com boas práticas.

## 5. FUNDAMENTAÇÃO
   - Usa `(Pág. X)`.

## 6. CITAÇÕES RELEVANTES
   - Transcreve 3 frases entre aspas.

## 7. CONCLUSÕES
   - Parecer Final.

Tom: Formal, Técnico e Jurídico.
"""
instructions = st.text_area("Instruções:", value=default_prompt, height=300)

# ==========================================
# --- SELEÇÃO DE MODELO SEGURA (CORREÇÃO DO ERRO) ---
# ==========================================
def get_safe_model(key):
    """
    Força o uso do 'gemini-1.5-flash' ou 'gemini-1.5-flash-latest'.
    Evita modelos 'pro' ou experimentais que dão erro de quota.
    """
    try:
        genai.configure(api_key=key)
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # 1. Tenta encontrar especificamente o FLASH (que é gratuito e rápido)
        for m in models:
            if '1.5-flash' in m:
                return m
        
        # 2. Se não houver flash, tenta o Pro 1.5
        for m in models:
            if '1.5-pro' in m:
                return m
                
        # 3. Recurso final
        return 'models/gemini-pro'

    except Exception as e:
        return None

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
        # O Flash aguenta muito texto, 1 milhão de tokens.
        # Cortamos aos 800.000 caracteres para ser seguro.
        safe_text = text[:800000] 
        
        # Retry mechanism simples em caso de sobrecarga momentânea
        try:
            response = model.generate_content(f"{prompt}\n\nDADOS DO PDF:\n{safe_text}")
        except Exception:
            time.sleep(2) # Espera 2 segundos e tenta de novo
            response = model.generate_content(f"{prompt}\n\nDADOS DO PDF:\n{safe_text}")
            
        return response.text
    except Exception as e:
        return f"Erro IA: {str(e)}"

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
    for line in markdown_text.split('\n'):
        line = line.strip()
        if not line: continue
        if line.startswith('## ') or re.match(r'^\d+\.\s', line):
            clean = re.sub(r'^(##\s|\d+\.\s)', '', line)
            doc.add_heading(clean.upper(), level=1)
        elif line.startswith('### '):
            doc.add_heading(line[4:], level=2)
        elif line.startswith('- ') or line.startswith('* '):
            p = doc.add_paragraph(style='List Bullet')
            format_bold_runs(p, line[2:])
        else:
            p = doc.add_paragraph()
            format_bold_runs(p, line)

def create_professional_word_doc(content, legal_links):
    doc = Document()
    style_normal = doc.styles['Normal']
    style_normal.font.name = 'Calibri'
    style_normal.font.size = Pt(11)
    style_normal.paragraph_format.space_after = Pt(8)
    
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

# --- BOTÃO DE AÇÃO ---
st.markdown("---")

if st.button("🚀 Gerar Relatório Profissional", type="primary", use_container_width=True):
    if not api_key:
        st.error("⚠️ ERRO: Insira a Google API Key.")
    elif not uploaded_file:
        st.warning("⚠️ ERRO: Carregue um ficheiro PDF.")
    else:
        with st.spinner("🔍 A selecionar o modelo Flash e a processar..."):
            
            # 1. Seleção Segura do Modelo
            model_name = get_safe_model(api_key)
            
            if not model_name:
                st.error("Erro: Chave API inválida ou sem acesso a modelos.")
            else:
                # 2. Extrair
                pdf_text = extract_text_pypdf(uploaded_file)
                
                # 3. Analisar
                result = analyze_ai(pdf_text, instructions, api_key, model_name)
                
                if "Erro" in result and len(result) < 200:
                    st.error(result)
                else:
                    st.success(f"✅ Sucesso! (Modelo usado: {model_name})")
                    with st.expander("Ver Texto"):
                        st.write(result)
                    
                    # 4. Word
                    word_file = create_professional_word_doc(result, legal_refs)
                    
                    st.download_button(
                        label="⬇️ DOWNLOAD RELATÓRIO WORD (.docx)", 
                        data=word_file.getvalue(), 
                        file_name="Parecer_Tecnico_EIA.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        on_click=reset_app,
                        type="primary"
                    )
