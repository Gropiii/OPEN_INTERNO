import pandas as pd
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
import pytz
import re

# --- Configuração ---
ARQUIVO_DADOS = 'dados.csv'
ARQUIVO_TEMPLATE = 'template.html'
ARQUIVO_SAIDA = 'index.html'

# --- Lógica do Campeonato ---

try:
    df_raw = pd.read_csv(ARQUIVO_DADOS)
except FileNotFoundError:
    print(f"Erro: Arquivo '{ARQUIVO_DADOS}' não encontrado.")
    exit()

# Identificar os nomes base dos WODs (ex: WOD1, WOD2)
wod_base_names = sorted(list(set([re.match(r'(WOD\d+)_', col).group(1) for col in df_raw.columns if col.startswith('WOD')])))

all_categories_data = {}

# 1. Agrupa pela categoria geral (Masculino, Feminino)
for category_name, df_category_raw in df_raw.groupby('Categoria_Geral'):
    
    # DataFrame para guardar os resultados e pontos finais desta categoria geral
    df_leaderboard = pd.DataFrame({'Atleta': df_category_raw['Atleta']})
    
    # 2. Itera sobre cada WOD para calcular os pontos
    for wod_base in wod_base_names:
        resultado_col = f'{wod_base}_Resultado'
        categoria_col = f'{wod_base}_Categoria'
        pontos_col = f'{wod_base}_Pontos'

        # Pega os dados brutos apenas deste WOD para a categoria geral atual
        df_wod = df_category_raw[['Atleta', resultado_col, categoria_col]].copy()
        df_wod.rename(columns={resultado_col: 'Resultado', categoria_col: 'Categoria_WOD'}, inplace=True)
        
        # Determina a métrica de ordenação
        # Vamos assumir que se o resultado contiver ':', é tempo (menor é melhor)
        # Caso contrário, é reps/distância/peso (maior é melhor)
        try:
            is_time = df_wod['Resultado'].str.contains(':', na=False).any()
        except AttributeError:
            is_time = False

        # Converte para numérico se não for tempo, para poder ordenar
        if not is_time:
            df_wod['Resultado_Num'] = pd.to_numeric(df_wod['Resultado'], errors='coerce')
        else:
            # Para tempo, a ordenação alfabética já funciona (ex: '07:06' < '08:15')
            df_wod['Resultado_Num'] = df_wod['Resultado']

        # 3. A LÓGICA PRINCIPAL: RX > SCALE
        rx_results = df_wod[df_wod['Categoria_WOD'].str.lower() == 'rx'].copy()
        scale_results = df_wod[df_wod['Categoria_WOD'].str.lower() == 'scale'].copy()

        # Rankeia RX
        rx_results[pontos_col] = rx_results['Resultado_Num'].rank(method='min', ascending=is_time)
        
        # Rankeia Scale
        scale_results[pontos_col] = scale_results['Resultado_Num'].rank(method='min', ascending=is_time)
        
        # Aplica o offset: o melhor de Scale fica com pontuação após o último de RX
        rx_count = len(rx_results)
        scale_results[pontos_col] = scale_results[pontos_col] + rx_count

        # 4. Junta os resultados rankeados e mescla no leaderboard principal
        df_wod_ranked = pd.concat([rx_results, scale_results])
        
        # Adiciona os resultados brutos e as categorias de WOD ao leaderboard para exibição
        df_leaderboard = pd.merge(df_leaderboard, df_wod_ranked[['Atleta', 'Resultado', 'Categoria_WOD', pontos_col]], on='Atleta')
        df_leaderboard.rename(columns={'Resultado': resultado_col, 'Categoria_WOD': categoria_col}, inplace=True)

    # 5. Calcula o total de pontos e o rank final da categoria
    pontos_cols = [f'{wod}_Pontos' for wod in wod_base_names]
    df_leaderboard['Total Pontos'] = df_leaderboard[pontos_cols].sum(axis=1)
    df_classificado = df_leaderboard.sort_values(by='Total Pontos', ascending=True)
    df_classificado['Rank'] = range(1, len(df_classificado) + 1)
    
    all_categories_data[category_name] = df_classificado.to_dict(orient='records')

# --- Geração do HTML ---
env = Environment(loader=FileSystemLoader('.'))
template = env.get_template(ARQUIVO_TEMPLATE)
fuso_horario_sp = pytz.timezone('America/Sao_Paulo')
data_atualizacao = datetime.now(fuso_horario_sp).strftime('%d/%m/%Y %H:%M:%S')

html_gerado = template.render(
    categories_data=all_categories_data,
    wods_base_names=wod_base_names, # Passa os nomes base para o template
    data_atualizacao=data_atualizacao
)

with open(ARQUIVO_SAIDA, 'w', encoding='utf-8') as f:
    f.write(html_gerado)

print(f"Tabela gerada com sucesso com a lógica RX > Scale!")