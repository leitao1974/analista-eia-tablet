import streamlit as st
from pypdf import PdfReader
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, NotFound
import io
from datetime import datetime
import re
import os
import time

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="Análise EIA 2.0", page_icon="⚖️", layout="wide")

if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0
def reset_app(): st.session_state.uploader_key += 1

# --- 2. FUNÇÃO INTELIGENTE DE SELEÇÃO DE MODELO ---
def get_best_model(api_key):
    """Descobre qual o melhor modelo disponível na chave do utilizador."""
    try:
        genai.configure(api_key=api_key)
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # 1. Prioridade Absoluta: LITE (Melhor para cota)
        best = next((m for m in models if 'lite' in m), None)
        # 2. Prioridade Secundária: FLASH 2.0 ou 1.5
        if not best: best = next((m for m in models if 'flash' in m), None)
        # 3. Fallback
        if not best and models: best = models[0]
        
        return best
    except:
        return None

# --- 3. LEITURA DE LEGISLAÇÃO ---
def load_laws():
    folder = "legislacao"
    text = ""
    files = []
    if os.path.exists(folder):
        for f in os.listdir(folder):
            if f.lower().endswith('.pdf'):
                try:
                    reader = PdfReader(os.path.join(folder, f))
                    t = ""
                    for p in reader.pages: t += p.extract_text() or ""
                    text += f"\n=== LEGISLAÇÃO: {f} ===\n{t}"
                    files.append(f)
                except: pass
    return text, files

legal_text, legal_files = load_laws()

# --- 4. BARRA LATERAL ---
with st.sidebar:
    st.header("🔐 Configuração")
    api_key = st.text_input("Google API Key", type="password")
    
    current_model = None
    if api_key:
        current_model = get_best_model(api_key)
        if current_model:
            st.success(f"✅ Modelo Ativo: {current_model}")
            if "lite" in current_model: st.caption("🚀 Modo Lite ativado (Ideal para cotas).")
        else:
            st.error("Chave inválida ou sem modelos.")

    st.divider()
    
    # TIPOLOGIAS COMPLETAS
    TIPOLOGIAS = [
        "1. Agricultura, Silvicultura e Aquicultura",
        "2. Indústria Extrativa (Minas/Pedreiras)",
        "3. Indústria Energética",
        "4. Produção e Transformação de Metais",
        "5. Indústria Mineral e Química",
        "6. Infraestruturas (Vias, Aeroportos)",
        "7. Engenharia Hidráulica e Saneamento",
        "8. Tratamento de Resíduos",
        "9. Projetos Urbanos e Turísticos",
        "Outra Tipologia"
    ]
    project_type = st.selectbox("Setor:", TIPOLOGIAS, index=1)
    
    if legal_files:
        st.info(f"📚 {len(legal_files)} Leis na memória.")
    else:
        st.warning("Pasta 'legislacao' vazia.")

uploaded_files = st.file_uploader("Carregue o EIA/RNT", type=['pdf'], accept_multiple_files=True, key=f"uploader_{st.session_state.uploader_key}")

# --- 5. PROMPT E LÓGICA ---
instructions = f"""
Atua como Perito Sénior em Engenharia do Ambiente e Jurista.
Auditoria de conformidade rigorosa (RJAIA, LUA, Simplex Ambiental DL 11/2023).
Setor: {project_type}.

DADOS:
1. LEGISLAÇÃO OFICIAL (Verdade Absoluta)
2. EIA DO PROPONENTE

VERIFICA:
- Conformidade com o Simplex Ambiental (DL 11/2023).
- Validação de prazos e isenções.

CAPÍTULOS:
## 1. ENQUADRAMENTO LEGAL
## 2. DESCRIÇÃO DO PROJETO
## 3. PRINCIPAIS IMPACTES
## 4. MEDIDAS DE MITIGAÇÃO
## 5. ANÁLISE CRÍTICA DE CONFORMIDADE LEGAL (Obrigatório comparar EIA vs LEI)
## 6. CONCLUSÕES
"""

def analyze_ai(p_text, l_text, prompt, key, model):
    try:
        genai.configure(api_key=key)
        m = genai.GenerativeModel(model)
        
        # Limite de segurança para evitar novo bloqueio
        # 300k chars = ~100 páginas densas. Suficiente para RNT + Simplex.
        limit = 300000
        
        final_prompt = f"{prompt}\n\n### LEIS ###\n{l_text[:limit]}\n\n### EIA ###\n{p_text[:limit]}"
        
        return m.generate_content(final_prompt).text

    except ResourceExhausted:
        return "🚨 AINDA BLOQUEADO (429): A Google pede mais tempo de pausa. Espere mais 10 minutos."
    except Exception as e:
        return f"❌ Erro Técnico: {str(e)}"

# --- 6. GERAÇÃO DE WORD ---
def create_doc(content, p_type):
    doc = Document()
    doc.add_heading('PARECER TÉCNICO EIA', 0)
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

# --- 7. BOTÃO ---
st.markdown("---")
if st.button("🚀 Gerar Relatório", type="primary"):
    if not api_key or not uploaded_files:
        st.error("Falta API Key ou Ficheiro.")
    elif not current_model:
        st.error("Erro na deteção do modelo.")
    else:
        with st.spinner(f"A processar com {current_model}..."):
            # Ler PDF do EIA
            eia_full = ""
            for f in uploaded_files:
                try:
                    r = PdfReader(f)
                    for p in r.pages: eia_full += p.extract_text() or ""
                except: pass
            
            # Executar IA
            res = analyze_ai(eia_full, legal_text, instructions, api_key, current_model)
            
            if "🚨" in res or "❌" in res:
                st.error(res)
            else:
                st.success("✅ Sucesso!")
                st.markdown(res)
                docx = create_doc(res, project_type)
                st.download_button("⬇️ Download Word", docx, "Parecer_Auditado.docx")
