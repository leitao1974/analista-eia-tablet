import streamlit as st
from pypdf import PdfReader
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, NotFound
import os
import time

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Diagnóstico Final", page_icon="🔧", layout="wide")

# Função para limpar memória
def clear_cache():
    st.cache_data.clear()
    st.cache_resource.clear()
    if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0
    st.session_state.uploader_key += 1
    st.success("✅ Memória do servidor limpa!")

with st.sidebar:
    st.header("🔧 Diagnóstico")
    if st.button("🧹 1. LIMPAR MEMÓRIA (Obrigatório)", type="primary"):
        clear_cache()
    
    api_key = st.text_input("Google API Key", type="password")
    st.divider()

# --- LEITURA LEGISLAÇÃO ---
def load_laws():
    folder = "legislacao"
    text = ""
    if os.path.exists(folder):
        for f in os.listdir(folder):
            if f.endswith('.pdf'):
                try:
                    reader = PdfReader(os.path.join(folder, f))
                    for p in reader.pages: text += p.extract_text() or ""
                except: pass
    return text

legal_text = load_laws()

# --- UPLOAD EIA ---
st.title("🧪 Teste de Ligação (Auto-Modelo)")
st.info("Este teste vai detetar automaticamente qual o modelo que a sua chave permite usar.")

uploaded = st.file_uploader("Carregue o RNT (PDF pequeno)", type=['pdf'], key=f"uploader_{st.session_state.get('uploader_key', 0)}")

eia_text = ""
if uploaded:
    try:
        reader = PdfReader(uploaded)
        for p in reader.pages: eia_text += p.extract_text() or ""
    except: pass

# --- MÉTRICAS ---
len_lei = len(legal_text)
len_eia = len(eia_text)
total = len_lei + len_eia

c1, c2, c3 = st.columns(3)
c1.metric("Legislação (Memória)", f"{len_lei:,} chars")
c2.metric("EIA (Upload)", f"{len_eia:,} chars")
c3.metric("TOTAL", f"{total:,} chars")

# --- LÓGICA DE ENVIO INTELIGENTE ---
def find_best_model(k):
    genai.configure(api_key=k)
    try:
        all_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # Prioridade 1: Algum modelo "Lite" (são os melhores para cota)
        best = next((m for m in all_models if 'lite' in m), None)
        
        # Prioridade 2: Algum modelo "Flash"
        if not best: best = next((m for m in all_models if 'flash' in m), None)
        
        # Prioridade 3: O primeiro que aparecer
        if not best and all_models: best = all_models[0]
        
        return best, all_models
    except Exception as e:
        return None, str(e)

if st.button("🚀 Testar Envio", type="primary"):
    if not api_key:
        st.error("Falta API Key")
    elif total > 800000:
        st.error(f"❌ TOTAL MUITO ALTO ({total}). Limpe a pasta 'legislacao' no GitHub.")
    else:
        # 1. Encontrar Modelo
        model_name, debug_info = find_best_model(api_key)
        
        if not model_name:
            st.error(f"Não foi possível listar modelos. Erro: {debug_info}")
        else:
            st.success(f"✅ Modelo detetado e selecionado: {model_name}")
            
            # 2. Tentar Enviar
            try:
                with st.spinner("A enviar..."):
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel(model_name)
                    
                    # Prompt Curto para teste
                    prompt = f"Resume este texto numa frase:\n\nCONTEXTO:\n{legal_text[:5000]}\n\nDADOS:\n{eia_text[:5000]}"
                    
                    res = model.generate_content(prompt).text
                    st.balloons()
                    st.success("✅ RESPOSTA RECEBIDA:")
                    st.write(res)
                    
            except ResourceExhausted:
                st.error("🚨 ERRO 429 (Cota): A chave continua bloqueada temporariamente. Aguarde 10 min.")
            except NotFound:
                st.error(f"🚨 ERRO 404: O modelo {model_name} afinal não funciona. Tente outra chave.")
            except Exception as e:
                st.error(f"Erro Genérico: {e}")

