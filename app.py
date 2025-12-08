import streamlit as st
from pypdf import PdfReader
from docx import Document
from docx.shared import Pt
import google.generativeai as genai
import io
from datetime import datetime

# --- Configuração da Página ---
st.set_page_config(page_title="Analista EIA Pro (Benchmarking)", page_icon="🌍", layout="wide")

# --- Gestão de Estado ---
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

def reset_app():
    st.session_state.uploader_key += 1

# --- Interface ---
st.title("🌍 Analista EIA Pro (Com Benchmarking e Citações)")
st.markdown("""
Gera relatórios técnicos com **comparação de projetos semelhantes**, **novas medidas** e **referência às páginas**.
""")

with st.sidebar:
    st.header("🔐 Configuração")
    api_key = st.text_input("Google API Key", type="password")
    st.info("A IA irá comparar este estudo com as 'Melhores Técnicas Disponíveis' (BAT) do setor.")

uploaded_file = st.file_uploader(
    "Carregue o PDF do Estudo", 
    type=['pdf'], 
    key=f"uploader_{st.session_state.uploader_key}"
)

# --- O NOVO PROMPT DE BENCHMARKING (AQUI ESTÁ A MELHORIA) ---
default_prompt = """
Atua como um Perito Sénior em Avaliação de Impacte Ambiental com acesso a conhecimento de projetos internacionais.
O teu objetivo é realizar uma auditoria técnica ao documento, usando uma abordagem de BENCHMARKING.

O texto de entrada contém marcadores `--- PÁGINA X ---`. Usa-os OBRIGATORIAMENTE para fundamentar a análise.

Estrutura o relatório EXATAMENTE nestes 7 Capítulos:

1. RESUMO DETALHADO DO PROJETO
   - Descreve a localização, enquadramento e componentes principais (Pág. X).

2. PRINCIPAIS IMPACTES IDENTIFICADOS (Por Descritor)
   - Analisa os descritores (Ecologia, Hídricos, Ruído, etc.) e identifica os impactes significativos citados no estudo.

3. MEDIDAS DE MITIGAÇÃO E COMPENSAÇÃO PROPOSTAS NO ESTUDO
   - Lista o que o promotor propõe fazer.

4. ANÁLISE CRÍTICA E BENCHMARKING (O Ponto Mais Importante)
   - Compara as medidas deste estudo com **Projetos Semelhantes e Boas Práticas Internacionais**.
   - Identifica LACUNAS: O que é que costuma ser feito neste tipo de projetos (ex: fotovoltaico, eólico, pedreira, estrada) que NÃO está previsto aqui?
   - Propõe **NOVAS MEDIDAS CONCRETAS** baseadas nessa comparação.
   - Exemplo: "Em projetos semelhantes na Europa, aplica-se a medida X, que está ausente neste estudo."

5. FUNDAMENTAÇÃO (Referências de Página)
   - Valida a tua análise indicando onde no texto original encontraste a informação. Ex: "(Pág. 45)".

6. CITAÇÕES RELEVANTES
   - Transcreve 3 frases literais (entre aspas) do documento que evidenciem fragilidades ou assumam impactes severos.

7. CONCLUSÕES E PARECER TÉCNICO
   - Emite parecer (Favorável/Condicionado/Desfavorável).
   - Resume as novas medidas que TÊM de ser incluídas para viabilizar o projeto.

Tom: Técnico, Exigente e Comparativo.
"""
instructions = st.text_area("Instruções (Prompt):", value=default_prompt, height=450)

# --- Funções Técnicas ---
def get_available_model(key):
    try:
        genai.configure(api_key=key)
        models = list(genai.list_models())
        valid_models = [m.name for m in models if 'generateContent' in m.supported_generation_methods]
        if not valid_models: return None
        # Prioridade Flash > Pro
        for m in valid_models:
            if 'flash' in m: return m
        return valid_models[0]
    except:
        return None

def extract_text_with_page_numbers(file):
    text = ""
    try:
        reader = PdfReader(file)
        for i, page in enumerate(reader.pages):
            content = page.extract_text()
            if content:
                page_marker = f"\n\n--- PÁGINA {i+1} ---\n"
                text += page_marker + content
    except Exception as e:
        return f"ERRO LEITURA: {str(e)}"
    return text

def analyze_ai(text, prompt, key, model_name):
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel(model_name)
        
        # Aumentamos o contexto para permitir análises profundas
        safe_text = text[:500000] 
        
        full_prompt = f"{prompt}\n\n=== INÍCIO DO DOCUMENTO ===\n{safe_text}\n=== FIM DO DOCUMENTO ==="
        
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        return f"Erro na IA: {str(e)}"

def create_word_doc(content):
    doc = Document()
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(11)
    
    doc.add_heading('Parecer Técnico de Avaliação de Impacte Ambiental', 0)
    p = doc.add_paragraph()
    p.add_run(f'Data da Análise: {datetime.now().strftime("%d/%m/%Y")}').bold = True
    doc.add_paragraph('---')
    
    doc.add_paragraph(content)
    
    section = doc.sections[0]
    footer = section.footer
    p = footer.paragraphs[0]
    p.text = "Relatório gerado por IA com base na documentação submetida e Benchmarking internacional."
    
    bio = io.BytesIO()
    doc.save(bio)
    return bio

# --- Botão de Ação ---
if st.button("🚀 Gerar Análise Crítica"):
    if not api_key:
        st.error("⚠️ Falta a API Key.")
    elif not uploaded_file:
        st.warning("⚠️ Falta o PDF.")
    else:
        with st.spinner("📄 A ler PDF e a mapear páginas..."):
            model_name = get_available_model(api_key)
            if not model_name:
                st.error("Erro na API Key.")
                st.stop()
            pdf_text = extract_text_with_page_numbers(uploaded_file)
            
        with st.spinner("🌍 A realizar Benchmarking com projetos de referência..."):
            result = analyze_ai(pdf_text, instructions, api_key, model_name)
            
            if "Erro" in result and len(result) < 200:
                st.error(result)
            else:
                st.success("Análise de Benchmarking Concluída!")
                with st.expander("Ver Relatório no Ecrã"):
                    st.markdown(result)
                
                word_file = create_word_doc(result)
                
                st.download_button(
                    label="⬇️ Descarregar Relatório Técnico (.docx)",
                    data=word_file.getvalue(),
                    file_name="Parecer_Tecnico_Benchmarking.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    on_click=reset_app
                )
