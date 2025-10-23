import pandas as pd
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
import pytz
import warnings
import numpy as np
import time

# Ignora avisos informativos para uma saída limpa no terminal.
warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    message="Downcasting object dtype arrays on .fillna"
)

# --- Configuração ---
# O link para a sua planilha do Google Sheets.
URL_BASE = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vQU4WYxeZNQ1QDxTuIwx6cOTz1u_ZRpPJmmrS0Lepmfw_MkcNMmoxuGLPkn9OBIDWfHcPc2CJXMKLXv/pub?gid=0&single=true&output=csv'
URL_SHEETS = f"{URL_BASE}&cache_bust={int(time.time())}"

# --- Lógica do Campeonato ---
try:
    df_raw = pd.read_csv(URL_SHEETS)
    df_raw.replace(r'^\s*$', np.nan, regex=True, inplace=True)
except Exception as e:
    print(f"Erro ao ler dados da planilha: {e}")
    exit()

# Identifica os nomes base dos WODs de forma dinâmica.
wod_base_names = sorted(list(set([col.replace('_Resultado', '') for col in df_raw.columns if col.endswith('_Resultado')])))

all_categories_data = {}

# 1. Agrupa os dados pela 'Categoria_Geral'.
for category_name, df_category_raw in df_raw.groupby('Categoria_Geral'):
    
    df_leaderboard = pd.DataFrame({'Atleta': df_category_raw['Atleta']})
    
    # 2. Itera sobre cada WOD para calcular os pontos.
    for wod_base in wod_base_names:
        resultado_col = f'{wod_base}_Resultado'
        categoria_col = f'{wod_base}_Categoria'
        pontos_col = f'{wod_base}_Pontos'

        df_wod_full = df_category_raw[['Atleta', resultado_col, categoria_col]].copy()
        
        df_wod_participantes = df_wod_full.dropna(subset=[resultado_col]).copy()

        if df_wod_participantes.empty:
            penalty_score = 0
            df_wod_ranked = pd.DataFrame(columns=['Atleta', 'Resultado', 'Categoria_WOD', pontos_col])
        else:
            penalty_score = len(df_wod_participantes) + 1
            
            df_wod_participantes.rename(columns={resultado_col: 'Resultado', categoria_col: 'Categoria_WOD'}, inplace=True)
            df_wod_participantes['Categoria_WOD'].fillna('ADP', inplace=True) 
            df_wod_participantes['Categoria_WOD'] = df_wod_participantes['Categoria_WOD'].astype(str)
            
            metrica = wod_base.split('_')[-1].lower()
            is_time = (metrica == 'tempo')

            if not is_time:
                df_wod_participantes['Resultado_Num'] = pd.to_numeric(df_wod_participantes['Resultado'], errors='coerce')
            else:
                df_wod_participantes['Resultado_Num'] = df_wod_participantes['Resultado']

            # Lógica de 4 categorias: RX > INT > SC > ADP.
            rx_results = df_wod_participantes[df_wod_participantes['Categoria_WOD'].str.strip().str.lower() == 'rx'].copy()
            int_results = df_wod_participantes[df_wod_participantes['Categoria_WOD'].str.strip().str.lower() == 'int'].copy()
            sc_results = df_wod_participantes[df_wod_participantes['Categoria_WOD'].str.strip().str.lower() == 'sc'].copy()
            adp_results = df_wod_participantes[df_wod_participantes['Categoria_WOD'].str.strip().str.lower() == 'adp'].copy()

            rx_results[pontos_col] = rx_results['Resultado_Num'].rank(method='min', ascending=is_time)
            int_results[pontos_col] = int_results['Resultado_Num'].rank(method='min', ascending=is_time)
            sc_results[pontos_col] = sc_results['Resultado_Num'].rank(method='min', ascending=is_time)
            adp_results[pontos_col] = adp_results['Resultado_Num'].rank(method='min', ascending=is_time)
            
            rx_count = len(rx_results)
            int_count = len(int_results)
            sc_count = len(sc_results)

            if rx_count > 0: int_results[pontos_col] = int_results[pontos_col] + rx_count
            if rx_count > 0 or int_count > 0: sc_results[pontos_col] = sc_results[pontos_col] + rx_count + int_count
            if rx_count > 0 or int_count > 0 or sc_count > 0: adp_results[pontos_col] = adp_results[pontos_col] + rx_count + int_count + sc_count

            df_wod_ranked = pd.concat([rx_results, int_results, sc_results, adp_results])

        # Junta os dados rankeados de volta na lista COMPLETA de atletas.
        df_leaderboard = pd.merge(df_leaderboard, df_wod_ranked[['Atleta', 'Resultado', 'Categoria_WOD', pontos_col]], on='Atleta', how='left')
        
        # Aplica a pontuação de penalidade e converte a coluna para inteiro.
        df_leaderboard[pontos_col] = df_leaderboard[pontos_col].fillna(penalty_score).astype(int)

        # Preenche os resultados e categorias vazios com "--".
        df_leaderboard.rename(columns={'Resultado': resultado_col, 'Categoria_WOD': categoria_col}, inplace=True)
        df_leaderboard[resultado_col].fillna("--", inplace=True)
        df_leaderboard[categoria_col].fillna("--", inplace=True)
        
    # Calcula o total de pontos.
    pontos_cols = [f'{wod}_Pontos' for wod in wod_base_names]
    df_leaderboard['Total Pontos'] = df_leaderboard[pontos_cols].sum(axis=1)
    
    # Lógica de desempate em cascata.
    max_placements = len(df_leaderboard)
    placement_cols = [] # Guarda os nomes das colunas de colocação
    for i in range(1, max_placements + 1):
        placement_col_name = f'placements_{i}'
        df_leaderboard[placement_col_name] = (df_leaderboard[pontos_cols] == i).sum(axis=1)
        placement_cols.append(placement_col_name)

    # --- ### INÍCIO DA CORREÇÃO DEFINITIVA ### ---
    # Define as colunas que definem um EMPATE REAL (sem incluir o nome do atleta).
    tie_breaking_columns = ['Total Pontos'] + placement_cols
    
    # Cria a lista completa de critérios para a ORDENAÇÃO (incluindo o nome para desempate final).
    sort_by_columns = tie_breaking_columns + ['Atleta']
    sort_ascending_order = [True] + [False] * len(placement_cols) + [True]

    # Aplica a ordenação multi-critério para resolver todos os empates.
    df_classificado = df_leaderboard.sort_values(
        by=sort_by_columns,
        ascending=sort_ascending_order
    ).reset_index(drop=True)

    # Lógica de Ranking Compartilhado Corrigida
    ranks = []
    current_rank = 0
    tie_count = 0
    previous_tie_values = None

    for index, row in df_classificado.iterrows():
        # Pega os valores APENAS das colunas que definem o empate real.
        current_tie_values = tuple(row[tie_breaking_columns])

        # Se for a primeira linha ou se os valores de EMPATE forem DIFERENTES da linha anterior...
        if previous_tie_values is None or current_tie_values != previous_tie_values:
            # ...calcula o novo rank pulando os lugares ocupados pelo empate anterior.
            current_rank += tie_count + 1
            tie_count = 0 # Reseta a contagem de empates.
        else:
            # Se os valores de EMPATE forem IGUAIS, incrementa a contagem de empates.
            tie_count += 1
        
        ranks.append(current_rank)
        # Guarda os valores de EMPATE desta linha para comparar com a próxima.
        previous_tie_values = current_tie_values

    # Adiciona a coluna 'Rank' ao DataFrame com os valores calculados.
    df_classificado['Rank'] = ranks
    # --- ### FIM DA CORREÇÃO DEFINITIVA ### ---

    # Guarda os dados processados da categoria no dicionário principal.
    all_categories_data[category_name] = df_classificado.to_dict(orient='records')

# --- Geração do HTML ---
env = Environment(loader=FileSystemLoader('.'))
template = env.get_template('template.html')
fuso_horario_sp = pytz.timezone('America/Sao_Paulo')
data_atualizacao = datetime.now(fuso_horario_sp).strftime('%d/%m/%Y %H:%M:%S')

html_gerado = template.render(
    categories_data=all_categories_data,
    wods_base_names=wod_base_names,
    data_atualizacao=data_atualizacao
)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html_gerado)

print(f"Tabela gerada com sucesso!")