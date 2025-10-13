import pandas as pd
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
import pytz

# --- Configuração ---
URL_SHEETS = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vQU4WYxeZNQ1QDxTuIwx6cOTz1u_ZRpPJmmrS0Lepmfw_MkcNMmoxuGLPkn9OBIDWfHcPc2CJXMKLXv/pub?gid=0&single=true&output=csv'

# --- Lógica do Campeonato ---
try:
    df_raw = pd.read_csv(URL_SHEETS)
except Exception as e:
    print(f"Erro ao ler dados da planilha: {e}")
    exit()

# Identifica os nomes base dos WODs de forma dinâmica, encontrando todas as colunas de resultado
wod_base_names = sorted(list(set([col.replace('_Resultado', '') for col in df_raw.columns if col.endswith('_Resultado')])))

all_categories_data = {}

# 1. Agrupa pela categoria geral (Masculino, Feminino)
for category_name, df_category_raw in df_raw.groupby('Categoria_Geral'):
    
    df_leaderboard = pd.DataFrame({'Atleta': df_category_raw['Atleta']})
    
    # 2. Itera sobre cada WOD para calcular os pontos
    for wod_base in wod_base_names:
        resultado_col = f'{wod_base}_Resultado'
        categoria_col = f'{wod_base}_Categoria'
        pontos_col = f'{wod_base}_Pontos'

        df_wod = df_category_raw[['Atleta', resultado_col, categoria_col]].copy()
        df_wod.rename(columns={resultado_col: 'Resultado', categoria_col: 'Categoria_WOD'}, inplace=True)
        
        # Determina a métrica pela última parte do nome base do WOD
        metrica = wod_base.split('_')[-1].lower()
        is_time = (metrica == 'tempo')

        if not is_time:
            df_wod['Resultado_Num'] = pd.to_numeric(df_wod['Resultado'], errors='coerce')
        else:
            df_wod['Resultado_Num'] = df_wod['Resultado']

        # 3. Lógica RX > SCALE
        rx_results = df_wod[df_wod['Categoria_WOD'].str.lower() == 'rx'].copy()
        scale_results = df_wod[df_wod['Categoria_WOD'].str.lower() == 'scale'].copy()

        rx_results[pontos_col] = rx_results['Resultado_Num'].rank(method='min', ascending=is_time)
        scale_results[pontos_col] = scale_results['Resultado_Num'].rank(method='min', ascending=is_time)
        
        rx_count = len(rx_results)
        if rx_count > 0:
            scale_results[pontos_col] = scale_results[pontos_col] + rx_count

        df_wod_ranked = pd.concat([rx_results, scale_results])
        
        df_leaderboard = pd.merge(df_leaderboard, df_wod_ranked[['Atleta', 'Resultado', 'Categoria_WOD', pontos_col]], on='Atleta')
        df_leaderboard.rename(columns={'Resultado': resultado_col, 'Categoria_WOD': categoria_col}, inplace=True)

    # 4. Calcula o total de pontos e o rank final da categoria
    pontos_cols = [f'{wod}_Pontos' for wod in wod_base_names]
    df_leaderboard['Total Pontos'] = df_leaderboard[pontos_cols].sum(axis=1)
    df_classificado = df_leaderboard.sort_values(by='Total Pontos', ascending=True)
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

print(f"Tabela gerada com sucesso com nomes de WODs personalizados!")