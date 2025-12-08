import streamlit as st
import pdfplumber
from docx import Document
import google.generativeai as genai
import io

# --- 1. Configuração da Página ---
st.set_page_config(page_title="Analista EIA (Limpeza Auto)", page_icon="♻️")

# --- 2. Memória da Aplicação (Para permitir o reset) ---
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

def reset_app():
    """Limpa a memória e força o recarregamento da página"""
    st.session_state.uploader_key += 1

# --- 3. Interface Visual ---
st.title("♻️ Analista de EIA (Modo Seguro)")
st.markdown("""
Esta ferramenta analisa Estudos de Impacte Ambiental (PDF) usando Inteligência Artificial.
**Segurança:** Os dados são apagados da memória automaticamente após o download do relatório.
""")

# Barra Lateral para a Chave
with st.sidebar:
    st.header("Configuração")
    api_key = st.text_input("Cole aqui a sua Google API Key", type="password")
    st.info("Utilize apenas documentos públicos para teste.")

# Upload de Ficheiro (com chave dinâmica para reset)
uploaded_file = st.file_uploader(
    "Carregue o ficheiro PDF", 
    type=['pdf'], 
    key=f"uploader_{st.session_state.uploader_key}"
)

# Área de Instruções (O Prompt)
default_prompt = """
Atua como um Especialista em Avaliação de Impacte Ambiental.
Analisa o texto e cria um relatório técnico contendo:
1. Resumo do Projeto (Localização e Tipologia).
2. Principais Impactes (Fase de Construção e Exploração).
3. Avaliação das Medidas de Mitigação.
4. Parecer Final Técnico.
"""
instructions = st.text_area("Instruções para a Análise:", value=default_prompt, height=150)

# --- 4. Funções Técnicas (O Motor) ---
def extract_text(file):
    """Tira o texto de dentro do PDF"""
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
    return text

def analyze_ai(text, prompt, key):
    """Envia para o Google Gemini"""
    try:
        genai.configure(api_key=key)
        # Usamos o modelo Flash que lê muitos dados rápido
        model = genai.GenerativeModel('gemini-1.5-flash')
        full_prompt = f"INSTRUÇÕES:\n{prompt}\n\nDOCUMENTO:\n{text}"
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        return f"Erro na IA: {str(e)}"

# --- 5. Botão de Ação ---
if st.button("🚀 Analisar Documento"):
    if not api_key:
        st.error("⚠️ Falta a Chave da Google (API Key) na barra lateral.")
    elif not uploaded_file:
        st.warning("⚠️ Falta carregar o PDF.")
    else:
        with st.spinner("A ler o PDF e a pensar... (Aguarde)"):
            # Passo A: Ler PDF
            pdf_text = extract_text(uploaded_file)
            
            # Passo B: Perguntar à IA
            if pdf_text:
                final_text = analyze_ai(pdf_text, instructions, api_key)
                
                # Passo C: Mostrar no Ecrã
                st.success("Análise concluída com sucesso!")
                st.subheader("Pré-visualização do Relatório:")
                st.write(final_text)
                
                # Passo D: Criar Word na memória
                doc = Document()
                doc.add_heading('Relatório de Análise Automática (EIA)', 0)
                doc.add_paragraph(final_text)
                bio = io.BytesIO()
                doc.save(bio)
                
                st.markdown("---")
                st.warning("⚠️ Ao descarregar, a aplicação irá reiniciar por segurança.")
                
                # Passo E: Botão de Download com Limpeza
                st.download_button(
                    label="⬇️ Descarregar Word e Limpar Dados",
                    data=bio.getvalue(),
                    file_name="Relatorio_EIA.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    on_click=reset_app # <--- O comando de limpeza
                )