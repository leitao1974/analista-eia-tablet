import streamlit as st
from pypdf import PdfReader
from docx import Document
from docx.shared import Pt, RGBColor, Mm
from docx.enum.text import WD_ALIGN_PARAGRAPH
import google.generativeai as genai
import io
from datetime import datetime
import re

# --- Configuração ---
st.set_page_config(page_title="Analista EIA (Layout Pro)", page_icon="📝", layout="wide")

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

def reset_app():
    st.session_state.uploader_key += 1

# --- Interface ---
st.title("📝 Analista EIA Pro (Layout Word Profissional)")
st.markdown("""
Gera pareceres técnicos com **formatação profissional no Word**: Títulos reais, espaçamento correto, listas e negritos automáticos.
Inclui Benchmarking, Análise Jurídica e Links Oficiais.
""")

with st.sidebar:
    st.header("🔐 Configuração")
    api_key = st.text_input("Google API Key", type="password")
    st.info("O documento final terá um layout limpo e estruturado, pronto a ser entregue.")

uploaded_file = st.file_uploader("Carregue o PDF", type=['pdf'], key=f"uploader_{st.session_state.uploader_key}")

# --- MATRIZ JURÍDICA ---
legal_refs = {
    "RJAIA (DL 151-B/2013) - Versão Consolidada": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2013-116043164",
    "REDE NATURA (DL 140/99)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/1999-34460975",
    "RUÍDO (RGR - DL 9/2007)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2007-34526556",
    "ÁGUA (Lei 58/2005)": "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2005-34563267",
    "RESÍDUOS (RGGR)": "https://diariodarepublica.pt/dr/legislacao-consolidada/decreto-lei/2020-150917243"
}
legal_context_str = "\n".join([f"- {k}: {v}" for k, v in legal_refs.items()])

# --- PROMPT (Instruímos a IA a usar Markdown para facilitar a formatação) ---
default_prompt = f"""
Atua como um Perito Sénior em Engenharia do Ambiente e Jurista.
Realiza uma auditoria técnica e legal ao EIA.

CONTEXTO LEGISLATIVO (Links para DRE Consolidado):
{legal_context_str}

Usa a formatação Markdown para estruturar a tua resposta:
- Usa `## 1. TÍTULO` para os capítulos principais.
- Usa `### Subtítulo` se necessário.
- Usa `**negrito**` para destacar pontos chave.
- Usa listas com `-` para enumerar medidas ou impactes.

Estrutura o relatório EXATAMENTE nestes 7 Capítulos:

## 1. ENQUADRAMENTO LEGAL E CONFORMIDADE
   - O projeto enquadra-se no RJAIA? O estudo cita a legislação correta (versões vigentes)?

## 2. PRINCIPAIS IMPACTES (Técnico)
   - Análise por descritor ambiental.

## 3. MEDIDAS DE MITIGAÇÃO PROPOSTAS
   - Lista as medidas do promotor.

## 4. ANÁLISE CRÍTICA, BENCHMARKING E JURÍDICA
   - As medidas cumprem os limites legais (ex: ruído)?
   - Compara com boas práticas internacionais (Benchmarking).
   - Propõe novas medidas concretas.

## 5. FUNDAMENTAÇÃO (Referências de Página)
   - Usa sempre o formato `(Pág. X)`.

## 6. CITAÇÕES RELEVANTES
   - Transcreve 3 frases entre aspas.

## 7. CONCLUSÕES E PARECER
   - Parecer Final fundamentado.

Tom: Formal, Técnico e Jurídico.
"""
instructions = st.text_area("Instruções:", value=default_prompt, height=450)

# --- Funções Técnicas de IA ---
def get_available_model(key):
    try:
        genai.configure(api_key=key)
        return 'gemini-1.5-flash' 
    except:
        return None

def extract_text_pypdf(file):
    text = ""
    try:
        reader = PdfReader(file)
        for i, page in enumerate(reader.pages):
            content = page.extract_text()
            if content:
                text += f"\n\n--- PÁGINA {i+1} ---\n{content}"
    except Exception as e:
        return f"ERRO: {str(e)}"
    return text

def analyze_ai(text, prompt, key, model_name):
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel(model_name)
        safe_text = text[:500000]
        response = model.generate_content(f"{prompt}\n\nDADOS DO PDF:\n{safe_text}")
        return response.text
    except Exception as e:
        return f"Erro IA: {str(e)}"

# ==========================================
# --- NOVAS FUNÇÕES: HELPERS DE FORMATAÇÃO WORD ---
# ==========================================

def format_bold_runs(paragraph, text):
    """Deteta texto entre **asteriscos** e aplica negrito real no Word"""
    # Divide o texto pelos asteriscos. As partes ímpares (1, 3, 5...) são as que estão em negrito.
    parts = re.split(r'(\*\*.*?\*\*)', text)
    for part in parts:
        if part.startswith('**') and part.endswith('**'):
            run = paragraph.add_run(part[2:-2]) # Remove os asteriscos
            run.bold = True
        else:
            paragraph.add_run(part)

def parse_markdown_to_docx(doc, markdown_text):
    """Lê o texto da IA linha a linha e converte em elementos Word"""
    for line in markdown_text.split('\n'):
        line = line.strip()
        if not line: continue # Ignora linhas vazias

        # 1. Detetar Títulos (## e ###) e Títulos Numerados (1. Título)
        if line.startswith('## ') or re.match(r'^\d+\.\s', line):
            # Remove o '## ' ou o '1. ' se existir, para o título ficar limpo
            clean_title = re.sub(r'^(##\s|\d+\.\s)', '', line)
            # Adiciona como Heading Nível 1 (Azul e maior, definido nos estilos abaixo)
            doc.add_heading(clean_title.upper(), level=1)

        elif line.startswith('### '):
            doc.add_heading(line[4:], level=2)

        # 2. Detetar Listas (hífens ou asteriscos)
        elif line.startswith('- ') or line.startswith('* '):
            p = doc.add_paragraph(style='List Bullet')
            # Aplica negritos dentro da lista se houver
            format_bold_runs(p, line[2:])

        # 3. Parágrafos Normais
        else:
            p = doc.add_paragraph()
            # Aplica negritos dentro do parágrafo
            format_bold_runs(p, line)

def create_professional_word_doc(content, legal_links):
    doc = Document()
    
    # --- DEFINIÇÃO DE ESTILOS PROFISSIONAIS ---
    # Estilo Normal (Corpo do texto)
    style_normal = doc.styles['Normal']
    font_normal = style_normal.font
    font_normal.name = 'Calibri'
    font_normal.size = Pt(11)
    paragraph_format = style_normal.paragraph_format
    paragraph_format.space_after = Pt(8) # Espaço após cada parágrafo (dá "ar" ao texto)
    paragraph_format.line_spacing = 1.15 # Espaçamento entre linhas ligeiro

    # Estilo Heading 1 (Títulos dos Capítulos)
    style_h1 = doc.styles['Heading 1']
    font_h1 = style_h1.font
    font_h1.name = 'Cambria'
    font_h1.size = Pt(14)
    font_h1.bold = True
    font_h1.color.rgb = RGBColor(0, 51, 102) # Azul escuro profissional
    style_h1.paragraph_format.space_before = Pt(18)
    style_h1.paragraph_format.space_after = Pt(12)

    # --- CABEÇALHO DO DOCUMENTO ---
    title = doc.add_heading('PARECER TÉCNICO DE AVALIAÇÃO DE IMPACTE AMBIENTAL', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    meta_info = doc.add_paragraph()
    meta_info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta_info.add_run(f'Data de Emissão: {datetime.now().strftime("%d de %B de %Y")}').italic = True
    doc.add_paragraph('---')

    # --- CORPO DO RELATÓRIO (Usando o novo parser) ---
    # É aqui que a magia acontece: converte o texto da IA em Word bonito
    parse_markdown_to_docx(doc, content)
    
    # --- ANEXO JURÍDICO ---
    doc.add_page_break()
    doc.add_heading('ANEXO: Verificação de Legislação Consolidada (DRE)', level=1)
    doc.add_paragraph('Os seguintes links remetem para as versões consolidadas e vigentes dos diplomas legais mencionados no parecer. A sua consulta é obrigatória para validação.')
    
    for name, url in legal_links.items():
        p = doc.add_paragraph(style='List Bullet')
        p.add_run(name + ": ").bold = True
        run = p.add_run(url)
        run.font.color.rgb = RGBColor(0, 0, 255)
        run.font.underline = True

    # --- RODAPÉ ---
    section = doc.sections[0]
    footer = section.footer
    p = footer.paragraphs[0]
    p.text = "Documento Técnico gerado com suporte de IA. Requer validação por técnico habilitado."
    p.style = doc.styles['Footnote Text']
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    bio = io.BytesIO()
    doc.save(bio)
    return bio

# --- Botão ---
if st.button("🚀 Gerar Relatório Profissional"):
    if not api_key:
        st.error("Falta API Key")
    elif not uploaded_file:
        st.warning("Falta PDF")
    else:
        with st.spinner("A processar (Leitura > Análise > Formatação)..."):
            pdf_text = extract_text_pypdf(uploaded_file)
            result = analyze_ai(pdf_text, instructions, api_key, 'gemini-1.5-flash')
            
            if "Erro" in result and len(result) < 200:
                st.error(result)
            else:
                st.success("Relatório Gerado e Formatado!")
                with st.expander("Pré-visualização (Texto Raw)"):
                    st.write(result)
                
                # Usa a NOVA função de criação do Word
                word_file = create_professional_word_doc(result, legal_refs)
                
                st.download_button(
                    "⬇️ Download Parecer (.docx)", 
                    word_file.getvalue(), 
                    "Parecer_Tecnico_Pro.docx", 
                    on_click=reset_app
                )
