import streamlit as st
from pypdf import PdfReader
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
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
# --- 2. MOTOR DE IA (ROBUSTO) ---
# ==========================================
def get_auto_model(api_key):
    """Escolhe o melhor modelo disponível, priorizando LITE e FLASH."""
    try:
        genai.configure(api_key=api_key)
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # Ordem de preferência: 2.0 Lite -> Lite genérico -> 1.5 Flash
        priorities = ['gemini-2.0-flash-lite', 'lite', 'gemini-1.5-flash', 'flash']
        
        for p in priorities:
            found = next((m for m in models if p in m), None)
            if found: return found
            
        return models[0] if models else None
    except: return None

def analyze_robust(p_text, l_text, prompt, key, model_name):
    """
    Executa a análise com sistema de 'Retry' (tentativas automáticas) 
    para contornar erros momentâneos de cota (429).
    """
    genai.configure(api_key=key)
    model = genai.GenerativeModel(model_name)
    safety = [{"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}]
    
    # Limite de segurança para evitar bloqueios longos (aprox. 80-100 págs de cada lado)
    limit = 250000 
    
    final_prompt = f"""
    {prompt}
    
    ### FONTE DE VERDADE 1: LEGISLAÇÃO APLICÁVEL ###
    (Usa isto para validar conformidade e limites)
    {l_text[:limit]}
    
    ### DOCUMENTO EM ANÁLISE: ESTUDO DE IMPACTE (EIA) ###
    (O texto a auditar)
    {p_text[:limit]}
    """

    # Tenta 3 vezes se der erro de tráfego
    for attempt in range(3):
        try:
            return model.generate_content(final_prompt, safety_settings=safety).text
        except ResourceExhausted:
            time.sleep(5 + (attempt * 5)) # Espera progressiva (5s, 10s...)
            continue
        except Exception as e:
            return f"❌ Erro Técnico: {str(e)}"
    
    return "🚨 A Google está sobrecarregada neste momento (Erro 429). Aguarde 2 minutos e tente novamente."

# ==========================================
# --- 3. GESTÃO DE FICHEIROS ---
# ==========================================
def extract_text_from_pdfs(uploaded_files):
    """Extrai texto de uma lista de ficheiros carregados."""
    text = ""
    for f in uploaded_files:
        try:
            reader = PdfReader(f)
            for page in reader.pages: text += page.extract_text() + "\n"
        except: pass
    return text

def load_laws_from_folder():
    """Lê legislação fixa da pasta local."""
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

# Carrega legislação base (da pasta)
base_legal_text, base_legal_files = load_laws_from_folder()

# ==========================================
# --- 4. INTERFACE ---
# ==========================================
st.title("⚖️ Auditoria EIA Pro")

# --- BARRA LATERAL (CONFIGURAÇÃO + LEIS EXTRA) ---
with st.sidebar:
    st.header("1. Configuração")
    api_key = st.text_input("Chave API Google", type="password")
    
    # TIPOLOGIAS DO RJAIA
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
    st.markdown("---")
    project_type = st.selectbox("Setor de Atividade:", TIPOLOGIAS, index=1)
    
    st.markdown("---")
    st.header("2. Legislação")
    
    # Mostra leis da pasta (fixas)
    if base_legal_files:
        st.info(f"📂 {len(base_legal_files)} Diplomas na Base de Dados (Pasta)")
        with st.expander("Ver lista fixa"):
            for f in base_legal_files: st.caption(f"• {f}")
    else:
        st.warning("⚠️ Pasta 'legislacao' vazia.")
        
    # Uploader de Leis Extra (NOVO!)
    st.markdown("### ➕ Legislação Acessória")
    extra_laws = st.file_uploader(
        "Adicionar Portarias/Leis extra (PDF)", 
        type=['pdf'], 
        accept_multiple_files=True,
        help="Estes ficheiros serão cruzados juntamente com a legislação base."
    )

# --- ÁREA PRINCIPAL (UPLOAD EIA) ---
st.subheader("3. Carregar Estudo de Impacte (EIA)")
eia_files = st.file_uploader(
    "Selecione os ficheiros do projeto (Memória Descritiva, RNT, Anexos...)", 
    type=['pdf'], 
    accept_multiple_files=True, 
    key=f"uploader_{st.session_state.uploader_key}"
)

# ==========================================
# --- 5. LÓGICA DE AUDITORIA ---
# ==========================================

# Prompt Profissional
instructions = f"""
Atua como Perito Sénior em Engenharia do Ambiente e Jurista.
Realiza uma AUDITORIA DE CONFORMIDADE RIGOROSA ao EIA deste projeto do setor: {project_type}.

TENS ACESSO A:
1. LEGISLAÇÃO OFICIAL (Inclui base de dados e legislação acessória fornecida).
2. DADOS DO PROJETO (EIA e anexos).

A TUA MISSÃO:
- Verificar conformidade com o SIMPLEX AMBIENTAL (DL 11/2023) e RJAIA.
- Cruzar dados do EIA com a Legislação fornecida (ex: limites de emissão, distâncias, prazos).
- Detetar falhas ou omissões no EIA.

ESTRUTURA DO RELATÓRIO:
## 1. ENQUADRAMENTO LEGAL
## 2. DESCRIÇÃO DO PROJETO
## 3. ANÁLISE DE IMPACTES E MEDIDAS
## 4. AUDITORIA DE CONFORMIDADE LEGAL (Obrigatório: Comparar EIA vs LEI)
## 5. CONCLUSÕES E PARECER FINAL

Tom: Auditoria Técnica, Formal e Crítico.
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
    elif not eia_files: st.warning("⚠️ Carregue pelo menos um ficheiro do EIA.")
    else:
        # Seleção de Modelo
        best_model = get_auto_model(api_key)
        
        if not best_model:
            st.error("Erro: Chave API inválida.")
        else:
            with st.spinner(f"A preparar Auditoria com {best_model}..."):
                # 1. Preparar Texto do EIA
                eia_text = extract_text_from_pdfs(eia_files)
                
                # 2. Preparar Texto da Lei (Pasta + Extras)
                extra_laws_text = extract_text_from_pdfs(extra_laws) if extra_laws else ""
                full_legal_text = base_legal_text + "\n\n=== LEGISLAÇÃO ACESSÓRIA EXTRA ===\n" + extra_laws_text
                
                # 3. Executar Análise
                result = analyze_robust(eia_text, full_legal_text, instructions, api_key, best_model)
                
                if "🚨" in result or "❌" in result:
                    st.error(result)
                else:
                    st.success("✅ Auditoria Concluída!")
                    with st.expander("📄 Ler Parecer Técnico", expanded=True):
                        st.markdown(result)
                    
                    docx = create_doc(result, project_type)
                    st.download_button("⬇️ Descarregar Relatório (Word)", docx.getvalue(), "Parecer_Auditoria.docx", type="primary", on_click=reset_app)
