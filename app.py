import streamlit as st
from pypdf import PdfReader
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted # <--- Importante para apanhar o erro
import io
from datetime import datetime
import re
import os
import time

# --- Configuração OBRIGATÓRIA (Primeira linha) ---
st.set_page_config(page_title="Análise EIA", page_icon="⚖️", layout="wide")

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

def reset_app():
    st.session_state.uploader_key += 1

# ==========================================
# --- 1. LEITURA DE FICHEIROS (RAG) ---
# ==========================================

def load_legislation_knowledge_base(folder_path="legislacao"):
    """Lê os PDFs da pasta legislacao e prepara o 'cérebro' jurídico."""
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
            
            # Adiciona cabeçalho claro para a IA saber de que lei se trata
            legal_text += f"\n\n=== LEGISLAÇÃO OFICIAL: {filename} ===\n{content}"
            file_list.append(filename)
            debug_log.append(f"✅ '{filename}' ({len(reader.pages)} págs).")
        except Exception as e:
            debug_log.append(f"❌ Erro ao ler '{filename}': {str(e)}")
            
    return legal_text, file_list, debug_log

# Carrega a legislação ao iniciar a App
legal_knowledge_text, legal_files_list, load_logs = load_legislation_knowledge_base()

# ==========================================
# --- 0. STATUS E DIAGNÓSTICO ---
# ==========================================
st.title("⚖️ Análise Técnica e Legal (RAG)")

with st.expander("🕵️ STATUS DO SISTEMA (Legislação Carregada)", expanded=False):
    if os.path.exists("legislacao"):
        st.success(f"📂 Pasta 'legislacao' detetada.")
        for log in load_logs:
            if "✅" in log: st.success(log)
            elif "❌" in log: st.error(log)
            else: st.info(log)
    else:
        st.error("❌ A pasta 'legislacao' não foi encontrada no repositório.")

# ==========================================
# --- 2. CONFIGURAÇÃO (MODELOS & SETOR) ---
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
    "3. Energia": {"Emissões": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-34789569"},
    "Outra Tipologia": {"SIR": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2012-34658746"}
}

with st.sidebar:
    st.header("🔐 Configuração")
    api_key = st.text_input("Google API Key", type="password", help="Insira a chave (começa por AIza...).")
    
    selected_model = None
    if api_key:
        try:
            genai.configure(api_key=api_key)
            models_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            
            if models_list:
                st.success(f"Chave válida!")
                
                # --- LÓGICA DE SELEÇÃO INTELIGENTE (Prioridade: Lite -> 1.5 -> Flash) ---
                index_choice = 0
                found = False

                # 1. Procura modelos "Lite" (Melhores para evitar erros de cota)
                for i, m in enumerate(models_list):
                    if 'lite' in m and 'flash' in m:
                        index_choice = i
                        found = True
                        break
                
                # 2. Se não houver Lite, procura o clássico "1.5-flash" (Muito estável)
                if not found:
                    for i, m in enumerate(models_list):
                        if 'gemini-1.5-flash' in m and 'exp' not in m:
                            index_choice = i
                            found = True
                            break
                
                # 3. Se falhar tudo, agarra o primeiro que tiver "flash"
                if not found:
                    index_choice = next((i for i, m in enumerate(models_list) if 'flash' in m), 0)

                selected_model = st.selectbox("Modelo IA:", models_list, index=index_choice)
                
                if "lite" in selected_model:
                    st.caption("✅ Modelo 'Lite' selecionado (Otimizado para Cota Gratuita).")
                elif "1.5-flash" in selected_model:
                    st.caption("✅ Modelo 1.5 Flash selecionado (Alta Estabilidade).")
                else:
                    st.caption(f"ℹ️ Modelo: {selected_model}")
            else:
                st.error("Chave válida mas sem modelos disponíveis.")
        except:
            st.error("Chave inválida.")

    st.divider()
    project_type = st.selectbox("Setor do Projeto:", list(SPECIFIC_LAWS.keys()) + ["Outra Tipologia"])
    
    active_laws_links = COMMON_LAWS.copy()
    if project_type in SPECIFIC_LAWS:
        active_laws_links.update(SPECIFIC_LAWS[project_type])
    
    if legal_files_list:
        st.success(f"📚 {len(legal_files_list)} diplomas carregados na memória.")
    else:
        st.warning(f"⚠️ Nenhuma lei local. A usar apenas conhecimento geral.")

uploaded_files = st.file_uploader("Carregue o EIA (PDFs)", type=['pdf'], accept_multiple_files=True, key=f"uploader_{st.session_state.uploader_key}")

# --- PROMPT (INSTRUÇÕES PARA A IA) ---
instructions = f"""
Atua como Perito Sénior em Engenharia do Ambiente e Jurista.
Realiza uma AUDITORIA DE CONFORMIDADE RIGOROSA ao EIA de um projeto do setor: {project_type.upper()}.

Vais receber dois blocos de informação:
1. "CONHECIMENTO JURÍDICO (LEGISLAÇÃO OFICIAL)": O texto das leis que o utilizador carregou.
2. "DADOS DO PROJETO (EIA)": O texto do proponente.

A tua missão é CRUCIFERAR a informação. 
- Verifica se o projeto cumpre as regras do "Simplex Ambiental" (DL 11/2023) se este estiver presente nas leis.
- Verifica validades de licenças, prazos e isenções.
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
# --- 3. PROCESSAMENTO E IA (COM PROTEÇÃO DE ERRO) ---
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
    try:
        genai.configure(api_key=key)
        
        # Filtros de segurança no mínimo para não bloquear termos técnicos ambientais
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        
        m = genai.GenerativeModel(model)
        
        # Montagem do Prompt Final
        # Limitamos ligeiramente os caracteres para tentar evitar o erro de cota
        final_prompt = f"{prompt}\n\n### BLOCO 1: LEGISLAÇÃO OFICIAL (VERDADE ABSOLUTA) ###\n{l_text[:900000]}\n\n### BLOCO 2: EIA DO PROPONENTE ###\n{p_text[:500000]}"
        
        response = m.generate_content(final_prompt, safety_settings=safety_settings)
        return response.text

    except ResourceExhausted:
        return "⚠️ ERRO DE CAPACIDADE (429): O volume total de texto (Lei + EIA) excede o permitido pelo plano gratuito neste momento.\n\nSOLUÇÃO SUGERIDA:\n1. Vá ao GitHub e apague temporariamente os PDFs maiores da pasta 'legislacao', mantendo apenas o essencial (ex: Simplex e RJAIA).\n2. Reinicie a App e tente novamente.\n3. Ou aguarde alguns minutos e tente de novo."
    
    except Exception as e:
        return f"❌ Erro Técnico Inesperado: {str(e)}"

# --- LÓGICA DE WORD (LIMPEZA) ---

def clean_ai_formatting(text):
    text = re.sub(r'[*_#]', '', text)
    if len(text) > 10:
        uppercase = sum(1 for c in text if c.isupper())
        total = sum(1 for c in text if c.isalpha())
        if total > 0 and (uppercase / total) > 0.30: text = text.capitalize()
    return text.strip()

def parse_markdown_to_docx(doc, markdown_text):
    cleaning_mode = False
    for line in markdown_text.split('\n'):
        line = line.strip()
        if not line: continue
        
        clean_upper = re.sub(r'[*#_]', '', line).strip().upper()
        
        # Deteta Cabeçalhos
        if line.startswith('#'):
            clean_title = clean_ai_formatting(line.replace('#', ''))
            level = 1 if line.startswith('## ') else 2
            doc.add_heading(clean_title, level=level)
            
            # Lógica de limpeza para capítulos finais
            if any(x in clean_upper for x in ["ANÁLISE", "FUNDAMENTAÇÃO", "CITAÇÕES", "CONCLUS"]) or \
               clean_upper.startswith(("5.", "6.", "7.", "8.")):
                cleaning_mode = True
            else:
                cleaning_mode = False
            continue

        p = doc.add_paragraph()
        clean_txt = clean_ai_formatting(line) if cleaning_mode else line.replace('**', '') # Simplificado
        
        if line.startswith(('- ', '* ')):
            p.style = 'List Bullet'
            clean_txt = clean_txt[2:]
        
        p.add_run(clean_txt)

def create_doc(content, links, files, p_type):
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
    if files:
        doc.add_paragraph("Legislação Carregada (RAG):", style='Normal').bold = True
        for f in files: doc.add_paragraph(f"Ficheiro: {f}", style='List Bullet')
        
    bio = io.BytesIO()
    doc.save(bio)
    return bio

# --- BOTÃO E EXECUÇÃO ---
st.markdown("---")
if st.button("🚀 Gerar Relatório (Auditado)", type="primary", use_container_width=True):
    if not api_key: st.error("⚠️ Insira a API Key.")
    elif not uploaded_files: st.warning("⚠️ Carregue o EIA.")
    else:
        with st.spinner("⏳ A ler legislação e a auditar o EIA... (Aguarde até 2 min)"):
            # Pausa para evitar rate-limit imediato
            time.sleep(1)
            
            eia_text = extract_text(uploaded_files)
            result = analyze_ai(eia_text, legal_knowledge_text, instructions, api_key, selected_model)
            
            # Verifica se a resposta é um erro nosso
            if "⚠️ ERRO DE CAPACIDADE" in result or "❌" in result:
                st.error(result)
            else:
                st.success("✅ Auditoria Concluída!")
                with st.expander("Ver Relatório"): st.write(result)
                docx = create_doc(result, active_laws_links, legal_files_list, project_type)
                st.download_button("⬇️ Download Word", docx.getvalue(), "Parecer_Auditado.docx", type="primary", on_click=reset_app)

