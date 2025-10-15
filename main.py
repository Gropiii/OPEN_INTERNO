import pandas as pd
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
import pytz
import warnings

# Ignora especificamente o aviso de "downcasting" do Pandas para uma saída limpa.
warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    message="Downcasting object dtype arrays on .fillna"
)

# --- Configuração ---
# O link para a sua planilha do Google Sheets.
URL_SHEETS = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vQU4WYxeZNQ1QDxTuIwx6cOTz1u_ZRpPJmmrS0Lepmfw_MkcNMmoxuGLPkn9OBIDWfHcPc2CJXMKLXv/pub?gid=0&single=true&output=csv'

# --- Lógica do Campeonato ---
try:
    df_raw = pd.read_csv(URL_SHEETS)
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
            penalty_score = 1
            df_wod_ranked = pd.DataFrame(columns=['Atleta', 'Resultado', 'Categoria_WOD', pontos_col])
        else:
            penalty_score = len(df_wod_participantes) + 1
            
            df_wod_participantes.rename(columns={resultado_col: 'Resultado', categoria_col: 'Categoria_WOD'}, inplace=True)
            df_wod_participantes['Categoria_WOD'] = df_wod_participantes['Categoria_WOD'].astype(str)
            
            metrica = wod_base.split('_')[-1].lower()
            is_time = (metrica == 'tempo')

            if not is_time:
                df_wod_participantes['Resultado_Num'] = pd.to_numeric(df_wod_participantes['Resultado'], errors='coerce')
            else:
                df_wod_participantes['Resultado_Num'] = df_wod_participantes['Resultado']

            # Lógica de 3 categorias: RX > INT > SC.
            rx_results = df_wod_participantes[df_wod_participantes['Categoria_WOD'].str.lower() == 'rx'].copy()
            int_results = df_wod_participantes[df_wod_participantes['Categoria_WOD'].str.lower() == 'int'].copy()
            sc_results = df_wod_participantes[df_wod_participantes['Categoria_WOD'].str.lower() == 'sc'].copy()

            rx_results[pontos_col] = rx_results['Resultado_Num'].rank(method='min', ascending=is_time)
            int_results[pontos_col] = int_results['Resultado_Num'].rank(method='min', ascending=is_time)
            sc_results[pontos_col] = sc_results['Resultado_Num'].rank(method='min', ascending=is_time)
            
            rx_count = len(rx_results)
            int_count = len(int_results)

            if rx_count > 0:
                int_results[pontos_col] = int_results[pontos_col] + rx_count
            if rx_count > 0 or int_count > 0:
                sc_results[pontos_col] = sc_results[pontos_col] + rx_count + int_count

            df_wod_ranked = pd.concat([rx_results, int_results, sc_results])

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
    for i in range(1, max_placements + 1):
        placement_col_name = f'placements_{i}'
        df_leaderboard[placement_col_name] = (df_leaderboard[pontos_cols] == i).sum(axis=1)

    # Cria a lista de critérios para a ordenação final.
    sort_by_columns = ['Total Pontos']
    sort_ascending_order = [True] # Menor pontuação é melhor.

    for i in range(1, max_placements + 1):
        placement_col_name = f'placements_{i}'
        sort_by_columns.append(placement_col_name)
        sort_ascending_order.append(False) # Mais colocações altas é melhor.
        
    # --- ### INÍCIO DA NOVA LÓGICA DE DESEMPATE ALFABÉTICO ### ---
    # Adiciona o nome do atleta como o critério FINAL de desempate para garantir uma ordem única.
    sort_by_columns.append('Atleta')
    sort_ascending_order.append(True) # 'True' para ordem ascendente (A-Z).
    # --- ### FIM DA NOVA LÓGICA ### ---

    # Aplica a ordenação multi-critério para resolver todos os empates.
    df_classificado = df_leaderboard.sort_values(
        by=sort_by_columns,
        ascending=sort_ascending_order
    )
    
    # Adiciona a coluna de Rank final após a classificação correta.
    df_classificado['Rank'] = range(1, len(df_classificado) + 1)
    
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