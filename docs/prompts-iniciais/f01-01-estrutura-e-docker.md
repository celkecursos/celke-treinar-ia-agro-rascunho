# Estrutura inicial e serviços de IA no Docker

**Etapa:** 1 de 6
**Requer:** etapa 0 (`.env` e `docs/configuracao.md`)

## Orientação antes de começar

> **O que vai acontecer agora:** vou criar a estrutura do projeto e baixar o Ollama, o PostgreSQL e o modelo de IA.
> **É a parte mais demorada:** de alguns minutos a mais de uma hora, conforme a internet e o modelo.
> **O que você precisa fazer:** nada. Deixe o Docker aberto. Para acompanhar o download, em outro terminal:
> `docker compose logs -f ollama-init`. Se a barra parecer parada, é normal por alguns minutos.

## Prompt

Você está criando o **Celke Treinar IA Agro**. Nesta etapa, crie os arquivos da raiz: o Compose com todos os serviços
(inclusive os do fine-tuning, no profile `finetune`), as pastas do fine-tuning e os scripts de inicialização. Backend,
frontend e o treino chegam nas próximas etapas.

Decisões já tomadas: só o `frontend` publica porta, em `127.0.0.1`; o Ollama roda no Docker (imagem fixa `0.40.13`); o
serviço `ollama-init` baixa o modelo se faltar; o modelo vem de `CHAT_MODEL` no `.env`; a coleta de dados públicos
(Open-Meteo e IBGE) é feita pelo backend, que só acessa esses endereços.

Regras desta etapa:

- Crie os arquivos com **exatamente** o conteúdo indicado, sem melhorar nem reformatar. O conteúdo já foi
  testado junto; uma alteração aqui quebra outra etapa.
- Não pergunte nada ao usuário: as decisões estão neste prompt e em `docs/configuracao.md`.
- Mostre ao usuário as seções **Orientação** (antes de começar e ao terminar), com as suas palavras só onde
  houver marcador a trocar. Se o terminal não permitir mostrar agora, inclua no seu relatório final.
- Rode tudo o que está em **Verificação** e corrija o que falhar antes de terminar.
- Nunca mostre o valor de `POSTGRES_PASSWORD`.

Depois, deixe `scripts/iniciar.sh` executável: `chmod +x scripts/iniciar.sh`.

`.gitignore`:

``````text
.env
node_modules/
dist/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
.venv/
*.log
.DS_Store
# fine-tuning: dataset gerado, modelos baixados e treinados (vários GB)
finetuning/data/*
!finetuning/data/.gitkeep
finetuning/output/*
!finetuning/output/.gitkeep
finetuning/cache/
``````

`.gitattributes`:

``````text
# Scripts de shell sempre com LF, mesmo em clones no Windows: com CRLF o sh não os executa.
*.sh text eol=lf
``````

`.dockerignore`:

``````text
.git
.env
**/node_modules
**/dist
**/__pycache__
docs
``````

`.env.example`:

``````text
# Copie para .env e ajuste. Sem .env, os valores padrão do compose.yaml são usados.

# Endereço do navegador: http://localhost:8091
APP_PORT=8091
# 127.0.0.1 = só neste computador. 0.0.0.0 abre na rede local (sem login: veja "Segurança" no README).
APP_BIND=127.0.0.1

# GPU NVIDIA: descomente a linha do seu sistema (o separador muda). Sem GPU, deixe comentado.
# COMPOSE_FILE=compose.yaml;compose.gpu.yaml
# COMPOSE_FILE=compose.yaml:compose.gpu.yaml

# PostgreSQL. Obrigatório: os scripts/iniciar.* geram uma senha aleatória no .env na primeira vez. O banco
# não tem porta publicada; a senha vale só na criação do volume postgres-data.
POSTGRES_PASSWORD=
POSTGRES_DB=celke_agro
POSTGRES_USER=celke

# Modelo do Ollama (baixado pelo serviço ollama-init na primeira subida). Precisa aceitar ferramentas
# (tool calling). qwen3:8b roda em CPU com 16 GB de RAM; qwen3:14b pede GPU com 12 GB.
CHAT_MODEL=qwen3:8b
# Janela de contexto do modelo (tokens). Mais contexto = mais memória.
CHAT_NUM_CTX=8192
CHAT_TEMPERATURE=0.2
# Raciocínio do modelo: false é bem mais rápido e escolhe as ferramentas igual; true pensa antes de responder.
CHAT_THINK=false
OLLAMA_TIMEOUT_SECONDS=300
# Tempo que o modelo fica carregado na memória depois da última pergunta
OLLAMA_KEEP_ALIVE=30m
# Mensagens anteriores da conversa enviadas ao modelo
HISTORY_MAX_MESSAGES=6
# Rodadas de ferramentas por pergunta, antes de o modelo ser obrigado a responder
MAX_TOOL_ROUNDS=5

# Coleta de dados públicos (Open-Meteo e IBGE). Só saem do computador nomes de municípios, coordenadas,
# datas e códigos do IBGE.
# Primeiro ano baixado de chuva e produção. Mais anos = análises melhores e primeira coleta mais longa.
HISTORY_START_YEAR=2000
# Municípios que mais plantam soja na UF, usados na chuva média da UF (média ponderada pela área)
STATE_REFERENCE_COUNT=5
HTTP_TIMEOUT_SECONDS=60

# Agendamento: chuva todo dia, produção (PAM) e estimativa de safra (LSPA) uma vez por mês.
SCHEDULER_ENABLED=true
SCHEDULER_TIMEZONE=America/Sao_Paulo
# Hora da coleta diária de chuva
RAIN_COLLECT_HOUR=6
# Dia do mês da coleta de produção e estimativa de safra
MONTHLY_COLLECT_DAY=1

# Descobertas: só entram relações que passam no filtro estatístico
# q = p-valor corrigido para muitos testes (Benjamini-Hochberg)
DISCOVERY_MAX_Q=0.10
# Correlação mínima, em módulo
DISCOVERY_MIN_ABS_R=0.4
# Safras mínimas para testar uma relação
DISCOVERY_MIN_YEARS=8

# Alertas da safra em andamento
# Chuva acumulada na janela da safra abaixo da média histórica do mesmo período (%)
ALERT_RAIN_DEFICIT_PCT=25
# Dias seguidos sem chuva (menos de 1 mm) dentro da janela
ALERT_DRY_SPELL_DAYS=10

# Fine-tuning (etapa opcional, GPU NVIDIA): modelo base do Hugging Face, épocas e tamanho máximo de cada exemplo.
# O 8B pede GPU de 12 GB; com 8 GB, use unsloth/Qwen3-4B (e qwen3:4b como base no criar_modelo.sh).
FINETUNE_BASE_MODEL=unsloth/Qwen3-8B
FINETUNE_EPOCHS=2
FINETUNE_MAX_SEQ_LENGTH=4096
``````

`compose.yaml`:

``````yaml
# Celke Treinar IA Agro: frontend (nginx + React), backend (FastAPI), Ollama e PostgreSQL.
# Subir: scripts/iniciar.sh / scripts/iniciar.ps1 (criam o .env com a senha do banco na primeira vez)
# ou docker compose up -d --build com POSTGRES_PASSWORD no .env (sem senha o postgres não sobe).
# Valores padrão abaixo; para mudar, copie .env.example para .env.
name: celke-treinar-ia-agro

# Variáveis do backend, usadas também pelas ferramentas do fine-tuning.
x-backend-environment: &backend-environment
  OLLAMA_URL: http://ollama:11434
  OLLAMA_TIMEOUT_SECONDS: ${OLLAMA_TIMEOUT_SECONDS:-300}
  CHAT_MODEL: ${CHAT_MODEL:-qwen3:8b}
  CHAT_NUM_CTX: ${CHAT_NUM_CTX:-8192}
  CHAT_TEMPERATURE: ${CHAT_TEMPERATURE:-0.2}
  CHAT_THINK: ${CHAT_THINK:-false}
  HISTORY_MAX_MESSAGES: ${HISTORY_MAX_MESSAGES:-6}
  MAX_TOOL_ROUNDS: ${MAX_TOOL_ROUNDS:-5}
  POSTGRES_HOST: postgres
  POSTGRES_PORT: 5432
  POSTGRES_DB: ${POSTGRES_DB:-celke_agro}
  POSTGRES_USER: ${POSTGRES_USER:-celke}
  POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-}
  HISTORY_START_YEAR: ${HISTORY_START_YEAR:-2000}
  STATE_REFERENCE_COUNT: ${STATE_REFERENCE_COUNT:-5}
  HTTP_TIMEOUT_SECONDS: ${HTTP_TIMEOUT_SECONDS:-60}
  SCHEDULER_ENABLED: ${SCHEDULER_ENABLED:-true}
  SCHEDULER_TIMEZONE: ${SCHEDULER_TIMEZONE:-America/Sao_Paulo}
  RAIN_COLLECT_HOUR: ${RAIN_COLLECT_HOUR:-6}
  MONTHLY_COLLECT_DAY: ${MONTHLY_COLLECT_DAY:-1}
  DISCOVERY_MAX_Q: ${DISCOVERY_MAX_Q:-0.10}
  DISCOVERY_MIN_ABS_R: ${DISCOVERY_MIN_ABS_R:-0.4}
  DISCOVERY_MIN_YEARS: ${DISCOVERY_MIN_YEARS:-8}
  ALERT_RAIN_DEFICIT_PCT: ${ALERT_RAIN_DEFICIT_PCT:-25}
  ALERT_DRY_SPELL_DAYS: ${ALERT_DRY_SPELL_DAYS:-10}

services:
  frontend:
    build:
      context: ./frontend
      target: runtime
    # Só no próprio computador. Para abrir na rede local, troque 127.0.0.1 por 0.0.0.0 (ver README).
    ports:
      - "${APP_BIND:-127.0.0.1}:${APP_PORT:-8091}:80"
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped

  backend:
    build:
      context: ./backend
      target: runtime
    environment: *backend-environment
    depends_on:
      postgres:
        condition: service_healthy
      ollama:
        condition: service_healthy
    restart: unless-stopped

  ollama:
    image: ollama/ollama:0.40.13
    volumes:
      - ollama-models:/root/.ollama
      # modelo treinado no fine-tuning, para o `ollama create` (finetuning/criar_modelo.sh)
      - ./finetuning:/finetuning:ro
    environment:
      OLLAMA_KEEP_ALIVE: ${OLLAMA_KEEP_ALIVE:-30m}
    healthcheck:
      test: ["CMD", "ollama", "list"]
      interval: 10s
      timeout: 5s
      start_period: 20s
      retries: 10
    restart: unless-stopped

  # Baixa o modelo se faltar e termina. O modelo fica no volume ollama-models.
  ollama-init:
    image: ollama/ollama:0.40.13
    environment:
      OLLAMA_HOST: http://ollama:11434
      CHAT_MODEL: ${CHAT_MODEL:-qwen3:8b}
    entrypoint: ["/bin/sh", "-c"]
    command:
      - |
        if ollama show "$$CHAT_MODEL" > /dev/null 2>&1; then
          echo "Modelo $$CHAT_MODEL já instalado."
        else
          echo "Baixando $$CHAT_MODEL (só na primeira vez)..."
          ollama pull "$$CHAT_MODEL" || exit 1
        fi
        echo "Modelo pronto."
    depends_on:
      ollama:
        condition: service_healthy
    restart: "no"

  # Municípios, chuva, produção, coletas, descobertas, alertas e conversas.
  postgres:
    image: postgres:18.6-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-celke_agro}
      POSTGRES_USER: ${POSTGRES_USER:-celke}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-}
    volumes:
      # a partir do PostgreSQL 18 o volume fica em /var/lib/postgresql (os dados vão em 18/docker)
      - postgres-data:/var/lib/postgresql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U \"$$POSTGRES_USER\" -d \"$$POSTGRES_DB\""]
      interval: 5s
      timeout: 5s
      start_period: 10s
      retries: 10
    restart: unless-stopped

  # Fine-tuning (etapa opcional): dataset e avaliação no container do backend.
  # docker compose --profile finetune run --rm finetune-tools exportar
  # docker compose --profile finetune run --rm finetune-tools avaliar --modelo qwen3:8b
  finetune-tools:
    profiles: [finetune]
    build:
      context: ./backend
      target: runtime
    environment: *backend-environment
    entrypoint: ["python", "-m", "app.finetune"]
    volumes:
      - ./finetuning:/finetuning
    depends_on:
      postgres:
        condition: service_healthy
      ollama:
        condition: service_healthy

  # Treino LoRA na GPU NVIDIA: docker compose --profile finetune run --rm finetune-train
  finetune-train:
    profiles: [finetune]
    build:
      context: ./finetuning
    environment:
      BASE_MODEL: ${FINETUNE_BASE_MODEL:-unsloth/Qwen3-8B}
      EPOCHS: ${FINETUNE_EPOCHS:-2}
      MAX_SEQ_LENGTH: ${FINETUNE_MAX_SEQ_LENGTH:-4096}
    volumes:
      - ./finetuning:/finetuning
    shm_size: 8gb
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

  # docker compose --profile test run --rm backend-tests
  backend-tests:
    profiles: [test]
    build:
      context: ./backend
      target: test
    environment:
      POSTGRES_HOST: postgres-test
      POSTGRES_DB: celke_agro_test
      POSTGRES_USER: celke
      SCHEDULER_ENABLED: "false"
      INTEGRATION_API_URL: http://backend:8000/api
    depends_on:
      postgres-test:
        condition: service_healthy

  # Banco descartável dos testes unitários: em memória, sem senha e sem volume.
  postgres-test:
    profiles: [test]
    image: postgres:18.6-alpine
    environment:
      POSTGRES_DB: celke_agro_test
      POSTGRES_USER: celke
      POSTGRES_HOST_AUTH_METHOD: trust
    tmpfs:
      - /var/lib/postgresql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U celke -d celke_agro_test"]
      interval: 2s
      timeout: 5s
      retries: 15

  # docker compose --profile test run --rm frontend-tests
  frontend-tests:
    profiles: [test]
    build:
      context: ./frontend
      target: test

volumes:
  ollama-models:
  postgres-data:
``````

`compose.gpu.yaml`:

``````yaml
# GPU NVIDIA. Windows: basta o driver NVIDIA e o Docker Desktop com WSL2. Linux: requer o NVIDIA
# Container Toolkit. Para valer sempre, use COMPOSE_FILE no .env (ver .env.example).
# docker compose -f compose.yaml -f compose.gpu.yaml up -d
services:
  ollama:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
``````

`compose.dev.yaml`:

``````yaml
# Desenvolvimento do frontend com o Vite (npm run dev): publica a API em 127.0.0.1:8000.
# docker compose -f compose.yaml -f compose.dev.yaml up -d
services:
  backend:
    ports:
      - "127.0.0.1:8000:8000"
``````

`scripts/iniciar.sh`:

``````sh
#!/usr/bin/env sh
# Sobe o Celke Treinar IA Agro, espera o modelo e mostra o endereço. Pode rodar quantas vezes quiser.
set -eu
cd "$(dirname "$0")/.."

if ! docker info > /dev/null 2>&1; then
  echo "O Docker não está rodando. Abra o Docker Desktop (ou inicie o serviço docker) e tente de novo."
  exit 1
fi

# Senha do PostgreSQL: gerada uma vez e guardada no .env (o banco guarda a senha da primeira subida).
if ! grep -qs "^POSTGRES_PASSWORD=..*" .env; then
  value=$(od -An -N24 -tx1 /dev/urandom | tr -d ' \n')
  if [ -f .env ]; then
    grep -v "^POSTGRES_PASSWORD=" .env > .env.tmp || true
    mv .env.tmp .env
  fi
  printf 'POSTGRES_PASSWORD=%s\n' "$value" >> .env
  chmod 600 .env
  echo "POSTGRES_PASSWORD criada no arquivo .env (guarde o arquivo; não o envie ao git)."
fi

echo "Subindo os serviços (a primeira vez constrói as imagens e pode levar alguns minutos)..."
docker compose up -d --build

echo "Aguardando o modelo (o download só acontece na primeira vez; são de 5 a 9 GB)."
echo "Para ver o progresso, em outro terminal: docker compose logs -f ollama-init"
status=$(docker wait celke-treinar-ia-agro-ollama-init-1)
if [ "$status" != "0" ]; then
  echo "Falha ao baixar o modelo. Veja: docker compose logs ollama-init"
  exit 1
fi

echo "Verificando a API..."
port=$(docker compose port frontend 80 | sed 's/.*://')
for _ in $(seq 1 30); do
  if docker compose exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)" > /dev/null 2>&1; then
    echo ""
    echo "Pronto! Abra http://localhost:$port"
    echo "Documentação da API: http://localhost:$port/api/docs"
    echo "Logs: docker compose logs -f backend    Parar: docker compose stop"
    exit 0
  fi
  sleep 2
done
echo "A API não respondeu. Veja: docker compose ps && docker compose logs backend"
exit 1
``````

`scripts/iniciar.ps1`:

``````powershell
# Sobe o Celke Treinar IA Agro no Windows (PowerShell), espera o modelo e mostra o endereço.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\iniciar.ps1
# Sem 'Stop': no PowerShell 5.1, um simples aviso do Docker no stderr viraria erro fatal com *> $null.
# As falhas do Docker sao conferidas pelo $LASTEXITCODE.
$ErrorActionPreference = 'Continue'
Set-Location (Join-Path $PSScriptRoot '..')

docker info *> $null
if ($LASTEXITCODE -ne 0) {
  Write-Host 'O Docker nao esta rodando. Abra o Docker Desktop e tente de novo.'
  exit 1
}

# Senha do PostgreSQL: gerada uma vez e guardada no .env (o banco guarda a senha da primeira subida).
$envFile = Join-Path (Get-Location) '.env'
$lines = @()
if (Test-Path $envFile) { $lines = @(Get-Content $envFile -Encoding UTF8) }
if (-not ($lines | Where-Object { $_ -match '^POSTGRES_PASSWORD=.+' })) {
  $bytes = New-Object byte[] 24
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  $value = -join ($bytes | ForEach-Object { $_.ToString('x2') })
  $lines = @($lines | Where-Object { $_ -notmatch '^POSTGRES_PASSWORD=' }) + "POSTGRES_PASSWORD=$value"
  # UTF-8 sem BOM: o Docker Compose le o .env assim
  [System.IO.File]::WriteAllLines($envFile, [string[]]$lines)
  Write-Host 'POSTGRES_PASSWORD criada no arquivo .env (guarde o arquivo; nao o envie ao git).'
}

Write-Host 'Subindo os servicos (a primeira vez constroi as imagens e pode levar alguns minutos)...'
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host 'Aguardando o modelo (o download so acontece na primeira vez; sao de 5 a 9 GB).'
Write-Host 'Para ver o progresso, em outro terminal: docker compose logs -f ollama-init'
$status = docker wait celke-treinar-ia-agro-ollama-init-1
if ($status -ne '0') {
  Write-Host 'Falha ao baixar o modelo. Veja: docker compose logs ollama-init'
  exit 1
}

$port = ((docker compose port frontend 80) -split ':')[-1]
for ($i = 0; $i -lt 30; $i++) {
  docker compose exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)" *> $null
  if ($LASTEXITCODE -eq 0) {
    Write-Host ''
    Write-Host "Pronto! Abra http://localhost:$port"
    Write-Host "Documentacao da API: http://localhost:$port/api/docs"
    Write-Host 'Logs: docker compose logs -f backend    Parar: docker compose stop'
    exit 0
  }
  Start-Sleep -Seconds 2
}
Write-Host 'A API nao respondeu. Veja: docker compose ps; docker compose logs backend'
exit 1
``````

Crie também estes arquivos **vazios**:

- `finetuning/data/.gitkeep`
- `finetuning/output/.gitkeep`

## Verificação

```bash
docker compose config -q && echo compose-ok
docker compose up -d ollama postgres ollama-init
docker wait celke-treinar-ia-agro-ollama-init-1    # 0 ao terminar o download; pode levar muito tempo
docker compose ps                                   # ollama e postgres healthy, sem porta publicada
docker compose exec -T ollama ollama list           # o modelo do .env
docker compose exec -T postgres psql -U celke celke_agro -c "select version()"
```

Rode o download em segundo plano, se a sua ferramenta permitir, e avise o usuário a cada etapa concluída. Se o
`ollama-init` terminar com erro, veja `docker compose logs ollama-init`: repita `docker compose up ollama-init` se foi
queda de internet.

Com GPU, confira que o Ollama a detectou: `docker compose logs ollama` tem `inference compute` com o nome da placa.

## Depois de executar

```bash
git add .gitignore .gitattributes .dockerignore .env.example compose.yaml compose.gpu.yaml compose.dev.yaml scripts finetuning LICENSE.txt docs/configuracao.md
git update-index --chmod=+x scripts/iniciar.sh
git commit -m "chore: cria a estrutura inicial e os serviços de IA no Docker"
```

## Orientação ao terminar

> **Pronto:** os serviços de IA estão no ar e o modelo foi baixado. Ele não será baixado de novo. Continue sem fazer nada.
