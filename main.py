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

# 2. Criar o DataFrame final que será exibido (começa só com os atletas)
df_leaderboard = pd.DataFrame()
df_leaderboard['Atleta'] = df_raw['Atleta']

# 3. Processar cada WOD para calcular os pontos
lista_colunas_pontos = []
for wod_col in df_raw.columns:
    if wod_col.lower() == 'atleta':
        continue

    # Determina se "maior é melhor" ou "menor é melhor" pela métrica no nome da coluna
    # O padrão é que maior é melhor (Reps, Distancia, Peso)
    menor_e_melhor = False
    if '_tempo' in wod_col.lower():
        menor_e_melhor = True

    # Nome da coluna de pontos para este WOD
    pontos_col_name = wod_col + '_Pontos'
    lista_colunas_pontos.append(pontos_col_name)

    # Copia a coluna de resultado bruto para o leaderboard
    df_leaderboard[wod_col] = df_raw[wod_col]
    
    # Converte para numérico para poder classificar (ignorando erros por enquanto)
    # Isso é importante para colunas como 'Reps' e 'Distancia'
    if not menor_e_melhor:
         df_raw[wod_col] = pd.to_numeric(df_raw[wod_col], errors='coerce')

    # Calcula o ranking (pontos). O método 'min' lida com empates.
    # Se menor for melhor (tempo), ascending=True. Senão (reps), ascending=False.
    df_leaderboard[pontos_col_name] = df_raw[wod_col].rank(method='min', ascending=menor_e_melhor)

# 4. Calcular o total de pontos
df_leaderboard['Total Pontos'] = df_leaderboard[lista_colunas_pontos].sum(axis=1)

# 5. Classificar os atletas pelo total de pontos (menor é melhor)
df_classificado = df_leaderboard.sort_values(by='Total Pontos', ascending=True)

# 6. Adicionar a coluna de Classificação (Rank) final
df_classificado['Rank'] = range(1, len(df_classificado) + 1)


# --- Geração do HTML ---

# 7. Preparar o ambiente do Jinja2
env = Environment(loader=FileSystemLoader('.'))
template = env.get_template(ARQUIVO_TEMPLATE)

# 8. Obter a data e hora atual
fuso_horario_sp = pytz.timezone('America/Sao_Paulo')
data_atualizacao = datetime.now(fuso_horario_sp).strftime('%d/%m/%Y %H:%M:%S')

# 9. Preparar os dados para o template
# Converte o DataFrame para uma lista de dicionários, que é fácil de usar no HTML
atletas_data = df_classificado.to_dict(orient='records')

# Pega todos os nomes de WODs originais
wods_headers = [col for col in df_raw.columns if col.lower() != 'atleta']

# 10. Renderizar o template com os dados
html_gerado = template.render(
    atletas=atletas_data,
    wods=wods_headers,
    data_atualizacao=data_atualizacao
)

# 11. Salvar o resultado no arquivo final
with open(ARQUIVO_SAIDA, 'w', encoding='utf-8') as f:
    f.write(html_gerado)

print(f"Tabela gerada com sucesso no arquivo '{ARQUIVO_SAIDA}'!")