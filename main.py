import pandas as pd
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
import pytz

# --- Configuração ---
ARQUIVO_DADOS = 'dados.csv'
ARQUIVO_TEMPLATE = 'template.html'
ARQUIVO_SAIDA = 'index.html'

# --- Lógica do Campeonato ---

# 1. Carregar os dados brutos
try:
    df_raw = pd.read_csv(ARQUIVO_DADOS)
except FileNotFoundError:
    print(f"Erro: Arquivo '{ARQUIVO_DADOS}' não encontrado.")
    exit()

# Dicionário que guardará os dados finais de cada categoria
all_categories_data = {}

# Pega os nomes das colunas de WODs
wods_headers = [col for col in df_raw.columns if col.lower() not in ['atleta', 'categoria']]

# 2. Agrupa por 'Categoria' e processa cada grupo separadamente
for category_name, df_category_raw in df_raw.groupby('Categoria'):
    
    # Cria um DataFrame de leaderboard apenas para esta categoria
    df_leaderboard = pd.DataFrame()
    df_leaderboard['Atleta'] = df_category_raw['Atleta']
    
    lista_colunas_pontos = []
    
    # Itera sobre cada WOD para calcular os pontos DENTRO da categoria
    for wod_col in wods_headers:
        menor_e_melhor = '_tempo' in wod_col.lower()
        pontos_col_name = wod_col + '_Pontos'
        lista_colunas_pontos.append(pontos_col_name)

        df_leaderboard[wod_col] = df_category_raw[wod_col].values
        
        # Converte para numérico para poder classificar
        if not menor_e_melhor:
             df_category_raw[wod_col] = pd.to_numeric(df_category_raw[wod_col], errors='coerce')
        
        # Calcula o ranking (pontos) apenas para os atletas desta categoria
        df_leaderboard[pontos_col_name] = df_category_raw[wod_col].rank(method='min', ascending=menor_e_melhor)

    # 3. Calcula o total de pontos e o rank final da categoria
    df_leaderboard['Total Pontos'] = df_leaderboard[lista_colunas_pontos].sum(axis=1)
    df_classificado = df_leaderboard.sort_values(by='Total Pontos', ascending=True)
    df_classificado['Rank'] = range(1, len(df_classificado) + 1)
    
    # 4. Guarda os dados processados da categoria no dicionário principal
    all_categories_data[category_name] = df_classificado.to_dict(orient='records')

# --- Geração do HTML ---

# 5. Prepara o ambiente do Jinja2
env = Environment(loader=FileSystemLoader('.'))
template = env.get_template(ARQUIVO_TEMPLATE)

# 6. Pega data e hora atual
fuso_horario_sp = pytz.timezone('America/Sao_Paulo')
data_atualizacao = datetime.now(fuso_horario_sp).strftime('%d/%m/%Y %H:%M:%S')

# 7. Renderiza o template, passando o dicionário com todas as categorias
html_gerado = template.render(
    categories_data=all_categories_data,
    wods=wods_headers,
    data_atualizacao=data_atualizacao
)

# 8. Salva o resultado no arquivo final
with open(ARQUIVO_SAIDA, 'w', encoding='utf-8') as f:
    f.write(html_gerado)

print(f"Tabela gerada com sucesso no arquivo '{ARQUIVO_SAIDA}'!")