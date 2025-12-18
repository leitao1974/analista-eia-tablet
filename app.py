import streamlit as st
from pypdf import PdfReader
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, NotFound, InvalidArgument
import io
from datetime import datetime
import re
import os
import time

# --- 1. CONFIGURAÇÃO OBRIGATÓRIA ---
st.set_page_config(page_title="Análise EIA Pro", page_icon="⚖️", layout="wide")

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

def reset_app():
    st.session_state.uploader_key += 1

# ==========================================
# --- 2. FUNÇÃO INTELIGENTE DE SELEÇÃO DE MODELO ---
# ==========================================
def get_best_model(api_key):
    """Descobre o melhor modelo 'Lite' ou 'Flash' disponível."""
    try:
        genai.configure(api_key=api_key)
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # 1. Prioridade: Lite 2.0 (Ouro para cotas)
        best = next((m for m in models if 'gemini-2.0-flash-lite' in m), None)
        # 2. Prioridade: Qualquer Lite
        if not best: best = next((m for m in models if 'lite' in m), None)
        # 3. Prioridade: Flash 1.5 (Estável)
        if not best: best = next((m for m in models if 'gemini-1.5-flash' in m), None)
        # 4. Fallback
        if not best and models: best = models[0]
        
        return best
    except:
        return None

# ==========================================
# --- 3. LEITURA DE LEGISLAÇÃO ---
# ==========================================
def load_legislation_knowledge_base(folder_path="legislacao"):
    legal_text = ""
    file_list = []
    
    if not os.path.exists(folder_path):
        return "", [], ["❌ Pasta 'legislacao' ausente."]

    files = os.listdir(folder_path)
    for filename in files:
        if not filename.lower().endswith('.pdf'): continue
        try:
            full_path = os.path.join(folder_path, filename)
            reader = PdfReader(full_path)
            content = ""
            for page in reader.pages:
                content += page.extract_text() + "\n"
            
            legal_text += f"\n\n=== LEI: {filename} ===\n{content}"
            file_list.append(filename)
        except: pass
            
    return legal_text, file_list, []

legal_knowledge_text, legal_files_list, _ = load_legislation_knowledge_base()

# ==========================================
# --- 4. INTERFACE ---
# ==========================================
st.title("⚖️ Análise Técnica EIA (RAG)")

with st.sidebar:
    st.header("🔐 Configuração")
    api_key = st.text_input("Google API Key (Use uma NOVA se der erro 429)", type="password")
    
    selected_model = None
    if api_key:
        selected_model = get_best_model(api_key)
        if selected_model:
            st.success(f"✅ Modelo: {selected_model}")
        else:
            st.error("Chave inválida.")

    st.divider()
    
    # TIPOLOGIAS (Mantive a lista completa)
    TIPOLOGIAS = [
        "1. Agricultura, Silvicultura e Aquicultura",
        "2. Indústria Extrativa (Minas/Pedreiras)",
        "3. Indústria Energética",
        "4. Produção e Transformação de Metais",
        "5. Indústria Mineral e Química",
        "6. Infraestruturas",
        "7. Engenharia Hidráulica",
        "8. Tratamento de Resíduos",
        "9. Projetos Urbanos e Turísticos",
        "Outra Tipologia"
    ]
    project_type = st.selectbox("Setor:", TIPOLOGIAS, index=1)
    
    if legal_files_list:
        st.info(f"📚 {len(legal_files_list)} Leis carregadas.")
    else:
        st.warning("Pasta 'legislacao' vazia.")

uploaded_files = st.file_uploader("Carregue o RNT (PDF)", type=['pdf'], accept_multiple_files=True, key=f"uploader_{st.session_state.uploader_key}")

# --- PROMPT ---
instructions = f"""
Atua como Perito Sénior em Engenharia do Ambiente.
Auditoria ao EIA do setor: {project_type}.

DADOS:
1. LEGISLAÇÃO OFICIAL (Verdade Absoluta)
2. EIA DO PROPONENTE

VERIFICA:
- Conformidade com o Simplex Ambiental (DL 11/2023).
- Se o EIA cita valores limites, valida-os contra a lei.

CAPÍTULOS:
1. ENQUADRAMENTO LEGAL
2. DESCRIÇÃO DO PROJETO
3. IMPACTES
4. MEDIDAS DE MITIGAÇÃO
5. ANÁLISE DE CONFORMIDADE (EIA vs LEI)
6. CONCLUSÕES
"""

# ==========================================
# --- 5. EXECUÇÃO ---
# ==========================================
def extract_text(files):
    text = ""
    for f in files:
        try:
            reader = PdfReader(f)
            for page in reader.pages: text += page.extract_text() + "\n"
        except: pass
    return text

def analyze_ai(p_text, l_text, prompt, key, model):
    try:
        genai.configure(api_key=key)
        m = genai.GenerativeModel(model)
        
        # CORTES DE SEGURANÇA (Para evitar novo bloqueio)
        limit = 200000 # Caracteres
        
        final_prompt = f"{prompt}\n\n### LEIS ###\n{l_text[:limit]}\n\n### EIA ###\n{p_text[:limit]}"
        
        return m.generate_content(final_prompt).text

    except ResourceExhausted:
        return "🚨 ERRO 429: Chave bloqueada. Crie uma nova chave API no Google AI Studio."
    except Exception as e:
        return f"❌ Erro: {str(e)}"

def create_doc(content, p_type):
    doc = Document()
    doc.add_heading('PARECER TÉCNICO', 0)
    doc.add_paragraph(f'Setor: {p_type} | Data: {datetime.now().strftime("%d/%m/%Y")}')
    
    for line in content.split('\n'):
        line = line.strip()
        if not line: continue
        if line.startswith('#'):
            h = line.replace('#','').strip()
            doc.add_heading(h, level=1 if '## ' in line else 2)
        else:
            p = doc.add_paragraph(line.replace('**',''))
            if line.startswith('- '): 
                p.style = 'List Bullet'
                p.text = line[2:]
                
    bio = io.BytesIO()
    doc.save(bio)
    return bio

st.markdown("---")
if st.button("🚀 Gerar Relatório", type="primary"):
    if not api_key: st.error("Falta API Key.")
    elif not uploaded_files: st.warning("Falta Ficheiro.")
    elif not selected_model: st.error("Erro Modelo.")
    else:
        with st.spinner(f"A processar com {selected_model}..."):
            time.sleep(1)
            eia_txt = extract_text(uploaded_files)
            res = analyze_ai(eia_txt, legal_knowledge_text, instructions, api_key, selected_model)
            
            if "🚨" in res or "❌" in res:
                st.error(res)
            else:
                st.success("✅ Feito!")
                with st.expander("Ver Relatório"): st.write(res)
                docx = create_doc(res, project_type)
                # LINHA CORRIGIDA ABAIXO:
                st.download_button("⬇️ Download Word", docx.getvalue(), "Parecer_Final.docx", type="primary", on_click=reset_app)
