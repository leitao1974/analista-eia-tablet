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

# --- Configuração OBRIGATÓRIA (Primeira linha) ---
st.set_page_config(page_title="Análise EIA", page_icon="⚖️", layout="wide")

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

def reset_app():
    st.session_state.uploader_key += 1

# ==========================================
# --- 1. FUNÇÃO DE LEITURA (COM DIAGNÓSTICO) ---
# ==========================================

def load_legislation_knowledge_base(folder_path="legislacao"):
    """Lê PDFs e regista erros detalhados para diagnóstico."""
    legal_text = ""
    file_list = []
    debug_log = [] 
    
    if not os.path.exists(folder_path):
        return "AVISO: Pasta não encontrada.", [], ["❌ A pasta 'legislacao' não existe."]

    files = os.listdir(folder_path)
    
    if not files:
        return "AVISO: Pasta vazia.", [], ["⚠️ A pasta existe mas está vazia."]

    for filename in files:
        if filename.startswith('.'): continue
        full_path = os.path.join(folder_path, filename)
        
        if os.path.isdir(full_path): continue
            
        if not filename.lower().endswith('.pdf'):
            debug_log.append(f"⚠️ '{filename}' ignorado (não é PDF).")
            continue

        try:
            reader = PdfReader(full_path)
            content = ""
            for page in reader.pages:
                content += page.extract_text() + "\n"
            
            legal_text += f"\n\n=== LEGISLAÇÃO OFICIAL: {filename} ===\n{content}"
            file_list.append(filename)
            debug_log.append(f"✅ '{filename}' carregado ({len(reader.pages)} págs).")
            
        except Exception as e:
            debug_log.append(f"❌ ERRO ao ler '{filename}': {str(e)}")
            legal_text += f"\n[Erro ao ler lei {filename}: {str(e)}]\n"
            
    return legal_text, file_list, debug_log

# Carrega a legislação ao iniciar
legal_knowledge_text, legal_files_list, load_logs = load_legislation_knowledge_base()

# ==========================================
# --- 0. MOSTRAR DIAGNÓSTICO NO TOPO ---
# ==========================================
st.title("⚖️ Análise Técnica e Legal (RAG)")

with st.expander("🕵️ STATUS DO SISTEMA (Legislação)", expanded=False):
    if os.path.exists("legislacao"):
        st.success(f"📂 Pasta 'legislacao' encontrada.")
        if not load_logs:
            st.warning("Pasta vazia.")
        else:
            for log in load_logs:
                if "✅" in log: st.success(log)
                elif "❌" in log: st.error(log)
                else: st.info(log)
    else:
        st.error("❌ A pasta 'legislacao' NÃO FOI ENCONTRADA no GitHub.")

# ==========================================
# --- 2. CONFIGURAÇÃO (LEIS & MODELOS) ---
# ==========================================

COMMON_LAWS = {
    "RJAIA (DL 151-B/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-116043164",
    "LUA (DL 75/2015)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2015-106562356",
    "Simplex Ambiental (DL 11/2023)": "https://diariodarepublica.pt/dr/detalhe/decreto-lei/11-2023-207212480",
    "RGGR (DL 102-D/2020)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2020-150917243",
    "RGR (Ruído - DL 9/2007)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2007-34526556",
    "Lei da Água (Lei 58/2005)": "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2005-34563267",
    "REN (DL 166/2008)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2008-34493635",
    "RAN (DL 73/2009)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2009-34493636"
}

SPECIFIC_LAWS = {
    "1. Agricultura/Silvicultura": {"NREAP (DL 81/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-34789570"},
    "2. Indústria Extrativa": {
        "Massas Minerais (DL 270/2001)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2001-34449875",
        "Resíduos Extração (DL 10/2010)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2010-34658745"
    },
    "3. Energia/Indústria": {"Emissões (DL 127/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-34789569"},
    "Outra Tipologia": {"SIR (DL 169/2012)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2012-34658746"}
}

with st.sidebar:
    st.header("🔐 1. Configuração")
    
    api_key = st.text_input("Google API Key", type="password", help="Insira a chave (começa por AIza...).")
    
    selected_model = None
    if api_key:
        try:
            genai.configure(api_key=api_key)
            models_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            
            if models_list:
                st.success(f"Chave válida!")
                
                # --- LÓGICA DE SELEÇÃO DE MODELO (CORRIGIDA) ---
                # Procura explicitamente pelo nome exato ou substring forte
                preferred_model_index = 0
                found_preferred = False

                for i, m in enumerate(models_list):
                    # Prioridade Absoluta: gemini-1.5-flash (evitando versões experimentais se houver a estável)
                    if 'gemini-1.5-flash' in m and 'exp' not in m and '8b' not in m:
                        preferred_model_index = i
                        found_preferred = True
                        break
                
                # Se não encontrou a versão "limpa", tenta qualquer variante 1.5-flash
                if not found_preferred:
                    for i, m in enumerate(models_list):
                        if 'gemini-1.5-flash' in m:
                            preferred_model_index = i
                            break

                selected_model = st.selectbox("Modelo IA:", models_list, index=preferred_model_index)
                
                if "1.5-flash" in selected_model:
                    st.caption("✅ Modelo Económico (1.5 Flash) Selecionado.")
                else:
                    st.caption(f"⚠️ Modelo atual: {selected_model}. Pode consumir mais cota.")
            else:
                st.error("Sem modelos disponíveis.")
        except:
            st.error("Chave inválida.")

    st.divider()
    
    st.header("🏗️ 2. Tipologia")
    project_type = st.selectbox("Selecione o setor:", list(SPECIFIC_LAWS.keys()) + ["Outra Tipologia"])
    
    active_laws_links = COMMON_LAWS.copy()
    if project_type in SPECIFIC_LAWS:
        active_laws_links.update(SPECIFIC_LAWS[project_type])
    
    if legal_files_list:
        st.success(f"📚 {len(legal_files_list)} Leis carregadas na memória.")
    else:
        st.warning(f"⚠️ Nenhuma lei local (Modo Memória).")

uploaded_files = st.file_uploader("Carregue o EIA (PDFs)", type=['pdf'], accept_multiple_files=True, key=f"uploader_{st.session_state.uploader_key}")

# --- PROMPT ---
instructions = f"""
Atua como Perito Sénior em Engenharia do Ambiente e Jurista.
Realiza uma AUDITORIA DE CONFORMIDADE RIGOROSA ao EIA de um projeto do setor: {project_type.upper()}.

Vais receber dois blocos de informação:
1. "CONHECIMENTO JURÍDICO (LEGISLAÇÃO OFICIAL)": O texto das leis que o utilizador carregou.
2. "DADOS DO PROJETO (EIA)": O texto do proponente.

A tua missão é CRUCIFERAR a informação. 
- Verifica especificamente se o projeto cumpre as novas regras do "Simplex Ambiental" (DL 11/2023) se este estiver presente nas leis.
- Se o EIA cita um valor limite, verifica se esse valor existe no "CONHECIMENTO JURÍDICO".

REGRAS DE FORMATAÇÃO:
1. "Sentence case" apenas.
2. Não uses negrito (`**`) nas conclusões.
3. RASTREABILIDADE: Cita sempre a fonte *(Lei X, Artigo Y)* ou *(EIA, pág. Z)*.

Estrutura o relatório nestes 8 Capítulos:
## 1. ENQUADRAMENTO LEGAL E CONFORMIDADE
## 2. DESCRIÇÃO DO PROJETO
## 3. PRINCIPAIS IMPACTES (Técnico)
## 4. MEDIDAS DE MITIGAÇÃO PROPOSTAS
## 5. ANÁLISE CRÍTICA DE CONFORMIDADE LEGAL (CRUCIAL: Compara EIA vs LEI OFICIAL)
## 6. FUNDAMENTAÇÃO
## 7. CITAÇÕES RELEVANTES
## 8. CONCLUSÕES

Tom: Auditoria Forense, Formal e Técnico.
"""

# ==========================================
# --- 3. PROCESSAMENTO E WORD ---
# ==========================================

def extract_text_from_uploads(files):
    full_text = ""
    for file in files:
        try:
            full_text += f"\n\n=== INÍCIO DO EIA: {file.name} ===\n"
            reader = PdfReader(file)
            for i, page in enumerate(reader.pages):
                content = page.extract_text()
                if content: full_text += f"\n[FONTE: {file.name} | PÁGINA: {i+1}]\n{content}"
        except Exception as e: full_text += f"\n\nERRO AO LER {file.name}: {str(e)}\n"
    return full_text

def analyze_ai(project_text, legal_text, prompt, key, model_name):
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel(model_name)
        final_prompt = f"{prompt}\n\n### BLOCO 1: LEGISLAÇÃO OFICIAL (VERDADE ABSOLUTA) ###\n{legal_text[:1000000]}\n\n### BLOCO 2: EIA DO PROPONENTE ###\n{project_text[:500000]}"
        return model.generate_content(final_prompt).text
    except Exception as e: return f"Erro IA: {str(e)}"

# --- WORD CLEANING LOGIC ---

def clean_ai_formatting(text):
    text = re.sub(r'[*_#]', '', text)
    if len(text) > 10:
        uppercase = sum(1 for c in text if c.isupper())
        total = sum(1 for c in text if c.isalpha())
        if total > 0 and (uppercase / total) > 0.30: text = text.capitalize()
    return text.strip()

def format_bold_runs(paragraph, text):
    parts = re.split(r'(\*\*.*?\*\*)', text)
    for part in parts:
        if part.startswith('**') and part.endswith('**'):
            paragraph.add_run(part[2:-2]).bold = True
        else:
            paragraph.add_run(part)

def parse_markdown_to_docx(doc, markdown_text):
    cleaning_mode = False
    for line in markdown_text.split('\n'):
        line = line.strip()
        if not line: continue
        
        clean_upper = re.sub(r'[*#_]', '', line).strip().upper()
        is_header = line.startswith('#')
        
        # Lógica de "Trinco" para limpar capítulos finais
        if is_header or re.match(r'^\d+\.\s+[A-Z]', line):
            if any(x in clean_upper for x in ["ENQUADRAMENTO", "DESCRIÇÃO", "IMPACTES", "MEDIDAS"]) or \
               clean_upper.startswith(("1.", "2.", "3.", "4.")):
                cleaning_mode = False
            elif any(x in clean_upper for x in ["ANÁLISE", "FUNDAMENTAÇÃO", "CITAÇÕES", "CONCLUS"]) or \
                 clean_upper.startswith(("5.", "6.", "7.", "8.")):
                cleaning_mode = True

        if line.startswith('#'):
            clean_title = clean_ai_formatting(line.replace('#', ''))
            level = 1 if line.startswith('## ') else 2
            doc.add_heading(clean_title, level=level)
            continue

        p = doc.add_paragraph()
        if cleaning_mode:
            # Modo Limpo: Sem negrito
            clean_txt = clean_ai_formatting(line)
            if line.startswith(('- ', '* ')):
                p.style = 'List Bullet'
                clean_txt = clean_ai_formatting(line[2:])
            p.add_run(clean_txt)
        else:
            # Modo Normal: Com negrito
            if line.startswith(('- ', '* ')):
                p.style = 'List Bullet'
                format_bold_runs(p, line[2:])
            else:
                format_bold_runs(p, line)

def create_word_doc(content, links, files, p_type):
    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Calibri'
    style.font.size = Pt(11)
    style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    
    doc.add_heading('PARECER TÉCNICO EIA', 0).alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f'Setor: {p_type} | Data: {datetime.now().strftime("%d/%m/%Y")}').alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph('---')
    
    parse_markdown_to_docx(doc, content)
    
    doc.add_page_break()
    doc.add_heading('ANEXO: Fontes', 1)
    if links:
        doc.add_paragraph("Legislação Online:", style='Normal').bold = True
        for n, u in links.items():
            p = doc.add_paragraph(style='List Bullet')
            p.add_run(f"{n}: ").bold = True
            p.add_run(u).font.color.rgb = RGBColor(0, 0, 255)
    if files:
        doc.add_paragraph("Ficheiros Carregados (RAG):", style='Normal').bold = True
        for f in files: doc.add_paragraph(f"Ficheiro: {f}", style='List Bullet')
        
    bio = io.BytesIO()
    doc.save(bio)
    return bio

# --- BOTÃO ---
st.markdown("---")
if st.button("🚀 Gerar Relatório (Auditado)", type="primary", use_container_width=True):
    if not api_key: st.error("⚠️ Insira a API Key.")
    elif not uploaded_files: st.warning("⚠️ Carregue o EIA.")
    else:
        with st.spinner(f"A auditar contra {len(legal_files_list)} Leis Oficiais..."):
            eia_text = extract_text_from_uploads(uploaded_files)
            result = analyze_ai(eia_text, legal_knowledge_text, instructions, api_key, selected_model)
            
            if "Erro" in result and len(result) < 200: st.error(result)
            else:
                st.success("✅ Concluído!")
                with st.expander("Ver Relatório"): st.write(result)
                docx = create_word_doc(result, active_laws_links, legal_files_list, project_type)
                st.download_button("⬇️ Download Word", docx.getvalue(), "Parecer_Auditado.docx", type="primary", on_click=reset_app)
