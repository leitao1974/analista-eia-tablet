import streamlit as st
from pypdf import PdfReader
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, InternalServerError
import io
from datetime import datetime
import os
import time

# --- 1. CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Auditor EIA Pro", page_icon="⚖️", layout="wide")

st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #FF4B4B; color: white; font-weight: bold; }
    .stSuccess, .stInfo, .stWarning { border-left: 5px solid #ccc; }
</style>
""", unsafe_allow_html=True)

if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0
def reset_app(): st.session_state.uploader_key += 1

# ==========================================
# --- 2. MOTOR IA (MODO ESTÁVEL - 1.5 FLASH) ---
# ==========================================

def analyze_stable(p_text, l_text, prompt, key):
    """
    Usa estritamente o modelo gemini-1.5-flash para garantir estabilidade.
    """
    genai.configure(api_key=key)
    # FORÇAMOS O MODELO ESTÁVEL (Não usamos Lite nem 2.0 para evitar erros 429/404)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    safety = [{"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}]
    
    # LIMITE DE SEGURANÇA MÁXIMA
    # 60.000 caracteres = ~20 páginas densas. 
    # Isto garante que o pedido é leve o suficiente para passar em qualquer conta gratuita.
    limit = 60000 
    
    final_prompt = f"""
    {prompt}
    
    === FONTE DE VERDADE: LEGISLAÇÃO ===
    (Usa apenas estes excertos para validar)
    {l_text[:limit]}
    
    === DOCUMENTO EM ANÁLISE: EIA ===
    (Analisa este conteúdo)
    {p_text[:limit]}
    """

    # Retry Loop Lento (Espera 20s entre tentativas)
    for attempt in range(3):
        try:
            return model.generate_content(final_prompt, safety_settings=safety).text
        except ResourceExhausted:
            st.toast(f"⚠️ Tráfego elevado. A tentar de novo em 15 segundos... (Tentativa {attempt+1}/3)")
            time.sleep(15) 
            continue
        except InternalServerError:
            time.sleep(5)
            continue
        except Exception as e:
            return f"❌ Erro Técnico: {str(e)}"
    
    return "🚨 A Google continua a rejeitar a conexão (Erro 429 Persistente). Por favor, aguarde 30 minutos antes de tentar novamente."

# ==========================================
# --- 3. GESTÃO DE FICHEIROS ---
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

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("1. Configuração")
    api_key = st.text_input("Chave API Google", type="password")
    
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
    
    # LEIS FIXAS
    if base_legal_files:
        st.success(f"📂 {len(base_legal_files)} Diplomas na Base (Pasta)")
        with st.expander("Ver lista fixa"):
            for f in base_legal_files: st.caption(f"• {f}")
    else:
        st.warning("⚠️ Pasta 'legislacao' vazia.")
        
    # LEIS ACESSÓRIAS (MÚLTIPLOS FICHEIROS)
    st.markdown("### ➕ Legislação Acessória")
    extra_laws = st.file_uploader(
        "Carregar Portarias/Leis extra", 
        type=['pdf'], 
        accept_multiple_files=True
    )

# --- ÁREA PRINCIPAL (EIA - MÚLTIPLOS FICHEIROS) ---
st.subheader("3. Documentos do Projeto (EIA)")
st.info("Pode carregar múltiplos ficheiros: Memória Descritiva, RNT, Anexos, Peças Desenhadas...")
eia_files = st.file_uploader(
    "Arraste os ficheiros para aqui", 
    type=['pdf'], 
    accept_multiple_files=True, 
    key=f"uploader_{st.session_state.uploader_key}"
)

# ==========================================
# --- 5. EXECUÇÃO ---
# ==========================================

instructions = f"""
Atua como Perito Sénior em Engenharia do Ambiente e Jurista.
Realiza uma AUDITORIA DE CONFORMIDADE RIGOROSA ao EIA deste projeto do setor: {project_type}.

TENS ACESSO A:
1. LEGISLAÇÃO OFICIAL (Base de dados + Legislação Extra).
2. DADOS DO PROJETO (Todos os ficheiros carregados).

A TUA MISSÃO:
- Verificar conformidade com o SIMPLEX AMBIENTAL (DL 11/2023).
- Verificar validade das licenças e prazos.
- Cruzar dados do EIA com a Lei.

ESTRUTURA DO RELATÓRIO:
## 1. ENQUADRAMENTO LEGAL
## 2. DESCRIÇÃO DO PROJETO
## 3. ANÁLISE DE IMPACTES E MEDIDAS
## 4. AUDITORIA DE CONFORMIDADE LEGAL (Obrigatório: Comparar EIA vs LEI)
## 5. CONCLUSÕES E PARECER FINAL

Tom: Auditoria Técnica e Formal.
"""

def create_doc(content, p_type):
    doc = Document()
    doc.styles['Normal'].font.name = 'Calibri'
    doc.add_heading('PARECER TÉCNICO DE AUDITORIA', 0).alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f'Setor: {p_type} | Data: {datetime.now().strftime("%d/%m/%Y")}').alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph("_"*70)
    
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
    elif not eia_files: st.warning("⚠️ Carregue os ficheiros do EIA.")
    else:
        with st.spinner("A analisar documentos... (Isto pode demorar 30 segundos)"):
            # Extração
            eia_text = extract_text_from_pdfs(eia_files)
            extra_laws_text = extract_text_from_pdfs(extra_laws) if extra_laws else ""
            full_legal_text = base_legal_text + "\n\n=== LEGISLAÇÃO EXTRA ===\n" + extra_laws_text
            
            # Execução (Modo Estável)
            result = analyze_stable(eia_text, full_legal_text, instructions, api_key)
            
            if "🚨" in result or "❌" in result:
                st.error(result)
            else:
                st.success("✅ Auditoria Concluída!")
                with st.expander("📄 Ler Parecer", expanded=True):
                    st.markdown(result)
                
                docx = create_doc(result, project_type)
                st.download_button("⬇️ Descarregar Word", docx.getvalue(), "Parecer_Auditoria.docx", type="primary", on_click=reset_app)
