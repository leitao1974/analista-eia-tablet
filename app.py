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

# --- 1. CONFIGURAÇÃO VISUAL (A "ESSÊNCIA") ---
st.set_page_config(page_title="Auditor EIA Pro", page_icon="⚖️", layout="wide")

# Estilo profissional para esconder mensagens de sistema feias
st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #FF4B4B; color: white; }
    .stSuccess { border-left: 5px solid #28a745; }
    .stError { border-left: 5px solid #dc3545; }
</style>
""", unsafe_allow_html=True)

if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0
def reset_app(): st.session_state.uploader_key += 1

# ==========================================
# --- 2. MOTOR INTELIGENTE (AUTOMÁTICO) ---
# ==========================================
def get_auto_model(api_key):
    """Escolhe o melhor modelo silenciosamente."""
    try:
        genai.configure(api_key=api_key)
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # A ordem de preferência para evitar cotas
        priorities = ['gemini-2.0-flash-lite', 'lite', 'gemini-1.5-flash', 'flash']
        
        for p in priorities:
            found = next((m for m in models if p in m), None)
            if found: return found
            
        return models[0] if models else None
    except: return None

def analyze_robust(p_text, l_text, prompt, key, model_name):
    """
    Tenta analisar. Se der erro 429, espera e tenta de novo sozinho (Retry Loop).
    O utilizador não vê isto a acontecer, só vê o resultado final.
    """
    genai.configure(api_key=key)
    model = genai.GenerativeModel(model_name)
    
    safety = [{"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}] # Simplificado
    
    # Corte de segurança silencioso
    limit = 250000 
    final_prompt = f"{prompt}\n\n### CONTEXTO LEGAL (LEGISLAÇÃO) ###\n{l_text[:limit]}\n\n### DOCUMENTO EM ANÁLISE (EIA) ###\n{p_text[:limit]}"

    # Loop de persistência (3 tentativas)
    for attempt in range(3):
        try:
            return model.generate_content(final_prompt, safety_settings=safety).text
        except ResourceExhausted:
            time.sleep(5 + (attempt * 5)) # Espera 5s, depois 10s...
            continue
        except Exception as e:
            return f"❌ Erro Técnico: {str(e)}"
    
    return "🚨 A Google está com tráfego elevado. Por favor, aguarde 2 minutos e tente novamente."

# ==========================================
# --- 3. DADOS E LEGISLAÇÃO ---
# ==========================================
def load_laws():
    folder = "legislacao"
    t = ""
    files = []
    if os.path.exists(folder):
        for f in os.listdir(folder):
            if f.endswith('.pdf'):
                try:
                    r = PdfReader(os.path.join(folder, f))
                    for p in r.pages: t += p.extract_text() + "\n"
                    files.append(f)
                except: pass
    return t, files

legal_text, legal_files = load_laws()

# LISTA COMPLETA DE TIPOLOGIAS (RESTAURADA)
TIPOLOGIAS = [
    "1. Agricultura, Silvicultura e Aquicultura",
    "2. Indústria Extrativa (Minas e Pedreiras)",
    "3. Indústria Energética",
    "4. Produção e Transformação de Metais",
    "5. Indústria Mineral e Química",
    "6. Infraestruturas (Rodovias, Ferrovias, Aeroportos)",
    "7. Engenharia Hidráulica (Barragens, Portos)",
    "8. Tratamento de Resíduos e Águas",
    "9. Projetos Urbanos e Turísticos",
    "Outra Tipologia"
]

COMMON_LAWS = {
    "RJAIA (DL 151-B/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-116043164",
    "Simplex Ambiental (DL 11/2023)": "https://diariodarepublica.pt/dr/detalhe/decreto-lei/11-2023-207212480"
}

# ==========================================
# --- 4. INTERFACE LIMPA ---
# ==========================================
st.title("⚖️ Auditoria EIA (IA)")

with st.sidebar:
    st.header("Parâmetros")
    api_key = st.text_input("Chave de Acesso (API Key)", type="password")
    
    st.markdown("---")
    project_type = st.selectbox("Setor de Atividade:", TIPOLOGIAS, index=1)
    
    st.markdown("---")
    if legal_files:
        st.success(f"📚 {len(legal_files)} Diplomas Legais Carregados")
        with st.expander("Ver lista"):
            for f in legal_files: st.caption(f"• {f}")
    else:
        st.warning("⚠️ Modo sem Legislação Local")

# Upload Limpo
uploaded_files = st.file_uploader("Carregue o EIA ou RNT (PDF)", type=['pdf'], accept_multiple_files=True, key=f"uploader_{st.session_state.uploader_key}")

# --- PROMPT ORIGINAL (PERITO SÉNIOR) ---
instructions = f"""
Atua como Perito Sénior em Engenharia do Ambiente e Jurista.
Realiza uma AUDITORIA DE CONFORMIDADE RIGOROSA ao EIA deste projeto do setor: {project_type}.

TENS ACESSO A:
1. LEGISLAÇÃO OFICIAL (Verdade Absoluta - usa para validar prazos e limites).
2. DADOS DO PROJETO (EIA).

CRITÉRIOS DE AUDITORIA:
- Verifica conformidade com o SIMPLEX AMBIENTAL (DL 11/2023).
- Verifica validade das licenças mencionadas.
- Cruza os valores limite do EIA com a Lei.

ESTRUTURA DO RELATÓRIO:
## 1. ENQUADRAMENTO LEGAL
## 2. DESCRIÇÃO DO PROJETO
## 3. ANÁLISE DE IMPACTES E MEDIDAS
## 4. AUDITORIA DE CONFORMIDADE LEGAL (Obrigatório: Comparar EIA vs LEI)
## 5. CONCLUSÕES E PARECER FINAL

Tom: Auditoria Técnica e Formal.
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

def create_doc(content, p_type):
    doc = Document()
    doc.styles['Normal'].font.name = 'Calibri'
    doc.add_heading('PARECER TÉCNICO DE AUDITORIA', 0).alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f'Setor: {p_type} | Data: {datetime.now().strftime("%d/%m/%Y")}').alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph('_' * 70)
    
    # Parser Simples de Markdown para Word
    for line in content.split('\n'):
        line = line.strip()
        if not line: continue
        if line.startswith('#'):
            clean = line.replace('#','').strip()
            doc.add_heading(clean, level=1 if '## ' in line else 2)
        else:
            p = doc.add_paragraph(line.replace('**',''))
            if line.startswith('- '): 
                p.style = 'List Bullet'
                p.text = line[2:]
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.add_page_break()
    doc.add_heading('Fontes Consultadas', 1)
    doc.add_paragraph("Legislação:", style='List Bullet')
    for k, v in COMMON_LAWS.items(): doc.add_paragraph(f"{k}", style='List Bullet')
                
    bio = io.BytesIO()
    doc.save(bio)
    return bio

if st.button("🚀 INICIAR AUDITORIA", type="primary"):
    if not api_key: st.error("⚠️ Insira a Chave API.")
    elif not uploaded_files: st.warning("⚠️ Carregue o documento EIA.")
    else:
        # A magia acontece aqui: Seleção automática e invisível
        best_model = get_auto_model(api_key)
        
        if not best_model:
            st.error("Erro: Chave API inválida.")
        else:
            with st.spinner("🕵️‍♂️ O Auditor IA está a analisar a conformidade legal..."):
                eia_text = extract_text(uploaded_files)
                
                # Chama a função robusta (que tenta 3x se falhar)
                result = analyze_robust(eia_text, legal_text, instructions, api_key, best_model)
                
                if "🚨" in result or "❌" in result:
                    st.error(result)
                else:
                    st.success("✅ Auditoria Concluída com Sucesso!")
                    with st.expander("📄 Ler Parecer Técnico", expanded=True):
                        st.markdown(result)
                    
                    docx = create_doc(result, project_type)
                    st.download_button("⬇️ Descarregar Relatório (Word)", docx.getvalue(), "Parecer_Auditoria.docx", type="primary", on_click=reset_app)
