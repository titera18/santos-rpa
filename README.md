# Santos FC na mídia

Robô que coleta notícias do Santos FC em vários sites, grava em SQLite, calcula a relevância de cada
notícia, analisa os dados e gera um dashboard em HTML.

## Como executar

```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m santos_rpa robo --abrir
```

| Comando | O que faz |
|---|---|
| `python -m santos_rpa robo` | Execução completa: coleta, análise e dashboard |
| `python -m santos_rpa robo --abrir` | Igual, e abre o dashboard no navegador |
| `python -m santos_rpa robo --sem-coleta` | Só refaz a análise e o dashboard, sem acessar a internet |
| `python -m santos_rpa painel` | Serve o dashboard em <http://localhost:8765> |
| `python -m unittest discover -s tests -t .` | Roda os testes |

Use o Python do ambiente (`.venv\Scripts\python.exe`) e rode os comandos na raiz do projeto.

## Arquitetura

O projeto segue as camadas do Domain-Driven Design. As dependências só apontam para dentro, em direção ao domínio, e
`tests/test_arquitetura.py` falha se alguma camada quebrar essa regra.

```text
santos_rpa/
├── dominio/             Regras do negócio, sem banco, internet ou arquivos
│   ├── modelo.py        Entidade Noticia e objetos de valor (Foco, Tema, Sentimento)
│   ├── portas.py        Contratos que o mundo externo precisa cumprir
│   ├── foco.py          A notícia é sobre o clube?
│   ├── tema.py          De que assunto ela trata?
│   ├── sentimento.py    Ela é boa ou ruim para o clube?
│   ├── historias.py     Quais notícias falam do mesmo fato?
│   ├── relevancia.py    Pontos de repercussão e recência
│   ├── nomes.py         Pessoas citadas no título
│   ├── clubes.py        Clubes adversários
│   ├── analise.py       Índice de sentimento e conclusões
│   └── texto.py         Normalização e identidade da notícia
├── aplicacao/           Casos de uso, que coordenam o domínio
│   ├── executar_robo.py
│   ├── coletar_noticias.py
│   ├── reclassificar_base.py
│   ├── avaliar_sentimento.py
│   └── montar_painel.py
├── infraestrutura/      Implementação das portas
│   ├── coleta/          Fontes RSS, HTML e Google News, com o catálogo de sites
│   ├── persistencia/    Repositório SQLite e leitura dos títulos rotulados
│   ├── ia/              Modelo de IA local e cache das previsões
│   └── painel/          Modelo HTML e geração do dashboard
├── interfaces/          Entradas do sistema
│   ├── cli.py           Linha de comando; é onde as camadas se conectam
│   └── servidor_web.py  Dashboard em localhost
└── configuracao.py      Caminhos e porta
avaliacao/               Títulos rotulados à mão para medir o sentimento
scripts/                 Agendamento e execução pelo Windows
tests/                   Testes, separados pelas mesmas camadas
dados/                   Banco, dashboard e modelo de IA (fora do Git)
logs/                    Histórico das execuções (fora do Git)
```

## O que é gerado

- `dados/santos_noticias.db`: banco SQLite
- `dados/dashboard.html`: dashboard em um único arquivo, que funciona sem internet
- `logs/rpa.log`: histórico das execuções

## Fontes

| Tipo | Fontes |
|---|---|
| RSS | Gazeta Esportiva, Santos FC (site oficial) |
| Páginas HTML | ge, Lance, UOL, Terra, CNN Brasil |
| Agregador | Google News, com 6 buscas que trazem dezenas de outros veículos |

Para adicionar uma fonte, edite `FONTES_RSS` ou `FONTES_HTML` em `santos_rpa/infraestrutura/coleta/catalogo.py`. O robô se identifica no
User-Agent, respeita o `robots.txt`, espera 1 segundo entre acessos ao mesmo domínio e guarda apenas título,
resumo e link. Se uma fonte falhar, as demais continuam, e o problema aparece em "Saúde das fontes".

## Tabelas

| Tabela | Conteúdo |
|---|---|
| `noticias` | Notícias aceitas, com tema, tom, história e os componentes da relevância |
| `descartes` | Itens rejeitados e o motivo, para auditar o filtro |
| `execucoes` | Uma linha por execução |
| `execucao_fontes` | Resultado de cada fonte em cada execução |

## Como a relevância é calculada (0 a 100)

| Componente | Pontos | Regra |
|---|---|---|
| Foco | até 30 | 30 = clube explícito no título; 25 = "Santos" no título; 18 = editoria do clube ou pessoa do clube; 15 = só o estádio; 12 = só no resumo; 8 = ex-atleta |
| Tema | até 25 | Diretoria e SAF 25; Mercado 22; Jogo e Lesões 20; Arbitragem 18; Elenco 15; Estádio e Base 12; Seleção 10; História 8; Serviço e Outros 5 |
| Repercussão | até 25 | Veículos diferentes na mesma história: 2 = 8,3; 4 = 16,7; 8 ou mais = 25. "Onde assistir" não pontua |
| Recência | até 20 | Cai pela metade a cada 3 dias |

Os pesos ficam em `santos_rpa/dominio/` (`foco.py`, `tema.py` e `relevancia.py`). A base inteira é reclassificada a cada execução, então uma mudança de regra
vale também para as notícias antigas.

## Somente esporte

Notícias sobre moda, vida pessoal, ações sociais e casos de polícia são rejeitadas, com o motivo "fora de esporte"
na tabela `descartes`. Diretoria, finanças e estádio continuam, porque afetam o time e o jogo. Para mudar esse
critério, edite `FORA_DE_ESPORTE` em `santos_rpa/dominio/foco.py`.

Partidas de outros clubes na Vila Belmiro, como São Paulo x Corinthians, também são rejeitadas, com o motivo "jogo de outros
clubes na Vila Belmiro". A regra vale para títulos que citam o estádio sem citar o Santos e trazem dois clubes, ou um clube e
a palavra "clássico" ou "Majestoso". Notícias sobre a condição do estádio, como gramado e obras, continuam na base.

## Análise de sentimento

O sentimento responde se a notícia é boa ou ruim **para o Santos**: "Palmeiras vence o Santos" é negativo. Cada título
recebe uma nota de -1 a 1, somando pontos por placar e resultado (peso 3), fatos claros (peso 2) e indícios (peso 1).
Os termos que pesaram ficam em `sentimento_termos`.

O **índice de sentimento** vai de -100 a +100 e é calculado como (positivas - negativas) / total, sem os textos de
serviço. O dashboard mostra o índice por dia, por tema, por pessoa, por veículo e depois de cada jogo.

### Quanto dá para confiar

Medição em 219 títulos sorteados e rotulados à mão, sem ver a previsão e sem ajustar regras depois
(`avaliacao/sentimento_teste.csv` e `avaliacao/sentimento_validacao.csv`, sempre do ponto de vista do clube):

| Medida | Resultado |
|---|---|
| Acerto geral | 76% |
| Negativos | Precisão de 78%; encontra 78% |
| Positivos | Precisão de 65%; encontra 61% |

Os resultados variam entre as amostras, os rótulos foram feitos por uma única avaliação, e há só 28 positivos. Use o índice
para comparar períodos e temas, não como valor absoluto. Os títulos usados para criar as regras estão em
`avaliacao/sentimento_desenvolvimento.csv`; se alguma regra ou o modelo mudar, os dois arquivos de avaliação deixam de ser
uma medição às cegas.

### Modelo de IA

As regras decidem primeiro. Quando dão neutro, o modelo `cardiffnlp/twitter-xlm-roberta-base-sentiment`
(`santos_rpa/infraestrutura/ia/modelo_local.py`, versão fixa) opina se tiver confiança de 70% ou mais. Só com as regras, o acerto era de 74% e
apenas 36% dos positivos eram encontrados.

- **Privacidade:** o modelo roda no computador, e os títulos não são enviados a serviços externos.
- **Espaço:** ocupa cerca de 3 GB entre a pasta `dados/modelos/` e o ambiente Python. O download acontece uma vez.
- **Velocidade:** as previsões ficam na tabela `ia_previsoes`, então só títulos novos são analisados.
- **Falhas:** se o modelo não puder rodar, o robô segue só com as regras, registra o aviso no log e informa isso no dashboard.

Foram comparados também `pysentimiento/bertweet-pt-sentiment` e `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`. Nenhum modelo
sozinho superou as regras de forma consistente, porque eles não leem a notícia do ponto de vista do clube.

## Limitações

- **O sentimento é uma estimativa.** Só o título é lido, então ironia e contexto podem gerar erro. O modelo também não
  sabe quem é o clube: "Vitor Roque evolui e deve reforçar o Palmeiras" pode sair como positivo.
- **O filtro não é perfeito.** Separar o clube da cidade e de sobrenomes é feito por regras. Consulte `descartes`
  para ver o que foi rejeitado.
- **O histórico inicial é parcial.** A primeira execução só alcança o que os sites ainda listam e até 100 itens
  por busca no Google News. Comparações entre semanas ficam confiáveis após 14 dias de coleta.
- **A coleta HTML depende do layout dos sites.** Se um site mudar, a fonte aparece como "vazio" em "Saúde das fontes".
- **Listas a manter:** `PESSOAS_DO_CLUBE` em `dominio/foco.py` e `NAO_NOMES` em `dominio/nomes.py` precisam de ajuste quando o elenco mudar.
- **O agregador pesa no total.** Veículos do Google News entram com links de redirecionamento, e sites de torcida,
  como o Santistas.net, contam como veículos.

## Agendamento e dashboard em localhost

Para registrar as tarefas no Agendador do Windows, sem precisar de administrador:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\agendar.ps1
```

| Tarefa | O que faz |
|---|---|
| `Santos RPA` | Roda o robô de hora em hora, sem abrir janela. Se o computador estava desligado ou dormindo, roda quando ele voltar |
| `Santos Dashboard` | Mantém o dashboard em <http://localhost:8765> a partir do login |

O servidor só aceita conexões deste computador e entrega apenas o `dashboard.html`. Recarregue a página para
ver a última execução. As duas tarefas só rodam com o usuário logado. Para removê-las:

```powershell
Unregister-ScheduledTask -TaskName 'Santos RPA', 'Santos Dashboard' -Confirm:$false
```

## O que não vai para o GitHub

O `.gitignore` deixa de fora o ambiente Python, o modelo de IA, os logs, o banco e o dashboard gerado. Quem clonar o projeto
recria tudo com os comandos de "Como executar". Os títulos rotulados em `avaliacao/*.csv` são de veículos de terceiros e vão
junto, porque os testes dependem deles.
