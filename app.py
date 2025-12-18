import streamlit as st
from pypdf import PdfReader
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
import io
from datetime import datetime
import re
import os
import time

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Diagnóstico EIA", page_icon="🔧", layout="wide")

# Função para limpar memória à força
def clear_cache():
    st.cache_data.clear()
    st.cache_resource.clear()
    if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0
    st.session_state.uploader_key += 1
    st.success("Memória limpa com sucesso!")

with st.sidebar:
    st.header("🔧 Diagnóstico")
    if st.button("🧹 1. CLICAR AQUI PRIMEIRO (Limpar Memória)", type="primary"):
        clear_cache()
    
    api_key = st.text_input("Google API Key", type="password")
    st.divider()

# --- LEITURA LEGISLAÇÃO ---
def load_laws():
    folder = "legislacao"
    text = ""
    count = 0
    files = []
    
    if os.path.exists(folder):
        for f in os.listdir(folder):
            if f.endswith('.pdf'):
                try:
                    reader = PdfReader(os.path.join(folder, f))
                    t = ""
                    for p in reader.pages: t += p.extract_text() or ""
                    text += f"\n=== LEI: {f} ===\n{t}"
                    files.append(f)
                except: pass
    return text, files

legal_text, legal_files = load_laws()

# --- UPLOAD EIA ---
st.title("🧪 Teste de Capacidade (RNT)")
uploaded = st.file_uploader("Carregue o RNT (25 págs)", type=['pdf'], key=f"uploader_{st.session_state.get('uploader_key', 0)}")

eia_text = ""
if uploaded:
    try:
        reader = PdfReader(uploaded)
        for p in reader.pages: eia_text += p.extract_text() or ""
    except: pass

# --- O VERDADEIRO DIAGNÓSTICO ---
len_lei = len(legal_text)
len_eia = len(eia_text)
total = len_lei + len_eia

c1, c2, c3 = st.columns(3)
c1.metric("Tamanho Legislação", f"{len_lei:,} caracteres")
c2.metric("Tamanho EIA", f"{len_eia:,} caracteres")
c3.metric("TOTAL A ENVIAR", f"{total:,} caracteres", delta="Limite Seguro: ~800.000")

# --- LÓGICA DE ENVIO ---
def run_ai(k, prompt):
    genai.configure(api_key=k)
    # FORÇA O MODELO 1.5 FLASH (O mais leve de todos)
    model = genai.GenerativeModel('gemini-1.5-flash') 
    return model.generate_content(prompt).text

if st.button("🚀 Testar Envio", type="primary"):
    if total > 900000:
        st.error(f"❌ IMPOSSÍVEL ENVIAR: Tem {total} caracteres. O limite é cerca de 800.000. Limpe a pasta legislação.")
    elif not api_key:
        st.error("Falta API Key")
    else:
        try:
            with st.spinner("A enviar..."):
                prompt = f"Analisa este EIA com base na Lei:\n\nLEI:\n{legal_text[:100000]}\n\nEIA:\n{eia_text[:100000]}"
                res = run_ai(api_key, prompt)
                st.success("✅ SUCESSO! A API respondeu:")
                st.write(res)
        except ResourceExhausted:
            st.error("🚨 ERRO 429: A sua chave está temporariamente bloqueada pela Google (Penalty Box).")
            st.warning("Espere 5 a 10 minutos sem fazer nada e tente de novo.")
        except Exception as e:
            st.error(f"Erro: {e}")

