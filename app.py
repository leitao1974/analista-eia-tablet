import streamlit as st
import pdfplumber
from docx import Document
import google.generativeai as genai
import io

# --- 1. Configuração da Página ---
st.set_page_config(page_title="Analista EIA (Robust)", page_icon="🛡️")

# --- 2. Memória da Aplicação ---
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

def reset_app():
    st.session_state.uploader_key += 1

# --- 3. Interface Visual ---
st.title("🛡️ Analista de EIA (Modo Seguro)")
st.markdown("""
Esta versão é resiliente a erros de leitura em PDFs complexos.
**Segurança:** Os dados são limpos após o download.
""")

with st.sidebar:
    st.header("Configuração")
    api_key = st.text_input("Cole aqui a Google API Key", type="password")
    st.info("Nota: Se o PDF for digitalizado (imagem), a IA pode não conseguir ler o texto.")

uploaded_file = st.file_uploader(
    "Carregue o ficheiro PDF", 
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

# --- 4. Funções Técnicas (Atualizadas para evitar Crash) ---
def extract_text(file):
    """Extrai texto com proteção contra erros de página"""
    text = ""
    try:
        with pdfplumber.open(file) as pdf:
            total_pages = len(pdf.pages)
            # Vamos ler página a página com cuidado
            for i, page in enumerate(pdf.pages):
                try:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + "\n"
                except Exception as e:
                    # Se uma página der erro, ignoramos e continuamos
                    print(f"Aviso: Não foi possível ler a página {i+1}. Erro: {e}")
                    continue
    except Exception as e:
        return f"Erro crítico ao abrir o ficheiro: {str(e)}"
        
    return text

def analyze_ai(text, prompt, key):
    try:
        if len(text) < 50:
            return "ERRO: Não foi possível extrair texto suficiente. O PDF pode ser uma imagem digitalizada (scan) sem OCR."
            
        genai.configure(api_key=key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        # Limitamos o tamanho do texto para não exceder limites extremos, se necessário
        full_prompt = f"INSTRUÇÕES:\n{prompt}\n\nDADOS DO DOCUMENTO:\n{text}"
        
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        return f"Erro na IA: {str(e)}"

# --- 5. Botão de Ação ---
if st.button("🚀 Analisar Documento"):
    if not api_key:
        st.error("⚠️ Falta a Chave da Google.")
    elif not uploaded_file:
        st.warning("⚠️ Falta o PDF.")
    else:
        with st.spinner("A processar o documento..."):
            # Passo A: Extrair
            pdf_text = extract_text(uploaded_file)
            
            # Passo B: Analisar
            if pdf_text and "Erro crítico" not in pdf_text:
                final_text = analyze_ai(pdf_text, instructions, api_key)
                
                # Mostrar resultado
                if "ERRO:" in final_text:
                    st.error(final_text)
                else:
                    st.success("Concluído!")
                    st.write(final_text)
                    
                    # Passo C: Gerar Word
                    doc = Document()
                    doc.add_heading('Relatório EIA', 0)
                    doc.add_paragraph(final_text)
                    bio = io.BytesIO()
                    doc.save(bio)
                    
                    st.download_button(
                        label="⬇️ Descarregar Word e Limpar",
                        data=bio.getvalue(),
                        file_name="Relatorio_EIA.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        on_click=reset_app
                    )
            else:
                st.error(f"Falha na leitura do PDF: {pdf_text}")
