import streamlit as st
from pypdf import PdfReader
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, NotFound, InternalServerError
import io
from datetime import datetime
import os
import time

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Análise EIA Manual", page_icon="🔧", layout="wide")

if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0
def reset_app(): st.session_state.uploader_key += 1

# --- FUNÇÃO DE ANÁLISE COM "RETRY" (A SALVAÇÃO) ---
def analyze_with_retry(p_text, l_text, prompt, key, model_name):
    genai.configure(api_key=key)
    model = genai.GenerativeModel(model_name)
    
    # Configurações de segurança no mínimo
    safety = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]

    # Limite seguro de texto
    limit = 200000 
    final_prompt = f"{prompt}\n\n### LEIS ###\n{l_text[:limit]}\n\n### EIA ###\n{p_text[:limit]}"

    # TENTA 3 VEZES ANTES DE DESISTIR
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return model.generate_content(final_prompt, safety_settings=safety).text
        except ResourceExhausted:
            if attempt < max_retries - 1:
                time.sleep(10) # Espera 10 segundos antes de tentar de novo
                continue
            else:
                return "🚨 ERRO FINAL (429): Mesmo após 3 tentativas, a Google rejeitou. Tente outro Modelo na lista acima."
        except Exception as e:
            return f"❌ Erro: {str(e)}"
    
    return "Erro desconhecido."

# --- INTERFACE ---
st.title("⚖️ Análise Técnica (Modo Manual)")

with st.sidebar:
    st.header("🔐 Configuração")
    api_key = st.text_input("Google API Key", type="password")
    
    # SELEÇÃO MANUAL DE MODELO
    model_options = []
    if api_key:
        try:
            genai.configure(api_key=api_key)
            # Lista tudo o que existe
            model_options = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        except:
            st.error("Chave inválida.")

    # Dropdown para o utilizador escolher
    selected_model = st.selectbox(
        "Escolha o Modelo (Tente um por um):", 
        model_options if model_options else ["Insira a chave primeiro"],
        index=0 if model_options else 0
    )
    
    if "1.5-flash" in str(selected_model):
        st.success("⭐ Recomendado (Estável)")
    elif "lite" in str(selected_model):
        st.warning("⚠️ Lite: Pode ter limites baixos")
    
    st.divider()
    
    # TIPOLOGIAS
    TIPOLOGIAS = [
        "1. Agricultura/Silvicultura", "2. Indústria Extrativa", "3. Energia", 
        "4. Metais", "5. Química", "6. Infraestruturas", 
        "7. Hidráulica", "8. Resíduos", "9. Urbanismo", "Outra"
    ]
    project_type = st.selectbox("Setor:", TIPOLOGIAS, index=1)

# LEITURA LEIS
def load_laws():
    folder = "legislacao"
    t = ""
    f_list = []
    if os.path.exists(folder):
        for f in os.listdir(folder):
            if f.endswith('.pdf'):
                try:
                    r = PdfReader(os.path.join(folder, f))
                    for p in r.pages: t += p.extract_text() + "\n"
                    f_list.append(f)
                except: pass
    return t, f_list

legal_text, legal_files = load_laws()
if legal_files: st.sidebar.info(f"📚 {len(legal_files)} Leis carregadas.")

uploaded_files = st.file_uploader("Carregue o RNT", type=['pdf'], accept_multiple_files=True, key=f"uploader_{st.session_state.uploader_key}")

# --- EXECUÇÃO ---
instructions = f"""
Atua como Perito Sénior em Engenharia do Ambiente.
Auditoria ao EIA do setor: {project_type}.
DADOS: 1. LEGISLAÇÃO OFICIAL | 2. EIA DO PROPONENTE
VERIFICA: Conformidade Simplex Ambiental (DL 11/2023) e validade de licenças.
CAPÍTULOS: 1. ENQUADRAMENTO, 2. PROJETO, 3. IMPACTES, 4. MEDIDAS, 5. CONFORMIDADE LEGAL, 6. CONCLUSÕES.
"""

def extract_text(files):
    text = ""
    for f in files:
        try:
            reader = PdfReader(f)
            for page in reader.pages: text += page.extract_text() + "\n"
        except: pass
    return text

def create_doc(content, p_type):
    doc = Document()
    doc.add_heading('PARECER TÉCNICO', 0)
    doc.add_paragraph(f'Setor: {p_type} | Data: {datetime.now().strftime("%d/%m/%Y")}')
    for line in content.split('\n'):
        if line.strip(): doc.add_paragraph(line.replace('#','').replace('*',''))
    bio = io.BytesIO()
    doc.save(bio)
    return bio

st.markdown("---")
if st.button("🚀 Gerar Relatório (com Retry)", type="primary"):
    if not api_key or not uploaded_files:
        st.error("Falta dados.")
    else:
        with st.spinner(f"A tentar contactar {selected_model}... (Pode demorar se houver retries)"):
            eia_txt = extract_text(uploaded_files)
            res = analyze_with_retry(eia_txt, legal_text, instructions, api_key, selected_model)
            
            if "🚨" in res or "❌" in res:
                st.error(res)
            else:
                st.success("✅ Conseguimos!")
                st.write(res)
                st.download_button("Word", create_doc(res, project_type).getvalue(), "Parecer.docx", on_click=reset_app)
