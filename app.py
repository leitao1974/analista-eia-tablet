import streamlit as st
from pypdf import PdfReader
from docx import Document
import google.generativeai as genai
import io

# --- Configuração ---
st.set_page_config(page_title="Analista EIA (Robust)", page_icon="🛡️")

# --- Memória para Reset ---
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

def reset_app():
    st.session_state.uploader_key += 1

# --- Interface ---
st.title("🛡️ Analista de EIA (Versão Robusta)")
st.markdown("Versão atualizada com motor de leitura `pypdf` para maior compatibilidade.")

with st.sidebar:
    st.header("Configuração")
    api_key = st.text_input("Google API Key", type="password")

# Upload
uploaded_file = st.file_uploader(
    "Carregue o PDF", 
    type=['pdf'], 
    key=f"uploader_{st.session_state.uploader_key}"
)

default_prompt = """
Atua como um Especialista em Avaliação de Impacte Ambiental.
Analisa o texto e cria um relatório técnico contendo:
1. Resumo do Projeto.
2. Principais Impactes Identificados.
3. Medidas de Mitigação.
4. Parecer Final Técnico.
"""
instructions = st.text_area("Instruções:", value=default_prompt, height=150)

# --- Funções ---
def extract_text_pypdf(file):
    """Extrai texto usando pypdf (mais resistente a erros)"""
    text = ""
    try:
        reader = PdfReader(file)
        # Ler todas as páginas
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
    except Exception as e:
        return f"ERRO DE LEITURA: {str(e)}"
    return text

def analyze_ai(text, prompt, key):
    try:
        if "ERRO DE LEITURA" in text:
            return text
            
        genai.configure(api_key=key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Proteção contra textos vazios
        if len(text.strip()) < 50:
            return "O ficheiro parece vazio ou é uma imagem digitalizada. A IA precisa de texto selecionável."

        full_prompt = f"INSTRUÇÕES:\n{prompt}\n\nDADOS DO DOCUMENTO:\n{text}"
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        return f"Erro na IA: {str(e)}"

# --- Botão ---
if st.button("🚀 Analisar"):
    if not api_key:
        st.error("⚠️ Falta a API Key.")
    elif not uploaded_file:
        st.warning("⚠️ Falta o PDF.")
    else:
        with st.spinner("A ler com o novo motor..."):
            # 1. Extrair
            pdf_text = extract_text_pypdf(uploaded_file)
            
            # 2. Analisar
            result = analyze_ai(pdf_text, instructions, api_key)
            
            if "ERRO" in result or "Erro" in result:
                st.error(result)
            else:
                st.success("Sucesso!")
                st.write(result)
                
                # 3. Word
                doc = Document()
                doc.add_heading('Relatório EIA', 0)
                doc.add_paragraph(result)
                bio = io.BytesIO()
                doc.save(bio)
                
                st.download_button(
                    label="⬇️ Download e Limpar",
                    data=bio.getvalue(),
                    file_name="Relatorio.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    on_click=reset_app
                )


