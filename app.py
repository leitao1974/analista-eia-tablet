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

        # 1. Detetar Títulos (## e ###) e
