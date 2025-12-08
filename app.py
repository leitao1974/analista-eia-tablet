import pandas as pd
import numpy as np

# --- CONFIGURAÇÕES ---
DATA_INICIAL = "2025-06-03"
PRAZO_DIAS_UTEIS = 150

# Feriados Nacionais Portugueses (apenas os que impactam dias úteis neste intervalo)
feriados_pt = [
    "2025-06-10", # Dia de Portugal (Terça)
    "2025-06-19", # Corpo de Deus (Quinta)
    "2025-08-15", # Assunção N. Sra (Sexta)
    "2025-10-05", # Implantação (Domingo - irrelevante p/ cálculo mas listado)
    "2025-11-01", # Todos os Santos (Sábado - irrelevante p/ cálculo mas listado)
    "2025-12-01", # Restauração (Segunda)
    "2025-12-08", # Imaculada Conceição (Segunda)
    "2025-12-25", # Natal (Quinta)
    "2026-01-01", # Ano Novo (Quinta)
]

# Converter feriados para formato datetime do numpy
feriados = np.array(feriados_pt, dtype='datetime64[D]')

# --- CÁLCULO ---
def calcular_fim_prazo_aia(inicio, dias, feriados_lista):
    # Data inicial
    start = np.datetime64(inicio)
    
    # busday_offset calcula dias úteis. 
    # weekmask='1111100' define Seg-Sex como úteis.
    # roll='forward' garante que se começar num feriado, avança.
    fim = np.busday_offset(start, dias, roll='forward', weekmask='1111100', holidays=feriados_lista)
    
    return pd.to_datetime(fim)

data_final = calcular_fim_prazo_aia(DATA_INICIAL, PRAZO_DIAS_UTEIS, feriados)

# --- RELATÓRIO FINAL ---
print(f"--- RELATÓRIO PROCESSO AIA ---")
print(f"Início do Prazo:      {pd.to_datetime(DATA_INICIAL).strftime('%d/%m/%Y')}")
print(f"Duração (Dias Úteis): {PRAZO_DIAS_UTEIS}")
print(f"Suspensões Judiciais: NÃO APLICÁVEL (Regime AIA)")
print("-" * 30)
print(f"Data Final Calculada: {data_final.strftime('%d/%m/%Y')}")

# Verificação
if data_final.strftime('%d/%m/%Y') == "08/01/2026":
    print("✅ STATUS: O cálculo bate certo com 08/01/2026.")
else:
    print("❌ STATUS: Divergência encontrada.")
