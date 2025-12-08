import streamlit as st
from pypdf import PdfReader
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import google.generativeai as genai
import io
from datetime import datetime
import re

# --- Configuração ---
st.set_page_config(page_title="Analista EIA (Auto-Detect)", page_icon="🛡️", layout="wide")

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

def reset_app():
    st.session_state.uploader_key += 1

# --- Interface ---
st.title("🛡️ Analista EIA Pro (Sistema Auto-Adaptável)")
st.markdown("Esta versão deteta automaticamente os modelos de IA disponíveis na sua conta para evitar erros.")

with st.sidebar:
    st.header("🔐 Configuração")
    api_key = st.text_input("Google API Key", type="password")
    if api_key:
        st.success("Chave inserida.")

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
# --- NOVA FUNÇÃO DE AUTO-DETEÇÃO (A SOLUÇÃO) ---
# ==========================================
def find_best_model(key):
    """
    Pergunta à Google que modelos existem e escolhe o melhor.
    Evita erros de 'Model Not Found'.
    """
    try:
        genai.configure(api_key=key)
        available_models = []
        
        # Listar modelos que suportam geração de texto
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        
        if not available_models:
            return None, "Nenhum modelo compatível encontrado na conta."

        # Lógica de Escolha (Prioridade: Flash > Pro > Outros)
        chosen = None
        
        # 1. Tenta encontrar o Flash (mais rápido e capaz)
        for m in available_models:
            if 'flash' in m and '1.5' in m:
                chosen = m
                break
        
        # 2. Se não houver Flash, tenta o Pro (mais recente)
        if not chosen:
            for m in available_models:
                if '1.5' in m and 'pro' in m:
                    chosen = m
                    break

        # 3. Se não houver 1.5, tenta o Pro clássico
        if not chosen:
            for m in available_models:
                if 'gemini-pro' in m:
                    chosen = m
                    break
        
        # 4. Se falhar tudo, pega no primeiro da lista
        if not chosen:
            chosen = available_models[0]

        return chosen, f"Modelo selecionado: {chosen}"

    except Exception as e:
        return None, f"Erro ao listar modelos: {str(e)}"

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
        safe_text = text[:100000] # Limite de segurança
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
        with st.spinner("🔍 A detetar modelo de IA e a processar..."):
            
            # 1. AUTO-DETEÇÃO DO MODELO (O SEGREDO)
            model_name, status_msg = find_best_model(api_key)
            
            if not model_name:
                # Se falhar aqui, o problema é 100% da chave API
                st.error(f"Erro Crítico: {status_msg}")
            else:
                st.info(f"✅ {status_msg}") # Mostra qual modelo foi escolhido
                
                # 2. Extrair
                pdf_text = extract_text_pypdf(uploaded_file)
                
                # 3. Analisar
                result = analyze_ai(pdf_text, instructions, api_key, model_name)
                
                if "Erro" in result and len(result) < 200:
                    st.error(result)
                else:
                    st.success("✅ Sucesso!")
                    with st.expander("Ver Texto"):
                        st.write(result)
                    
                    # 4. Word
                    word_file = create_professional_word_doc(result, legal_refs)
                    
                    st.download_button(
                        label="⬇️ DOWNLOAD RELATÓRIO WORD (.docx)", 
                        data=word_file.getvalue(), 
                        file_name="Parecer_Tecnico_Final.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        on_click=reset_app,
                        type="primary"
                    )
