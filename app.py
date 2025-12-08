import streamlit as st
from pypdf import PdfReader
from docx import Document
import google.generativeai as genai
import io

# --- Configuração ---
st.set_page_config(page_title="Analista EIA (Diagnóstico)", page_icon="🔧")

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

def reset_app():
    st.session_state.uploader_key += 1

# --- Interface ---
st.title("🔧 Analista de EIA (Modo Diagnóstico)")
st.warning("Este modo vai detetar automaticamente qual o modelo IA disponível na sua conta.")

with st.sidebar:
    st.header("Configuração")
    api_key = st.text_input("Google API Key", type="password")

uploaded_file = st.file_uploader("Carregue o PDF", type=['pdf'], key=f"uploader_{st.session_state.uploader_key}")

instructions = st.text_area("Instruções:", value="Faz um resumo deste documento.", height=100)

# --- Funções Inteligentes ---
def get_available_model(key):
    """Pergunta à Google que modelos esta chave pode usar"""
    try:
        genai.configure(api_key=key)
        # Lista todos os modelos disponíveis
        models = list(genai.list_models())
        
        # Procura um modelo que gere texto (generateContent)
        valid_models = []
        for m in models:
            if 'generateContent' in m.supported_generation_methods:
                valid_models.append(m.name)
        
        # Tenta priorizar o Flash, depois o Pro, depois qualquer um
        if not valid_models:
            return None, "Nenhum modelo encontrado. A chave pode estar inválida."
            
        # Lógica de escolha automática
        chosen = None
        for m in valid_models:
            if 'flash' in m:
                chosen = m
                break
        if not chosen:
            for m in valid_models:
                if 'pro' in m:
                    chosen = m
                    break
        if not chosen:
            chosen = valid_models[0] # Escolhe o primeiro que aparecer
            
        return chosen, valid_models
    except Exception as e:
        return None, str(e)

def extract_text_pypdf(file):
    text = ""
    try:
        reader = PdfReader(file)
        for page in reader.pages:
            text += page.extract_text() + "\n"
    except Exception as e:
        return f"ERRO LEITURA: {str(e)}"
    return text

def analyze_ai(text, prompt, key, model_name):
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel(model_name) # Usa o modelo detetado
        response = model.generate_content(f"{prompt}\n\nDADOS:\n{text[:100000]}") # Limite segurança
        return response.text
    except Exception as e:
        return f"Erro na IA: {str(e)}"

# --- Botão ---
if st.button("🚀 Analisar (Auto-Detect)"):
    if not api_key:
        st.error("Falta a API Key.")
    elif not uploaded_file:
        st.warning("Falta o PDF.")
    else:
        with st.spinner("A verificar a sua API Key e modelos disponíveis..."):
            # 1. Detetar Modelo
            chosen_model, log_models = get_available_model(api_key)
            
            if not chosen_model:
                st.error(f"Erro Crítico na Chave: {log_models}")
            else:
                st.info(f"✅ Modelo detetado e selecionado: **{chosen_model}**")
                # (Opcional) Mostra lista para debug
                with st.expander("Ver todos os modelos disponíveis na conta"):
                    st.write(log_models)

                # 2. Processar
                with st.spinner("A ler e analisar..."):
                    pdf_text = extract_text_pypdf(uploaded_file)
                    result = analyze_ai(pdf_text, instructions, api_key, chosen_model)
                    
                    if "Erro" in result and len(result) < 200:
                        st.error(result)
                    else:
                        st.success("Sucesso!")
                        st.write(result)
                        
                        doc = Document()
                        doc.add_paragraph(result)
                        bio = io.BytesIO()
                        doc.save(bio)
                        
                        st.download_button("⬇️ Download", bio.getvalue(), "Relatorio.docx", on_click=reset_app)
