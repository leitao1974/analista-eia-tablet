import streamlit as st
from pypdf import PdfReader
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, NotFound
import io
from datetime import datetime
import os
import time

# --- 1. CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Auditor EIA Pro", page_icon="⚖️", layout="wide")

st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #FF4B4B; color: white; }
    .stSuccess, .stInfo, .stWarning { border-left: 5px solid #ccc; }
</style>
""", unsafe_allow_html=True)

if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0
def reset_app(): st.session_state.uploader_key += 1

# ==========================================
# --- 2. MOTOR DE IA (DINÂMICO) ---
# ==========================================
def get_available_models(api_key):
    """
    Pergunta à Google quais os modelos disponíveis para ESTA chave.
    Retorna uma lista para o utilizador escolher.
    """
    try:
        genai.configure(api_key=api_key)
        # Lista apenas modelos que geram texto
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        return models
    except:
        return []

def analyze_robust(p_text, l_text, prompt, key, model_name):
    """
    Executa a análise com o modelo ESCOLHIDO.
    Inclui sistema de 'Retry' para erros de cota (429).
    """
    genai.configure(api_key=key)
    model = genai.GenerativeModel(model_name)
    safety = [{"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}]
    
    # Limite de segurança (aprox. 80-100 págs de cada lado)
    limit = 200000 
    
    final_prompt = f"""
    {prompt}
    
    ### FONTE DE VERDADE 1: LEGISLAÇÃO APLICÁVEL ###
    {l_text[:limit]}
    
    ### DOCUMENTO EM ANÁLISE: ESTUDO DE IMPACTE (EIA) ###
    {p_text[:limit]}
    """

    # Tenta 3 vezes se der erro de tráfego
    for attempt in range(3):
        try:
            return model.generate_content(final_prompt, safety_settings=safety).text
        except ResourceExhausted:
            time.sleep(5 + (attempt * 5)) # Espera progressiva (5s, 10s...)
            continue
        except NotFound:
            return f"❌ Erro 404: O modelo '{model_name}' desapareceu ou não é compatível. Tente outro na lista."
        except Exception as e:
            return f"❌ Erro Técnico: {str(e)}"
    
    return "🚨 A Google está sobrecarregada (Erro 429). Aguarde 2 minutos e tente novamente."

# ==========================================
# --- 3. GESTÃO DE TEXTO ---
# ==========================================
def extract_text_from_pdfs(uploaded_files):
    text = ""
    for f in uploaded_files:
        try:
            reader = PdfReader(f)
            for page in reader.pages: text += page.extract_text() + "\n"
        except: pass
    return text

def load_laws_from_folder():
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

base_legal_text, base_legal_files = load_laws_from_folder()

# ==========================================
# --- 4. INTERFACE ---
# ==========================================
st.title("⚖️ Auditoria EIA Pro")

with st.sidebar:
    st.header("1. Configuração")
    api_key = st.text_input("Chave API Google", type="password")
    
    # --- SELETOR DE MODELO DINÂMICO ---
    available_models = []
    selected_model_name = ""
    
    if api_key:
        available_models = get_available_models(api_key)
        if available_models:
            # Tenta encontrar um "Lite" ou "Flash" para por como defeito
            default_ix = 0
            for i, m in enumerate(available_models):
                if 'lite' in m or 'flash' in m:
                    default_ix = i
                    break
            
            selected_model_name = st.selectbox(
                "Modelo de IA:", 
                available_models, 
                index=default_ix,
                help="Se der erro, troque para outro modelo da lista."
            )
            if "lite" in selected_model_name: st.caption("🚀 Recomendado (Rápido)")
        else:
            st.warning("Insira uma chave válida para carregar modelos.")
    
    st.markdown("---")
    
    # TIPOLOGIAS
    TIPOLOGIAS = [
        "1. Agricultura, Silvicultura e Aquicultura",
        "2. Indústria Extrativa (Minas e Pedreiras)",
        "3. Indústria Energética",
        "4. Produção e Transformação de Metais",
        "5. Indústria Mineral e Química",
        "6. Infraestruturas (Vias, Aeroportos)",
        "7. Engenharia Hidráulica e Saneamento",
        "8. Tratamento de Resíduos",
        "9. Projetos Urbanos e Turísticos",
        "Outra Tipologia"
    ]
    project_type = st.selectbox("Setor de Atividade:", TIPOLOGIAS, index=1)
    
    st.markdown("---")
    st.header("2. Legislação")
    
    # Leis Fixas
    if base_legal_files:
        st.info(f"📂 {len(base_legal_files)} Leis na Base Fixa")
    else:
        st.warning("⚠️ Pasta 'legislacao' vazia.")
        
    # Leis Extra
    st.markdown("### ➕ Legislação Acessória")
    extra_laws = st.file_uploader("Adicionar PDFs extra", type=['pdf'], accept_multiple_files=True)

# --- ÁREA PRINCIPAL ---
st.subheader("3. Carregar Estudo de Impacte (EIA)")
eia_files = st.file_uploader(
    "Selecione os ficheiros do projeto (Memória Descritiva, RNT...)", 
    type=['pdf'], 
    accept_multiple_files=True, 
    key=f"uploader_{st.session_state.uploader_key}"
)

# ==========================================
# --- 5. EXECUÇÃO ---
# ==========================================

instructions = f"""
Atua como Perito Sénior em Engenharia do Ambiente e Jurista.
Auditoria de conformidade rigorosa ao EIA do setor: {project_type}.

DADOS:
1. LEGISLAÇÃO OFICIAL (Base de dados + Legislação Acessória).
2. DADOS DO PROJETO (EIA e anexos).

OBJETIVOS:
- Verificar conformidade com SIMPLEX AMBIENTAL (DL 11/2023) e RJAIA.
- Cruzar dados do EIA com a Legislação fornecida.
- Detetar falhas ou omissões.

RELATÓRIO:
## 1. ENQUADRAMENTO LEGAL
## 2. DESCRIÇÃO DO PROJETO
## 3. IMPACTES E MEDIDAS
## 4. AUDITORIA DE CONFORMIDADE LEGAL (EIA vs LEI)
## 5. CONCLUSÕES

Tom: Auditoria Técnica e Formal.
"""

def create_doc(content, p_type):
    doc = Document()
    doc.styles['Normal'].font.name = 'Calibri'
    doc.add_heading('PARECER TÉCNICO DE AUDITORIA', 0).alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f'Setor: {p_type} | Data: {datetime.now().strftime("%d/%m/%Y")}').alignment = WD_ALIGN_PARAGRAPH.CENTER
    
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

    bio = io.BytesIO()
    doc.save(bio)
    return bio

if st.button("🚀 INICIAR AUDITORIA", type="primary"):
    if not api_key: st.error("⚠️ Insira a Chave API.")
    elif not eia_files: st.warning("⚠️ Carregue o EIA.")
    elif not selected_model_name: st.error("⚠️ Selecione um Modelo na barra lateral.")
    else:
        with st.spinner(f"A auditar com {selected_model_name}..."):
            # Preparar textos
            eia_text = extract_text_from_pdfs(eia_files)
            extra_laws_text = extract_text_from_pdfs(extra_laws) if extra_laws else ""
            full_legal_text = base_legal_text + "\n\n=== LEGISLAÇÃO EXTRA ===\n" + extra_laws_text
            
            # Executar
            result = analyze_robust(eia_text, full_legal_text, instructions, api_key, selected_model_name)
            
            if "🚨" in result or "❌" in result:
                st.error(result)
            else:
                st.success("✅ Auditoria Concluída!")
                with st.expander("📄 Ler Parecer", expanded=True):
                    st.markdown(result)
                
                docx = create_doc(result, project_type)
                st.download_button("⬇️ Download Word", docx.getvalue(), "Parecer_Auditoria.docx", type="primary", on_click=reset_app)
