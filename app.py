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

# --- Configuração ---
st.set_page_config(page_title="Análise", page_icon="⚖️", layout="wide")

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

def reset_app():
    st.session_state.uploader_key += 1

# ==========================================
# --- 1. BASE DE DADOS LEGISLATIVA (EXAUSTIVA) ---
# ==========================================

# Leis Transversais (Aplicáveis à maioria dos projetos EIA)
COMMON_LAWS = {
    "RJAIA (Avaliação Impacte Ambiental - DL 151-B/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-116043164",
    "LUA (Licenciamento Único Ambiental - DL 75/2015)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2015-106562356",
    "RGGR (Gestão de Resíduos - DL 102-D/2020)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2020-150917243",
    "RGR (Regulamento Geral do Ruído - DL 9/2007)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2007-34526556",
    "Lei da Água (Lei 58/2005)": "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2005-34563267",
    "Utilização Recursos Hídricos (DL 226-A/2007)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2007-34526558",
    "Qualidade do Ar (DL 102/2010)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2010-34526560",
    "Rede Natura 2000 (DL 140/99)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/1999-34460975",
    "REN (Reserva Ecológica Nacional - DL 166/2008)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2008-34493635",
    "RAN (Reserva Agrícola Nacional - DL 73/2009)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2009-34493636",
    "RJUE (Urbanização e Edificação - DL 555/99)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/1999-34563452",
    "Espécies Invasoras (DL 92/2019)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2019-123023867"
}

# Leis Específicas por Setor
SPECIFIC_LAWS = {
    "1. Agricultura, Silvicultura e Aquicultura": {
        "NREAP (Atividade Pecuária - DL 81/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-34789570",
        "Gestão de Efluentes Pecuários (Port. 631/2009)": "https://diariodarepublica.pt/dr/detalhe/portaria/631-2009-518868",
        "Sistemas Florestais (DL 16/2009)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2009-34488356"
    },
    "2. Indústria Extrativa (Minas e Pedreiras)": {
        "Massas Minerais (Pedreiras - DL 270/2001)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2001-34449875",
        "Resíduos de Extração (DL 10/2010)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2010-34658745",
        "Segurança e Saúde Minas (DL 162/90)": "https://diariodarepublica.pt/dr/detalhe/decreto-lei/162-1990-417937",
        "Revelação e Aproveitamento (Lei 54/2015)": "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2015-106560456"
    },
    "3. Indústria Energética": {
        "Bases do Sistema Elétrico (DL 15/2022)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2022-177343687",
        "Emissões Industriais (DL 127/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-34789569"
    },
    "4. Produção e Transformação de Metais": {
        "SIR (Sistema Indústria Responsável - DL 169/2012)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2012-34658746",
        "Emissões Industriais (DL 127/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-34789569"
    },
    "5. Indústria Mineral e Química": {
        "Seveso III (Acidentes Graves - DL 150/2015)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2015-106558967",
        "Emissões Industriais (DL 127/2013)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-34789569"
    },
    "6. Infraestruturas (Rodovias, Ferrovias, Aeroportos)": {
        "Estatuto das Estradas (Lei 34/2015)": "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2015-34585678",
        "Servidões Aeronáuticas (DL 48/2022)": "https://diariodarepublica.pt/dr/detalhe/decreto-lei/48-2022-185799345"
    },
    "7. Projetos de Engenharia Hidráulica (Barragens, Portos)": {
        "Segurança de Barragens (DL 21/2018)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2018-114833256",
        "Lei da Água (Lei 58/2005)": "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2005-34563267"
    },
    "8. Tratamento de Resíduos e Águas Residuais": {
        "RGGR (Resíduos - DL 102-D/2020)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2020-150917243",
        "Águas Residuais Urbanas (DL 152/97)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/1997-34512345",
        "Deposição em Aterro (DL 102-D/2020 Anexo)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2020-150917243"
    },
    "9. Projetos Urbanos, Turísticos e Outros": {
        "RJUE (Urbanização - DL 555/99)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/1999-34563452",
        "RJET (Empreendimentos Turísticos - DL 39/2008)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2008-34460567",
        "Acessibilidades (DL 163/2006)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2006-34524456"
    },
    "Outra Tipologia": {
        "SIR (Sistema Indústria Responsável - DL 169/2012)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2012-34658746"
    }
}

# ==========================================
# --- 2. INTERFACE E LÓGICA ---
# ==========================================

st.title("⚖️ Análise")
st.markdown("Análise Técnica e Legal com validação cruzada contra Legislação Oficial.")

with st.sidebar:
    st.header("🔐 1. Configuração")
    
    CHAVE_FIXA = "" 

    if CHAVE_FIXA:
        api_key = CHAVE_FIXA
        st.success(f"🔑 Chave API Carregada")
    else:
        api_key = st.text_input("Google API Key", type="password")
    
    selected_model = None
    if api_key:
        try:
            genai.configure(api_key=api_key)
            models_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            if models_list:
                st.success(f"Chave válida!")
                index_flash = next((i for i, m in enumerate(models_list) if '1.5' in m or 'flash' in m), 0)
                selected_model = st.selectbox("Modelo IA:", models_list, index=index_flash)
                st.caption("ℹ️ Modelos 1.5 Flash são recomendados para ler várias leis.")
            else:
                st.error("Chave válida mas sem modelos.")
        except:
            st.error("Chave inválida.")

    st.divider()
    
    st.header("🏗️ 2. Tipologia")
    project_type = st.selectbox(
        "Selecione o setor:",
        list(SPECIFIC_LAWS.keys()) + ["Outra Tipologia"]
    )
    
    active_laws_links = COMMON_LAWS.copy()
    if project_type in SPECIFIC_LAWS:
        active_laws_links.update(SPECIFIC_LAWS[project_type])

uploaded_files = st.file_uploader(
    "Carregue os PDFs do PROJETO (EIA, RNT, Anexos)", 
    type=['pdf'], 
    accept_multiple_files=True, 
    key=f"uploader_{st.session_state.uploader_key}"
)

# ==========================================
# --- 3. CARREGAMENTO DA LEGISLAÇÃO (RAG) ---
# ==========================================

def load_legislation_knowledge_base(folder_path="legislacao"):
    """Lê todos os PDFs na pasta 'legislacao' e retorna texto e lista de ficheiros."""
    legal_text = ""
    file_list = []
    
    if not os.path.exists(folder_path):
        os.makedirs(folder_path) 
        return "AVISO: Pasta 'legislacao' criada.", []

    files = [f for f in os.listdir(folder_path) if f.lower().endswith('.pdf')]
    
    if not files:
        return "AVISO: Pasta vazia.", []

    for filename in files:
        try:
            path = os.path.join(folder_path, filename)
            reader = PdfReader(path)
            content = ""
            for page in reader.pages:
                content += page.extract_text() + "\n"
            
            legal_text += f"\n\n=== LEGISLAÇÃO OFICIAL: {filename} ===\n{content}"
            file_list.append(filename)
        except Exception as e:
            legal_text += f"\n[Erro ao ler lei {filename}: {str(e)}]\n"
            
    return legal_text, file_list

# Carrega a legislação
legal_knowledge_text, legal_files_list = load_legislation_knowledge_base()

if legal_files_list:
    st.sidebar.success(f"📚 {len(legal_files_list)} Leis carregadas da pasta 'legislacao'.")
else:
    st.sidebar.warning(f"⚠️ Nenhuma lei local encontrada. A usar apenas memória.")


# --- PROMPT ---
instructions = f"""
Atua como Perito Sénior em Engenharia do Ambiente e Jurista.
Realiza uma AUDITORIA DE CONFORMIDADE RIGOROSA ao EIA de um projeto do setor: {project_type.upper()}.

Vais receber dois blocos de informação abaixo:
1. "CONHECIMENTO JURÍDICO (LEGISLAÇÃO OFICIAL)": Contém o texto integral das leis aplicáveis.
2. "DADOS DO PROJETO (EIA)": Contém o texto do proponente.

A tua missão é CRUCIFERAR a informação. Não confies na memória.
- Se o EIA cita um valor limite, verifica se esse valor existe no "CONHECIMENTO JURÍDICO".
- Se o EIA diz que está isento de algo, verifica se a Lei no "CONHECIMENTO JURÍDICO" confirma essa isenção.

REGRAS DE FORMATAÇÃO E CITAÇÃO:
1. "Sentence case" apenas.
2. Não uses negrito (`**`) nas conclusões.
3. RASTREABILIDADE TOTAL:
   - Quando citares um dado do EIA, escreve: *(EIA - NomeFicheiro, pág. X)*.
   - Quando citares uma obrigação legal, escreve: *(Lei - NomeFicheiroLei, Artigo X)*.

Estrutura o relatório EXATAMENTE nestes 8 Capítulos:

## 1. ENQUADRAMENTO LEGAL E CONFORMIDADE
   - Validação do enquadramento no RJAIA usando a lei fornecida.
   - Verificação das condicionantes legais (REN, RAN, etc.).

## 2. DESCRIÇÃO DO PROJETO
   - Resumo técnico com referências de página.

## 3. PRINCIPAIS IMPACTES (Técnico)
   - Análise por descritor.

## 4. MEDIDAS DE MITIGAÇÃO PROPOSTAS
   - Lista as medidas.

## 5. ANÁLISE CRÍTICA DE CONFORMIDADE LEGAL (O MAIS IMPORTANTE)
   - Compara o que o EIA diz vs. o que a LEI OFICIAL diz.
   - **Exemplo:** "O EIA refere um limite de ruído de 65dB, mas o RGR (pág. 12) define 63dB para zonas mistas. ERRO DETETADO."

## 6. FUNDAMENTAÇÃO
   - Explicação técnica das falhas.

## 7. CITAÇÕES RELEVANTES
   - Transcreve trechos do EIA e trechos da Lei que provam as contradições.

## 8. CONCLUSÕES
   - Parecer Final fundamentado.

Tom: Auditoria Forense, Formal e Técnico.
"""

# ==========================================
# --- 4. FUNÇÕES DE EXTRAÇÃO E WORD ---
# ==========================================

def extract_text_from_uploads(files):
    full_text = ""
    for file in files:
        try:
            full_text += f"\n\n=== INÍCIO DO EIA/PROJETO: {file.name} ===\n"
            reader = PdfReader(file)
            for i, page in enumerate(reader.pages):
                content = page.extract_text()
                if content:
                    full_text += f"\n[FONTE: {file.name} | PÁGINA: {i+1}]\n{content}"
        except Exception as e:
            full_text += f"\n\nERRO AO LER FICHEIRO {file.name}: {str(e)}\n"
    return full_text

def analyze_ai(project_text, legal_text, prompt, key, model_name):
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel(model_name)
        
        final_prompt = f"""
        {prompt}

        ###################################################
        BLOCO 1: CONHECIMENTO JURÍDICO (LEGISLAÇÃO OFICIAL)
        (Usa isto como a VERDADE ABSOLUTA)
        ###################################################
        {legal_text[:1000000]} 

        ###################################################
        BLOCO 2: DADOS DO PROJETO (EIA DO PROPONENTE)
        (Analisa isto à luz do Bloco 1)
        ###################################################
        {project_text[:500000]}
        """
        
        response = model.generate_content(final_prompt)
        return response.text
    except Exception as e:
        return f"Erro IA: {str(e)}"

# === FUNÇÕES WORD ===

def clean_ai_formatting(text):
    text = text.replace('**', '').replace('__', '').replace('###', '').replace('##', '')
    if len(text) > 5 and text.isupper():
        return text.capitalize()
    return text.strip()

def format_bold_runs(paragraph, text):
    parts = re.split(r'(\*\*.*?\*\*)', text)
    for part in parts:
        if part.startswith('**') and part.endswith('**'):
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        else:
            paragraph.add_run(part)

def parse_markdown_to_docx(doc, markdown_text):
    in_critical_section = False
    
    for line in markdown_text.split('\n'):
        line = line.strip()
        if not line: continue
        
        if line.startswith('## ') or re.match(r'^\d+\.\s', line):
            clean = re.sub(r'^(##\s|\d+\.\s)', '', line).replace('*', '')
            doc.add_heading(clean.title(), level=1)
            upper_clean = clean.upper()
            if "FUNDAMENTAÇÃO" in upper_clean or "CITAÇÕES" in upper_clean or "CONCLUSÕES" in upper_clean:
                in_critical_section = True
            else:
                in_critical_section = False
        
        elif line.startswith('### '):
            clean = line[4:].replace('*', '')
            if in_critical_section:
                p = doc.add_paragraph()
                p.add_run(clean_ai_formatting(clean))
            else:
                doc.add_heading(clean, level=2)
            
        elif line.startswith('- ') or line.startswith('* '):
            p = doc.add_paragraph(style='List Bullet')
            clean_line = line[2:]
            if in_critical_section:
                p.add_run(clean_ai_formatting(clean_line))
            else:
                format_bold_runs(p, clean_line)
                
        else:
            p = doc.add_paragraph()
            if in_critical_section:
                p.add_run(clean_ai_formatting(line))
            else:
                format_bold_runs(p, line)

def create_professional_word_doc(content, active_laws_links, local_laws_list, project_type):
    doc = Document()
    
    style_normal = doc.styles['Normal']
    style_normal.font.name = 'Calibri'
    style_normal.font.size = Pt(11)
    style_normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    
    style_h1 = doc.styles['Heading 1']
    style_h1.font.name = 'Cambria'
    style_h1.font.size = Pt(14)
    style_h1.font.bold = True
    style_h1.font.color.rgb = RGBColor(0, 51, 102)

    title = doc.add_heading(f'PARECER TÉCNICO EIA', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f'Setor: {project_type}').alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f'Data: {datetime.now().strftime("%d/%m/%Y")}').alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph('---')

    parse_markdown_to_docx(doc, content)
    
    doc.add_page_break()
    doc.add_heading('ANEXO: Legislação Consultada', level=1)
    
    # 1. Links Web (DRE)
    if active_laws_links:
        doc.add_paragraph("Legislação Online (Base de Dados):", style='Normal').bold = True
        for name, url in active_laws_links.items():
            p = doc.add_paragraph(style='List Bullet')
            p.add_run(name + ": ").bold = True
            run = p.add_run(url)
            run.font.color.rgb = RGBColor(0, 0, 255)
            run.font.underline = True

    # 2. Ficheiros Locais (PDFs)
    if local_laws_list:
        doc.add_paragraph("") # Espaço
        doc.add_paragraph("Legislação Carregada (Ficheiros Locais - RAG):", style='Normal').bold = True
        for fname in local_laws_list:
            p = doc.add_paragraph(style='List Bullet')
            p.add_run(f"Ficheiro: {fname}")

    bio = io.BytesIO()
    doc.save(bio)
    return bio

# --- BOTÃO ---
st.markdown("---")

if st.button("🚀 Gerar Relatório (Auditado)", type="primary", use_container_width=True):
    if not api_key:
        st.error("⚠️ Insira a API Key.")
    elif not selected_model:
        st.error("⚠️ Nenhum modelo selecionado.")
    elif not uploaded_files:
        st.warning("⚠️ Carregue o EIA para análise.")
    else:
        with st.spinner(f"A auditar {len(uploaded_files)} ficheiros contra {len(legal_files_list)} Leis Oficiais..."):
            
            eia_text = extract_text_from_uploads(uploaded_files)
            
            result = analyze_ai(eia_text, legal_knowledge_text, instructions, api_key, selected_model)
            
            if "Erro" in result and len(result) < 200:
                st.error(result)
            else:
                st.success("✅ Auditoria Concluída!")
                with st.expander("Ver Relatório"):
                    st.write(result)
                word_file = create_professional_word_doc(result, active_laws_links, legal_files_list, project_type)
                st.download_button("⬇️ Download Word", word_file.getvalue(), f"Parecer_EIA_Auditado.docx", on_click=reset_app, type="primary")
