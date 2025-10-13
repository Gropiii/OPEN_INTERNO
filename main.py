import pandas as pd
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
import pytz # Para lidar com fuso horário

# --- Configuração ---
ARQUIVO_DADOS = 'dados.csv'
ARQUIVO_TEMPLATE = 'template.html'
ARQUIVO_SAIDA = 'index.html' # Nome padrão que o GitHub Pages usa

# --- Lógica do Campeonato ---

# 1. Carregar os dados
try:
    df = pd.read_csv(ARQUIVO_DADOS)
except FileNotFoundError:
    print(f"Erro: Arquivo '{ARQUIVO_DADOS}' não encontrado.")
    exit()

# 2. Calcular a pontuação total
wods = [col for col in df.columns if col.lower().startswith('wod')]
df['Total Pontos'] = df[wods].sum(axis=1)

# 3. Classificar os atletas (menor pontuação primeiro)
df_classificado = df.sort_values(by='Total Pontos', ascending=True)

# 4. Adicionar a coluna de Classificação (Rank)
df_classificado['Rank'] = range(1, len(df_classificado) + 1)

# 5. Reordenar as colunas para melhor visualização
colunas_finais = ['Rank', 'Atleta'] + wods + ['Total Pontos']
df_classificado = df_classificado[colunas_finais]

# --- Geração do HTML ---

# 6. Preparar o ambiente do Jinja2
env = Environment(loader=FileSystemLoader('.'))
template = env.get_template(ARQUIVO_TEMPLATE)

# 7. Obter a data e hora atual (fuso de São Paulo)
fuso_horario_sp = pytz.timezone('America/Sao_Paulo')
data_atualizacao = datetime.now(fuso_horario_sp).strftime('%d/%m/%Y %H:%M:%S')

# 8. Renderizar o template com os dados
html_gerado = template.render(
    a_fazer_tabela=df_classificado.to_html(index=False, classes='table table-striped', justify='center'),
    a_fazer_data_atualizacao=data_atualizacao
)

# 9. Salvar o resultado em um arquivo
with open(ARQUIVO_SAIDA, 'w', encoding='utf-8') as f:
    f.write(html_gerado)

print(f"Tabela gerada com sucesso no arquivo '{ARQUIVO_SAIDA}'!")