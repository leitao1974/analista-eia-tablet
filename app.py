import streamlit as st
from pypdf import PdfReader
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
import io
from datetime import datetime
import re
import os
import time

# --- 1. CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Análise EIA", page_icon="⚖️", layout="wide")

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

def reset_app():
    st.session_state.uploader_key += 1

# ==========================================
# --- 2. LEITURA DE LEGISLAÇÃO (RAG) ---
# ==========================================

def load_legislation_knowledge_base(folder_path="legislacao"):
    legal_text = ""
    file_list = []
    
    if not os.path.exists(folder_path):
        return "", [], ["❌ Pasta 'legislacao' ausente."]

    files = os.listdir(folder_path)
    total_chars = 0
    
    for filename in files:
        if filename.startswith('.') or not filename.lower().endswith('.pdf'): continue
        try:
            full_path = os.path.join(folder_path, filename)
            reader = PdfReader(full_path)
            content = ""
            for page in reader.pages:
                content += page.extract_text() + "\n"
            
            legal_text += f"\n=== LEI: {filename} ===\n{content}"
            file_list.append(filename)
            total_chars += len(content)
        except: pass
            
    return legal_text, file_list, total_chars

legal_text_full, legal_files, legal_len = load_legislation_knowledge_base()

# ==========================================
# --- 3. INTERFACE LATERAL (DIAGNÓSTICO) ---
# ==========================================

with st.sidebar:
    st.header("1. Configuração")
    api_key = st.text_input("Google API Key", type="password")
    
    # Seleção de Modelo (Força Lite/Flash)
    selected_model = "gemini-1.5-flash" # Fallback seguro
    if api_key:
        try:
            genai.configure(api_key=api_key)
            models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            # Prioridade: Lite > 1.5 Flash > 2.0 Flash
            for m in models:
                if 'lite' in m: selected_model = m; break
                if '1.5-flash' in m: selected_model = m; break
            st.success(f"Modelo: {selected_model}")
        except: st.error("Chave inválida")

    st.divider()
    
    # --- DIAGNÓSTICO EM TEMPO REAL ---
    st.subheader("📊 Diagnóstico de Carga")
    st.caption("Verifique se o peso do texto excede o limite gratuito.")
    
    st.write(f"**Legislação:** {legal_len:,} caracteres")
    
    uploaded_files = st.file_uploader("Carregue o EIA", type=['pdf'], accept_multiple_files=True, key=f"uploader_{st.session_state.uploader_key}")
    
    eia_len = 0
    eia_text_full = ""
    
    if uploaded_files:
        for f in uploaded_files:
            try:
                reader = PdfReader(f)
                for page in reader.pages:
                    txt = page.extract_text()
                    if txt: eia_text_full += txt + "\n"
            except: pass
        eia_len = len(eia_text_full)
        st.write(f"**EIA (Projeto):** {eia_len:,} caracteres")
    
    total_load = legal_len + eia_len
    st.metric("Carga Total", f"{total_load:,}", delta="Limite rec: ~600.000", delta_color="inverse")
    
    if total_load > 600000:
        st.warning("⚠️ Carga elevada! O sistema cortará o texto automaticamente.")

# ==========================================
# --- 4. LÓGICA PRINCIPAL ---
# ==========================================

st.title("⚖️ Análise EIA (Modo Seguro)")

# Tipologias Simplificadas para Teste
TIPOLOGIAS = [
    "1. Agricultura/Silvicultura", "2. Indústria Extrativa", "3. Energia", 
    "4. Metais", "5. Química", "6. Infraestruturas", 
    "7. Hidráulica", "8. Resíduos", "9. Urbanismo", "Outra"
]
project_type = st.selectbox("Setor:", TIPOLOGIAS, index=1)

instructions = f"""
Atua como Perito Sénior em Engenharia do Ambiente.
Analisa o EIA ({project_type}) face à Legislação fornecida (Simplex DL 11/2023, RJAIA, etc.).
Verifica conformidade, prazos e isenções.

Estrutura:
1. ENQUADRAMENTO LEGAL
2. DESCRIÇÃO DO PROJETO
3. IMPACTES
4. MEDIDAS
5. ANÁLISE DE CONFORMIDADE (Crucial: Comparar EIA vs Lei)
6. CONCLUSÕES
"""

def analyze_safe(p_text, l_text, prompt, key, model):
    try:
        genai.configure(api_key=key)
        m = genai.GenerativeModel(model)
        
        # --- LIMITADOR DE SEGURANÇA (O SEGREDO) ---
        # A cota gratuita aceita aprox 1 milhão tokens/min, mas é instável.
        # Vamos definir um teto seguro de caracteres.
        SAFE_LIMIT_PER_BLOCK = 250000 # ~70 páginas de texto denso cada
        
        p_cut = p_text[:SAFE_LIMIT_PER_BLOCK]
        l_cut = l_text[:SAFE_LIMIT_PER_BLOCK]
        
        # Aviso interno para a IA saber que o texto foi cortado
        final_prompt = f"""
        {prompt}
        NOTA: O texto foi truncado por limites técnicos. Analisa o que foi fornecido.
        
        ### LEGISLAÇÃO ###
        {l_cut}
        
        ### EIA DO PROJETO ###
        {p_cut}
        """
        
        return m.generate_content(final_prompt).text

    except ResourceExhausted:
        return "🚨 ERRO 429 (COTA): A Google bloqueou o pedido. \n\nSOLUÇÃO: Aguarde 2 minutos e tente de novo (o 'balde' de tokens precisa de esvaziar)."
    except Exception as e:
        return f"❌ Erro: {str(e)}"

# --- GERAÇÃO DE WORD ---
def create_doc(content):
    doc = Document()
    doc.add_heading('PARECER TÉCNICO', 0)
    doc.add_paragraph(f"Data: {datetime.now().strftime('%d/%m/%Y')}")
    
    for line in content.split('\n'):
        line = line.strip()
        if not line: continue
        if line.startswith('#'):
            doc.add_heading(line.replace('#','').strip(), level=1 if '## ' in line else 2)
        else:
            p = doc.add_paragraph(line.replace('**',''))
            if line.startswith('- '): p.style = 'List Bullet'
            
    bio = io.BytesIO()
    doc.save(bio)
    return bio

# --- BOTÃO ---
if st.button("🚀 Analisar", type="primary"):
    if not api_key or not uploaded_files:
        st.error("Falta API Key ou Ficheiro.")
    else:
        with st.spinner("A processar (Modo Seguro)..."):
            time.sleep(1)
            res = analyze_safe(eia_text_full, legal_text_full, instructions, api_key, selected_model)
            
            if "🚨" in res or "❌" in res:
                st.error(res)
            else:
                st.success("Sucesso!")
                st.write(res)
                st.download_button("Download Word", create_doc(res), "Parecer.docx")
