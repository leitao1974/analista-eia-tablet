import streamlit as st
from pypdf import PdfWriter
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
import io
import os
import time
import tempfile
import re
from datetime import datetime

# ==========================================
# --- 1. CONFIGURAÇÃO E DADOS LEGISLATIVOS ---
# ==========================================

st.set_page_config(page_title="Auditor EIA Master", page_icon="⚖️", layout="wide")

st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #0e4da4; color: white; }
    .stSuccess, .stInfo { border-left: 5px solid #0e4da4; }
</style>
""", unsafe_allow_html=True)

if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0
def reset_app(): st.session_state.uploader_key += 1

# --- BASE DE DADOS LEGISLATIVA (RJAIA Completo) ---
COMMON_LAWS = {
    "RJAIA (DL 151-B/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-116043164",
    "SIMPLEX AMBIENTAL (DL 11/2023)": "https://diariodarepublica.pt/dr/detalhe/decreto-lei/11-2023-207604364",
    "REDE NATURA (DL 140/99)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/1999-34460975",
    "RUÍDO (RGR - DL 9/2007)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2007-34526556"
}

SPECIFIC_LAWS = {
    "1. Agricultura, Silvicultura e Aquicultura": {
        "ATIVIDADE PECUÁRIA (NREAP)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2008-34480678",
        "GESTÃO EFLUENTES (Port. 631/2009)": "https://diariodarepublica.pt/dr/detalhe/portaria/631-2009-518868"
    },
    "2. Indústria Extrativa (Minas e Pedreiras)": {
        "MASSAS MINERAIS (DL 270/2001)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2001-34449875",
        "RESÍDUOS DE EXTRAÇÃO (DL 10/2010)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2010-34658745"
    },
    "3. Indústria Energética": {
        "SISTEMA ELÉTRICO (DL 15/2022)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2022-177343687",
        "EMISSÕES INDUSTRIAIS (DL 127/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-34789569"
    },
    "4. Produção e Transformação de Metais": {
        "EMISSÕES INDUSTRIAIS (DL 127/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-34789569",
        "LICENCIAMENTO INDUSTRIAL (SIR)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2015-106567543"
    },
    "5. Infraestruturas (Vias, Aeroportos)": {
        "ESTATUTO ESTRADAS (Lei 34/2015)": "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2015-34585678",
        "RUÍDO GRANDES INFRAESTRUTURAS": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2007-34526556"
    },
    "6. Engenharia Hidráulica e Saneamento": {
        "DOMÍNIO HÍDRICO (Lei 54/2005)": "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2005-34563267",
        "ÁGUAS RESIDUAIS (DL 152/97)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/1997-34512345"
    },
    "7. Tratamento de Resíduos": {
        "RGGR (DL 102-D/2020)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2020-150917243"
    },
    "8. Projetos Urbanos e Turísticos": {
        "RJUE (Urbanização - DL 555/99)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/1999-34563452",
        "EMPREENDIMENTOS TURÍSTICOS": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2008-34460567"
    },
    "Outra Tipologia": {}
}

# ==========================================
# --- 2. MOTOR DE ARQUIVOS (FILE API) ---
# ==========================================

def get_available_models(api_key):
    try:
        genai.configure(api_key=api_key)
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        return models
    except: return []

def merge_pdfs_to_temp(uploaded_files):
    merger = PdfWriter()
    for uploaded_file in uploaded_files:
        merger.append(uploaded_file)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        merger.write(tmp)
        tmp_path = tmp.name
    return tmp_path

def analyze_large_document(merged_pdf_path, laws_str, prompt_instructions, key, model_name):
    genai.configure(api_key=key)
    status_msg = st.empty()
    status_msg.info("📤 A carregar ficheiro gigante para Google Cloud (File API)...")
    
    processo_file = None
    try:
        # 1. Upload
        processo_file = genai.upload_file(path=merged_pdf_path, display_name="Processo EIA")
        
        # 2. Esperar processamento
        status_msg.info("⚙️ A processar PDF na Cloud...")
        while processo_file.state.name == "PROCESSING":
            time.sleep(2)
            processo_file = genai.get_file(processo_file.name)
        
        if processo_file.state.name == "FAILED": raise ValueError("Falha no processamento do PDF pela Google.")
        
        status_msg.success("✅ Ficheiro pronto. A gerar análise jurídica...")

        # 3. Gerar Conteúdo
        model = genai.GenerativeModel(model_name)
        
        full_prompt = [
            prompt_instructions,
            "\n=== LEGISLAÇÃO APLICÁVEL E LINKS DE REFERÊNCIA ===\n",
            laws_str,
            "\n=== INSTRUÇÃO FINAL ===\n",
            "Analisa agora o ficheiro PDF em anexo seguindo estritamente a estrutura definida.",
            processo_file
        ]

        response = model.generate_content(full_prompt)
        status_msg.empty()
        return response.text

    except ResourceExhausted:
        return "🚨 Erro de Cota: Limite da API atingido."
    except Exception as e:
        return f"❌ Erro Técnico: {str(e)}"
    finally:
        if processo_file:
            try: genai.delete_file(processo_file.name)
            except: pass

# ==========================================
# --- 3. GERADOR DE WORD ---
# ==========================================

def clean_markdown(text):
    return text.replace('**', '').strip()

def create_professional_doc(content, project_type, active_laws_dict):
    doc = Document()
    
    style_normal = doc.styles['Normal']
    style_normal.font.name = 'Calibri'
    style_normal.font.size = Pt(11)
    
    title = doc.add_heading('AUDITORIA TÉCNICA EIA', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f'Setor: {project_type}').alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f'Data: {datetime.now().strftime("%d/%m/%Y")}').alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph('---')

    for line in content.split('\n'):
        line = line.strip()
        if not line: continue
        
        if line.startswith('## '):
            clean = clean_markdown(line.replace('## ', ''))
            h = doc.add_heading(clean.upper(), level=1)
            h.style.font.color.rgb = RGBColor(14, 77, 164)
        elif line.startswith('### '):
            clean = clean_markdown(line.replace('### ', ''))
            doc.add_heading(clean, level=2)
        elif line.startswith('- ') or line.startswith('* '):
            p = doc.add_paragraph(line[2:], style='List Bullet')
        else:
            doc.add_paragraph(line)

    doc.add_page_break()
    doc.add_heading('ANEXO: LEGISLAÇÃO DE REFERÊNCIA', level=1)
    
    for name, url in active_laws_dict.items():
        p = doc.add_paragraph(style='List Bullet')
        p.add_run(name + ": ").bold = True
        run = p.add_run("Consultar DRE")
        run.font.color.rgb = RGBColor(0, 0, 255)
        p.add_run(f" ({url})").italic = True

    bio = io.BytesIO()
    doc.save(bio)
    return bio

# ==========================================
# --- 4. INTERFACE ---
# ==========================================

with st.sidebar:
    st.header("1. Configuração")
    api_key = st.text_input("Chave API Google", type="password")
    
    model_name = ""
    if api_key:
        models = get_available_models(api_key)
        if models:
            ix = 0
            for i, m in enumerate(models):
                if 'flash' in m: ix = i; break
            model_name = st.selectbox("Modelo IA", models, index=ix)
    
    st.markdown("---")
    st.header("2. Tipologia")
    project_type = st.selectbox("Setor RJAIA:", list(SPECIFIC_LAWS.keys()) + ["Outra Tipologia"])
    
    active_laws = COMMON_LAWS.copy()
    if project_type in SPECIFIC_LAWS:
        active_laws.update(SPECIFIC_LAWS[project_type])
    
    with st.expander("Ver Base Legal Ativa"):
        for k, v in active_laws.items():
            st.markdown(f"**{k}**: [Link]({v})")

st.title("⚖️ Auditor EIA Master")
st.caption("Google File API (Processos grandes) + Base Legal + Relatório Word")

uploaded_files = st.file_uploader(
    "Carregar PDF(s) do Processo", 
    type=['pdf'], 
    accept_multiple_files=True,
    key=f"uploader_{st.session_state.uploader_key}"
)

# --- INSTRUÇÕES ESTRUTURADAS (ATUALIZADO) ---
instructions = f"""
Atua como Perito Sénior em Engenharia do Ambiente e Jurista.
Realiza uma auditoria técnica e legal ao EIA do setor: {project_type}.

CONTEXTO LEGISLATIVO (Prioritário):
(Ver lista anexa no prompt)

REGRAS DE FORMATAÇÃO:
1. Usa Markdown (##) para os títulos dos capítulos.
2. Identifica sempre a página do PDF onde encontraste a informação (ex: "Ref: Pág. 32").

ESTRUTURA OBRIGATÓRIA DO RELATÓRIO:

## 1. ENQUADRAMENTO LEGAL E CONFORMIDADE
   - O projeto enquadra-se corretamente no RJAIA (Anexo I ou II)?
   - Verifica ponto a ponto o cumprimento da legislação específica listada.
   - Identifica falhas administrativas (datas, entidades, peças instrutórias em falta).

## 2. PRINCIPAIS IMPACTES (Técnico)
   - Análise detalhada por descritor ambiental (Ar, Água, Ruído, Biodiversidade, etc.).
   - Foca nos impactes negativos significativos.

## 3. MEDIDAS DE MITIGAÇÃO PROPOSTAS
   - Lista as principais medidas apresentadas no EIA.
   - Organiza por fase (Construção vs Exploração).

## 4. ANÁLISE CRÍTICA E BENCHMARKING
   - As medidas propostas são suficientes face às Melhores Técnicas Disponíveis (MTD) para {project_type}?
   - Existem lacunas face às boas práticas do setor?

## 5. FUNDAMENTAÇÃO
   - Lista de evidências com referência às páginas do PDF analisado.
   - Justifica as observações feitas nos pontos anteriores.

## 6. CITAÇÕES RELEVANTES
   - Transcreve trechos chave do documento que evidenciem os problemas ou compromissos assumidos.

## 7. CONCLUSÕES E RECOMENDAÇÕES
   - Formular uma opinião técnica global sobre a qualidade do estudo e a viabilidade do projeto.
   - NÃO emitir "Parecer Favorável" ou "Desfavorável" (linguagem administrativa).
   - Focar em: O estudo é robusto? O projeto é ambientalmente viável se as medidas forem cumpridas?
   - Listar recomendações finais para melhoria.

Tom: Formal, Técnico e Construtivo.
"""

if st.button("🚀 INICIAR AUDITORIA", type="primary"):
    if not api_key or not model_name: st.error("⚠️ Configura a API Key.")
    elif not uploaded_files: st.warning("⚠️ Carrega ficheiros PDF.")
    else:
        with st.spinner("A processar auditoria..."):
            
            # Preparar string de leis
            laws_str = "\n".join([f"- {k}: {v}" for k, v in active_laws.items()])
            
            # Merge
            temp_path = merge_pdfs_to_temp(uploaded_files)
            
            # Executar IA
            result_text = analyze_large_document(temp_path, laws_str, instructions, api_key, model_name)
            
            # Limpar
            try: os.remove(temp_path)
            except: pass
            
            if "🚨" in result_text or "❌" in result_text:
                st.error(result_text)
            else:
                st.success("Auditoria Concluída!")
                
                with st.expander("📄 Ver Relatório", expanded=True):
                    st.markdown(result_text)
                
                docx_io = create_professional_doc(result_text, project_type, active_laws)
                
                st.download_button(
                    label="⬇️ Download Relatório Word",
                    data=docx_io.getvalue(),
                    file_name="Auditoria_EIA.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    on_click=reset_app
                )


