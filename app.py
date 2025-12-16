import streamlit as st
from pypdf import PdfReader
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import google.generativeai as genai
import io
from datetime import datetime
import re
import os
import time

# --- Configuração OBRIGATÓRIA ---
st.set_page_config(page_title="Análise EIA", page_icon="⚖️", layout="wide")

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

def reset_app():
    st.session_state.uploader_key += 1

# ==========================================
# --- 1. LEITURA DE FICHEIROS ---
# ==========================================

def load_legislation_knowledge_base(folder_path="legislacao"):
    legal_text = ""
    file_list = []
    debug_log = [] 
    
    if not os.path.exists(folder_path):
        return "AVISO: Pasta não encontrada.", [], ["❌ Pasta 'legislacao' ausente."]

    files = os.listdir(folder_path)
    if not files:
        return "AVISO: Pasta vazia.", [], ["⚠️ Pasta 'legislacao' vazia."]

    for filename in files:
        if filename.startswith('.'): continue
        full_path = os.path.join(folder_path, filename)
        if os.path.isdir(full_path): continue
        if not filename.lower().endswith('.pdf'): continue

        try:
            reader = PdfReader(full_path)
            content = ""
            for page in reader.pages:
                content += page.extract_text() + "\n"
            legal_text += f"\n\n=== LEI: {filename} ===\n{content}"
            file_list.append(filename)
            debug_log.append(f"✅ '{filename}' ({len(reader.pages)} pág).")
        except Exception as e:
            debug_log.append(f"❌ Erro '{filename}': {str(e)}")
            
    return legal_text, file_list, debug_log

legal_knowledge_text, legal_files_list, load_logs = load_legislation_knowledge_base()

# ==========================================
# --- 0. STATUS ---
# ==========================================
st.title("⚖️ Análise Técnica e Legal (RAG)")

with st.expander("🕵️ STATUS (Legislação)", expanded=False):
    if os.path.exists("legislacao"):
        st.success(f"📂 Pasta 'legislacao' OK.")
        for log in load_logs:
            if "✅" in log: st.success(log)
            elif "❌" in log: st.error(log)
            else: st.info(log)
    else:
        st.error("❌ Pasta 'legislacao' não encontrada.")

# ==========================================
# --- 2. CONFIGURAÇÃO (MODELO 2.5 LITE) ---
# ==========================================

COMMON_LAWS = {
    "RJAIA (DL 151-B/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-116043164",
    "LUA (DL 75/2015)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2015-106562356",
    "Simplex (DL 11/2023)": "https://diariodarepublica.pt/dr/detalhe/decreto-lei/11-2023-207212480",
    "Lei da Água": "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2005-34563267"
}

SPECIFIC_LAWS = {
    "1. Agricultura/Silvicultura": {"NREAP": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-34789570"},
    "2. Indústria Extrativa": {"Minas/Pedreiras": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2001-34449875"},
    "Outra Tipologia": {"SIR": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2012-34658746"}
}

with st.sidebar:
    st.header("🔐 Configuração")
    api_key = st.text_input("Google API Key", type="password")
    
    selected_model = None
    if api_key:
        try:
            genai.configure(api_key=api_key)
            models_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            
            if models_list:
                # --- NOVA LÓGICA: CAÇA AO 'LITE' ---
                index_choice = 0
                found = False

                # 1. Prioridade Máxima: Lite (Melhor para Cota Gratuita)
                for i, m in enumerate(models_list):
                    if 'lite' in m and 'flash' in m:
                        index_choice = i
                        found = True
                        break
                
                # 2. Se não houver Lite, tenta o Flash 2.5 normal (mas evita imagens/robotics)
                if not found:
                    for i, m in enumerate(models_list):
                        if 'flash' in m and '2.5' in m and 'image' not in m:
                            index_choice = i
                            break

                selected_model = st.selectbox("Modelo IA:", models_list, index=index_choice)
                
                if "lite" in selected_model:
                    st.caption("✅ Modelo 'Lite' Selecionado (Ótimo para evitar bloqueios!)")
                else:
                    st.caption("⚠️ Atenção: Modelos não-Lite podem atingir o limite mais depressa.")
            else:
                st.error("Sem modelos.")
        except:
            st.error("Chave inválida.")

    st.divider()
    project_type = st.selectbox("Setor:", list(SPECIFIC_LAWS.keys()) + ["Outra Tipologia"])
    
    active_laws_links = COMMON_LAWS.copy()
    if project_type in SPECIFIC_LAWS:
        active_laws_links.update(SPECIFIC_LAWS[project_type])
    
    if legal_files_list:
        st.success(f"📚 {len(legal_files_list)} Leis na memória.")

uploaded_files = st.file_uploader("Carregue EIA", type=['pdf'], accept_multiple_files=True, key=f"uploader_{st.session_state.uploader_key}")

# --- PROMPT ---
instructions = f"""
Atua como Perito Sénior em Engenharia do Ambiente e Jurista.
Auditoria de conformidade rigorosa (RJAIA, LUA, Simplex Ambiental DL 11/2023).
Setor: {project_type}.

DADOS:
1. LEGISLAÇÃO OFICIAL (Usa como Verdade Absoluta)
2. EIA DO PROPONENTE

VERIFICA:
- Conformidade com o Simplex Ambiental (DL 11/2023) se aplicável.
- Validação de limites numéricos.

CAPÍTULOS:
## 1. ENQUADRAMENTO LEGAL
## 2. DESCRIÇÃO DO PROJETO
## 3. PRINCIPAIS IMPACTES
## 4. MEDIDAS DE MITIGAÇÃO
## 5. ANÁLISE CRÍTICA DE CONFORMIDADE LEGAL (Obrigatório comparar EIA vs Lei carregada)
## 6. FUNDAMENTAÇÃO
## 7. CITAÇÕES
## 8. CONCLUSÕES
"""

# ==========================================
# --- 3. PROCESSAMENTO ---
# ==========================================

def extract_text(files):
    text = ""
    for f in files:
        try:
            reader = PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        except: pass
    return text

def analyze_ai(p_text, l_text, prompt, key, model):
    genai.configure(api_key=key)
    # Configurações de segurança no mínimo para evitar falsos positivos em textos técnicos
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]
    m = genai.GenerativeModel(model)
    # Limita input para prevenir erros 429 violentos
    final = f"{prompt}\n\n### LEIS ###\n{l_text[:900000]}\n\n### EIA ###\n{p_text[:500000]}"
    return m.generate_content(final, safety_settings=safety_settings).text

def create_doc(txt, p_type):
    doc = Document()
    doc.add_heading('PARECER TÉCNICO', 0)
    doc.add_paragraph(txt)
    bio = io.BytesIO()
    doc.save(bio)
    return bio

if st.button("🚀 Gerar Relatório", type="primary"):
    if not api_key or not uploaded_files:
        st.error("Falta API Key ou EIA.")
    else:
        with st.spinner("A processar (pode demorar 60s)..."):
            time.sleep(1) # Pausa estratégica
            eia_txt = extract_text(uploaded_files)
            res = analyze_ai(eia_txt, legal_knowledge_text, instructions, api_key, selected_model)
            
            if "quota" in res.lower() or "429" in res:
                st.error("🚨 Erro de Cota Gratuita.")
                st.warning("O modelo 'Lite' também encheu. Solução final: Remova 1 ou 2 PDFs da legislação e tente de novo.")
                st.code(res)
            else:
                st.success("Feito!")
                st.write(res)
                docx = create_doc(res, project_type)
                st.download_button("Word", docx, "parecer.docx")

