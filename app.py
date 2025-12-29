import streamlit as st
from pypdf import PdfReader, PdfWriter
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, NotFound
import io
from datetime import datetime
import os
import time
import tempfile # Necessário para lidar com ficheiros temporários no File API

# --- 1. CONFIGURAÇÃO VISUAL ---
st.set_page_config(page_title="Auditor EIA Pro (Pay-as-you-go)", page_icon="⚖️", layout="wide")

st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #2e7d32; color: white; }
    .stSuccess, .stInfo, .stWarning { border-left: 5px solid #ccc; }
</style>
""", unsafe_allow_html=True)

if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0
def reset_app(): st.session_state.uploader_key += 1

# ==========================================
# --- 2. MOTOR DE IA (FILE API) ---
# ==========================================

def get_available_models(api_key):
    """Lista modelos disponíveis na conta."""
    try:
        genai.configure(api_key=api_key)
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        return models
    except:
        return []

def analyze_large_document(merged_pdf_path, l_text, prompt, key, model_name):
    """
    Usa a File API para processar documentos gigantes (800+ páginas).
    Faz upload > Processa > Apaga.
    """
    genai.configure(api_key=key)
    
    # 1. Upload do Ficheiro para a Google Cloud
    status_msg = st.empty()
    status_msg.info("📤 A enviar ficheiro gigante para a Google Cloud (File API)...")
    
    try:
        # Upload
        processo_file = genai.upload_file(path=merged_pdf_path, display_name="Processo EIA Analise")
        
        # 2. Esperar pelo processamento (Active State)
        status_msg.info("⚙️ A Google está a processar o PDF... (pode demorar uns segundos)")
        
        while processo_file.state.name == "PROCESSING":
            time.sleep(2)
            processo_file = genai.get_file(processo_file.name)
            
        if processo_file.state.name == "FAILED":
            raise ValueError("A Google falhou a ler o ficheiro PDF.")
            
        status_msg.success("✅ Ficheiro lido com sucesso pela IA. A gerar relatório...")

        # 3. Configurar Modelo e Prompt
        model = genai.GenerativeModel(model_name)
        
        # O Prompt agora é uma lista mista (Texto + Referência do Ficheiro)
        full_prompt = [
            prompt,
            "--- INICIO DA LEGISLAÇÃO APLICÁVEL (CONTEXTO) ---",
            l_text[:150000], # A legislação continua como texto (limite de segurança)
            "--- FIM DA LEGISLAÇÃO ---",
            "Agora, analisa o documento do processo em anexo:",
            processo_file # O objeto ficheiro é passado diretamente aqui
        ]

        # 4. Gerar Conteúdo
        response = model.generate_content(full_prompt)
        
        # 5. LIMPEZA (CRÍTICO PARA NÃO PAGAR ARMAZENAMENTO)
        genai.delete_file(processo_file.name)
        status_msg.empty() # Limpa a mensagem de status
        
        return response.text

    except ResourceExhausted:
        return "🚨 Erro de Cota: O limite da API foi atingido. Verifica o teu 'Budget' na Google Cloud."
    except Exception as e:
        # Tenta limpar o ficheiro mesmo se der erro
        try: genai.delete_file(processo_file.name)
        except: pass
        return f"❌ Erro Técnico: {str(e)}"

# ==========================================
# --- 3. GESTÃO DE FICHEIROS ---
# ==========================================

def extract_text_from_pdfs(uploaded_files):
    """Mantido apenas para a legislação (ficheiros menores)."""
    text = ""
    for f in uploaded_files:
        try:
            reader = PdfReader(f)
            for page in reader.pages: text += page.extract_text() + "\n"
        except: pass
    return text

def merge_pdfs_to_temp(uploaded_files):
    """
    Junta múltiplos PDFs num único ficheiro temporário no disco.
    Necessário porque a API genai.upload_file precisa de um caminho físico (path).
    """
    merger = PdfWriter()
    for uploaded_file in uploaded_files:
        merger.append(uploaded_file)
    
    # Cria ficheiro temporário e fecha-o para que outros processos o possam ler
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        merger.write(tmp)
        tmp_path = tmp.name
    
    return tmp_path

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
st.title("⚖️ Auditoria EIA Pro (Versão Cloud)")

with st.sidebar:
    st.header("1. Configuração")
    api_key = st.text_input("Chave API Google (Billing Ativo)", type="password")
    
    available_models = []
    selected_model_name = ""
    
    if api_key:
        available_models = get_available_models(api_key)
        if available_models:
            # Tenta selecionar o Flash por defeito (mais barato)
            default_ix = 0
            for i, m in enumerate(available_models):
                if 'flash' in m:
                    default_ix = i
                    break
            
            selected_model_name = st.selectbox(
                "Modelo de IA:", 
                available_models, 
                index=default_ix
            )
            if "flash" in selected_model_name: 
                st.caption("⚡ Flash: Ideal para grandes volumes (Económico)")
            if "pro" in selected_model_name:
                st.caption("🧠 Pro: Melhor raciocínio (Mais caro)")
        else:
            st.warning("Insira uma chave válida.")
    
    st.markdown("---")
    
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
    if base_legal_files:
        st.info(f"📂 {len(base_legal_files)} Leis na Base Fixa")
    
    extra_laws = st.file_uploader("Legislação Extra (PDF)", type=['pdf'], accept_multiple_files=True)

# --- ÁREA PRINCIPAL ---
st.subheader("3. Carregar Processo (Suporta 800+ Páginas)")
st.info("ℹ️ O sistema vai juntar todos os ficheiros abaixo e enviar para a cloud da Google para análise.")
eia_files = st.file_uploader(
    "Ficheiros do Projeto (EIA, RNT, Anexos)", 
    type=['pdf'], 
    accept_multiple_files=True, 
    key=f"uploader_{st.session_state.uploader_key}"
)

# ==========================================
# --- 5. LÓGICA DE EXECUÇÃO ---
# ==========================================

instructions = f"""
Atua como Perito Sénior em Engenharia do Ambiente e Jurista.
Auditoria de conformidade rigorosa ao EIA do setor: {project_type}.

DADOS FORNECIDOS:
1. LEGISLAÇÃO: Texto fornecido no prompt.
2. PROCESSO: Ficheiro PDF completo em anexo.

OBJETIVOS:
- Verificar conformidade com SIMPLEX AMBIENTAL (DL 11/2023) e RJAIA.
- Analisar o PDF em anexo na íntegra.
- Detetar falhas, omissões de capítulos obrigatórios ou inconsistências.

ESTRUTURA DO RELATÓRIO:
## 1. DADOS GERAIS DO PROJETO
(Identificar promotor, localização, tipologia no PDF)
## 2. ENQUADRAMENTO LEGAL
## 3. ANÁLISE TÉCNICA (Resumo do EIA)
## 4. CONFORMIDADE LEGAL E OMISSÕES
(Cruzar o que está no PDF com a legislação fornecida)
## 5. CONCLUSÃO DO PARECER

Tom: Técnico, Formal e Crítico.
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

if st.button("🚀 INICIAR AUDITORIA COMPLETA", type="primary"):
    if not api_key: st.error("⚠️ Insira a Chave API.")
    elif not eia_files: st.warning("⚠️ Carregue os ficheiros do EIA.")
    elif not selected_model_name: st.error("⚠️ Selecione um Modelo.")
    else:
        with st.spinner(f"A processar o volume de dados com {selected_model_name}..."):
            
            # 1. Preparar Legislação (Mantém-se como texto para contexto rápido)
            extra_laws_text = extract_text_from_pdfs(extra_laws) if extra_laws else ""
            full_legal_text = base_legal_text + "\n\n=== LEGISLAÇÃO EXTRA ===\n" + extra_laws_text
            
            # 2. Preparar o Processo Gigante (Merge + Upload)
            temp_merged_path = merge_pdfs_to_temp(eia_files)
            
            # 3. Executar Análise via File API
            result = analyze_large_document(temp_merged_path, full_legal_text, instructions, api_key, selected_model_name)
            
            # 4. Limpeza Local
            try: os.remove(temp_merged_path)
            except: pass
            
            # 5. Resultados
            if "🚨" in result or "❌" in result:
                st.error(result)
            else:
                st.success("✅ Auditoria Concluída!")
                with st.expander("📄 Ler Parecer", expanded=True):
                    st.markdown(result)
                
                docx = create_doc(result, project_type)
                st.download_button("⬇️ Download Word", docx.getvalue(), "Parecer_Auditoria.docx", type="primary", on_click=reset_app)

