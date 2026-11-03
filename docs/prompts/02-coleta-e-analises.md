# Etapa 2 — Coleta de dados e análises

## Contexto

O `compose.yaml` já tem `ollama`, `ollama-init` e `postgres`, e o modelo está baixado. Nesta etapa você cria o backend
em `backend/` com a parte de **dados**: cadastro de municípios, coleta da chuva (Open-Meteo) e da produção (IBGE),
agendador, registro de cada coleta e as análises que cruzam chuva e rendimento. A parte de IA (chat, descobertas,
alertas) e o treino da previsão chegam nas etapas 3 e 4. Os testes não podem usar a internet nem o Ollama.

## Dependências (`backend/requirements.txt`, versões fixas)

```
fastapi==0.162.0
uvicorn[standard]==0.54.0
pydantic==2.14.2
pydantic-settings==2.16.2
ollama==0.6.3
httpx==0.28.1
psycopg[binary]==3.3.6
psycopg-pool==3.3.3
tzdata==2026.6
```

`requirements-dev.txt`: `-r requirements.txt`, `pytest==9.2.0`, `ruff==0.17.3`. `pyproject.toml`: pytest com
`testpaths = ["tests"]`, marcador `integration` e `addopts = "-m 'not integration'"`; Ruff com `line-length = 120`,
`target-version = "py313"`, `select = ["E", "F", "I", "B", "UP", "SIM"]` e `ignore = ["E501"]`.

`Dockerfile` em três estágios a partir de `python:3.13-slim`: `base` (usuário `app` com uid 1000, dependências),
`test` (dependências de desenvolvimento, `ruff check . && ruff format --check . && pytest`) e `runtime` (`uvicorn
app.main:app` na porta 8000, healthcheck em `/api/health`).

## Organização

Camadas: `api/` (rotas finas) → `services/` (regras) → `repositories/` (SQL com parâmetros `%s`). Os objetos
compartilhados são criados em `core/container.py`. Erros de negócio herdam de `AppError` e viram
`{"erro": {"codigo", "mensagem"}}`, com mensagens em português e a ação a tomar.

- `core/config.py`: `Settings` com todas as variáveis da etapa 1.
- `core/domain.py`: as 27 UFs (código IBGE, sigla, nome); as culturas com a **janela da safra** e os códigos do IBGE:
  soja de outubro do ano anterior a março (PAM 40124; LSPA 39443), milho de janeiro a abril, a 2ª safra (PAM 40122;
  LSPA 39441 e 39442 para 1ª e 2ª safra); nomes e abreviações dos meses; `normalize()` (sem acento, minúsculas).
- `repositories/database.py`: pool do psycopg e o esquema idempotente: `municipalities` (código IBGE, nome, UF,
  latitude, longitude, `principal`, `status` coletando/pronto/erro, mensagem), `state_references` (municípios de
  referência da chuva da UF, com a área de soja), `weather_daily` (município, dia, mm, `source` arquivo/recente),
  `crop_yearly` (nível municipio/uf/brasil, território, cultura, ano, áreas, produção, rendimento), `crop_estimates`
  (LSPA por período AAAAMM) e `collection_runs` (fonte chuva/producao/estimativa, origem agendada/botao/cadastro,
  situação executando/concluida/sem_novidade/erro, registros, mensagem, início e fim).

## Fontes públicas (`services/public_data.py`)

Um cliente HTTP que só acessa uma **lista fixa de endereços** por HTTPS, tenta de novo em erro de rede, 5xx e 429, e
explica o erro em português. Protocolos `RainSource` e `IbgeSource`, para os testes usarem dublês.

- Open-Meteo: arquivo `https://archive-api.open-meteo.com/v1/archive` (`daily=precipitation_sum`, fuso
  `America/Sao_Paulo`, dias `null` descartados); previsão `https://api.open-meteo.com/v1/forecast` com `past_days` para
  os dias que o arquivo ainda não tem (sem o dia de hoje); coordenadas em
  `https://geocoding-api.open-meteo.com/v1/search`, aceitando só resultado do Brasil com o mesmo nome e a mesma UF.
- IBGE: nome e UF do município (`/api/v1/localidades/municipios/{código}`, com a região imediata quando não houver
  microrregião), municípios de uma UF, último ano da PAM (`/api/v3/agregados/5457/periodos`), PAM pelo SIDRA
  (`/t/5457/n6|n3|n1/.../v/8331,216,214,112/p/{início}-{fim}/c782/40124,40122`), municípios que mais plantam soja na
  UF (`n6/in n3 {UF}`, variável 8331) e LSPA (`/t/6588/.../v/109,216,35,36/p/last N/c48/39441,39442,39443`). No SIDRA,
  `-` é zero, e `..`, `...` e `X` são sem dado; o nome do município vem como "Rio Verde - GO" ou "Rio Verde (GO)".

## Coletas (`services/collection_service.py`)

- **Cadastro** (`POST /api/municipalities {code}`): busca nome e coordenadas, grava como principal e, em segundo
  plano: escolhe os `STATE_REFERENCE_COUNT` municípios que mais plantam soja na UF (se a UF ainda não tiver), baixa a
  chuva desde `HISTORY_START_YEAR` dos que não têm, baixa a produção e a estimativa. A situação do município mostra o
  passo atual ("Baixando a chuva diária desde 2000…") e termina em `pronto` ou `erro` com a mensagem.
- **Chuva**: incremental, só os dias depois do último do arquivo; depois os últimos 10 dias da previsão como
  `recente`, que nunca substituem o arquivo.
- **Produção**: municípios (principais e referências), UFs com cadastro e Brasil; busca de novo os 2 últimos anos
  (o IBGE revisa) e conta só o que entrou ou mudou de valor.
- **Estimativa**: LSPA das UFs com cadastro e do Brasil.
- **Uma coleta por vez em cada fonte** (trava por fonte). O botão (`POST /api/collections/{fonte}`) recebe 409 se a
  fonte estiver coletando e 422 sem município cadastrado. Toda coleta grava o registro; sem dado novo, a situação é
  `sem_novidade` e a mensagem é "Já está atualizado: último ano disponível 2025." (ou o equivalente da fonte).
- Na inicialização, coletas e cadastros `executando`/`coletando` viram erro ("interrompida").

## Agendador (`services/scheduler.py`)

Thread que confere a cada minuto, pelo registro no banco, se alguma coleta está atrasada (`is_due`, função pura):
chuva todo dia a partir de `RAIN_COLLECT_HOUR`; produção e estimativa a partir do dia `MONTHLY_COLLECT_DAY` do mês.
Qualquer coleta bem-sucedida no período conta (inclusive pelo botão). Depois de erro, espera 60 minutos. Desligado
com `SCHEDULER_ENABLED=false`.

## Análises

- `services/statistics.py`: média, reta de mínimos quadrados, Pearson com p-valor (teste t com a beta incompleta
  regularizada), Benjamini-Hochberg.
- `services/seasons.py` (funções puras): soma por mês com marcação de mês completo, chuva da janela (só com todos os
  dias), maior veranico (dias seguidos com menos de 1 mm), chuva da UF (média ponderada pela área, com pelo menos
  metade da área com dado), safras com tendência e **desvio da tendência** (o rendimento sobe com a tecnologia),
  climatologia mensal e a safra em andamento comparada ao mesmo trecho das safras passadas.
- `services/charts.py`: especificações de gráfico com os nomes das props do Kole em snake_case (`tipo`, `titulo`,
  `dados`, `eixo_x`, `eixo_y`, `eixo_y_direito`, `series`, `barras`, `linhas`, `divergente`, `orientacao`, `chave_x`…):
  combinado chuva da safra × rendimento com a tendência, dispersão com regressão, barras divergentes do desvio, linhas
  do rendimento município × UF × Brasil, chuva mensal com a média histórica, mapa de calor ano × mês e ranking das
  referências.
- `GET /api/analyses/{código}/{cultura}`: safras, correlação, indicadores (chuva da última safra com o desvio,
  veranico, rendimento com o desvio, r e p) e os gráficos, com notas de método. `GET /api/estimates`: último
  levantamento da LSPA com o rendimento esperado pela tendência.

## Rotas desta etapa

`/api/health`, `/api/status` (backend, Ollama e se o modelo aceita ferramentas, banco, agendador),
`/api/municipalities` (listar, cadastrar, ver, excluir), `/api/ibge/states/{UF}/municipalities`,
`/api/collections` (fontes com o último dado e o agendamento, e as 50 coletas mais recentes),
`/api/collections/{fonte}`, `/api/analyses/{código}/{cultura}`, `/api/estimates`.

## Testes

Dublês em `tests/fakes.py`: chuva sintética determinística (estação chuvosa e seca, anos mais e menos chuvosos), PAM
sintética em que o rendimento cresce com a tendência e acompanha a chuva da safra, LSPA, executor que roda na hora e
executor que só guarda as tarefas (para testar a coleta em andamento). PostgreSQL de teste: tabelas limpas antes de
cada teste. Cubra: estatística com valores de referência, janelas e veranico, clientes com `httpx.MockTransport`
(endereço não permitido, nova tentativa, parsing do SIDRA), cadastro completo, 409 com a fonte coletando, "Já está
atualizado", ano novo da PAM, exclusão, `is_due` e o `tick` do agendador, análises e status.

## Verificação

```bash
docker compose --profile test run --rm --build backend-tests
docker compose --profile test rm -fs postgres-test
```

Ruff sem erros e todos os testes passando, sem internet nem Ollama.
