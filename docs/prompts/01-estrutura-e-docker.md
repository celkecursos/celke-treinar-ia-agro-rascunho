# Etapa 1 — Estrutura inicial e Docker

## Contexto

Você vai criar o Celke Treinar IA Agro: uma IA local que coleta chuva diária (Open-Meteo) e produção de soja e milho
(IBGE), cruza os dados e usa um modelo do Ollama com ferramentas para responder perguntas, descobrir relações e
avisar sobre a safra em andamento. Nesta etapa você cria só a estrutura e os serviços de infraestrutura no Docker.
Backend e frontend chegam nas próximas etapas: crie as pastas vazias `backend` e `frontend`.

## Arquivos da raiz

- `.gitignore`: `.env`, `node_modules/`, `dist/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.ruff_cache/`, `.venv/`,
  `*.log`, `.DS_Store`.
- `.gitattributes`: `*.sh text eol=lf` (com CRLF o `sh` não executa os scripts clonados no Windows).
- `.dockerignore`: `.git`, `.env`, `**/node_modules`, `**/dist`, `**/__pycache__`, `docs`.
- `LICENSE.txt`: MIT, com o nome de `git config user.name` e o ano atual.

## `compose.yaml`

`name: celke-treinar-ia-agro`. As variáveis do backend ficam numa âncora YAML (`x-backend-environment:
&backend-environment`), usada pelo `backend` e, na etapa 6, pelas ferramentas do fine-tuning. Serviços:

| Serviço | Imagem / build | Detalhes |
|---|---|---|
| `frontend` | build `./frontend`, target `runtime` | Única porta publicada: `"${APP_BIND:-127.0.0.1}:${APP_PORT:-8091}:80"`; depende do backend saudável |
| `backend` | build `./backend`, target `runtime` | Sem porta; todas as variáveis da tabela abaixo com padrão; volume `backend-ssh:/data/ssh`; depende de `postgres` e `ollama` saudáveis |
| `ollama` | `ollama/ollama:0.40.13` | Volume `ollama-models:/root/.ollama`; `OLLAMA_KEEP_ALIVE`; healthcheck `ollama list` |
| `ollama-init` | `ollama/ollama:0.40.13` | `OLLAMA_HOST=http://ollama:11434`; baixa `CHAT_MODEL` só se `ollama show` falhar; termina; `restart: "no"` |
| `postgres` | `pgvector/pgvector:0.8.6-pg18-trixie` (PostgreSQL 18 com a extensão pgvector, para vetores no próprio banco) | Volume `postgres-data:/var/lib/postgresql` (a partir do 18 o volume é esse caminho); senha de `POSTGRES_PASSWORD` **sem padrão**; healthcheck `pg_isready` |
| `backend-tests` | build `./backend`, target `test`, profile `test` | `POSTGRES_HOST=postgres-test`, `POSTGRES_DB=celke_agro_test`, `SCHEDULER_ENABLED=false`, `INTEGRATION_API_URL=http://backend:8000/api` |
| `postgres-test` | `pgvector/pgvector:0.8.6-pg18-trixie`, profile `test` | Em memória (`tmpfs: /var/lib/postgresql`), `POSTGRES_HOST_AUTH_METHOD=trust` |
| `frontend-tests` | build `./frontend`, target `test`, profile `test` | — |

Variáveis do backend (com o padrão):

```
OLLAMA_URL=http://ollama:11434          GPU_TUNNEL_PORT=11435          OLLAMA_TIMEOUT_SECONDS=300
CHAT_MODEL=qwen3:8b
CHAT_NUM_CTX=8192                       CHAT_TEMPERATURE=0.2           CHAT_THINK=false
HISTORY_MAX_MESSAGES=6                  MAX_TOOL_ROUNDS=5
POSTGRES_HOST=postgres  POSTGRES_PORT=5432  POSTGRES_DB=celke_agro  POSTGRES_USER=celke  POSTGRES_PASSWORD=
HISTORY_START_YEAR=2000                 STATE_REFERENCE_COUNT=5        HTTP_TIMEOUT_SECONDS=60
SCHEDULER_ENABLED=true                  SCHEDULER_TIMEZONE=America/Sao_Paulo
RAIN_COLLECT_HOUR=6                     MONTHLY_COLLECT_DAY=1
DISCOVERY_MAX_Q=0.10                    DISCOVERY_MIN_ABS_R=0.4        DISCOVERY_MIN_YEARS=8
ALERT_RAIN_DEFICIT_PCT=25               ALERT_DRY_SPELL_DAYS=10
```

GPU externa (por exemplo, a GPU hosting da Hostinger): nenhum arquivo de compose a mais e nada no `.env`. O backend
abre o túnel SSH ele mesmo (etapa 4) e guarda a chave SSH que gera no volume `backend-ssh`, montado em `/data/ssh` (o
`Dockerfile` cria a pasta com dono `app` e permissão 700). A porta do túnel (`GPU_TUNNEL_PORT`) não é publicada: só
a rede do Docker a alcança (`http://backend:11435`, usado pelo `finetune-tools` para avaliar um modelo do servidor).
Os scripts de inicialização esperam o `ollama-init` terminar.

`compose.gpu.yaml`: no `ollama`, `deploy.resources.reservations.devices` com `driver: nvidia`, `count: all`,
`capabilities: [gpu]`. `compose.dev.yaml`: publica o backend em `127.0.0.1:8000` (só para o Vite em desenvolvimento).

## `.env.example`

Todas as variáveis acima e `APP_PORT`, `APP_BIND`, `OLLAMA_KEEP_ALIVE` e as duas linhas comentadas de
`COMPOSE_FILE` (com `;` no Windows e `:` no Linux), cada uma com um comentário curto em português. Explique que o
modelo precisa aceitar ferramentas (tool calling), que `qwen3:8b` roda na CPU com 16 GB de RAM e que `qwen3:14b` pede
GPU de 12 GB, e que `CHAT_THINK=false` é bem mais rápido e escolhe as ferramentas igual.

## Scripts

`scripts/iniciar.sh` e `scripts/iniciar.ps1` (PowerShell 5.1, sem `$ErrorActionPreference = 'Stop'`, conferindo
`$LASTEXITCODE`):

1. Saem com mensagem clara se o Docker não estiver rodando.
2. Se o `.env` não tiver `POSTGRES_PASSWORD` com valor, geram 48 caracteres hexadecimais aleatórios e gravam no
   `.env` (UTF-8 sem BOM no PowerShell; `chmod 600` no sh).
3. `docker compose up -d --build`.
4. Esperam o `ollama-init` terminar (`docker wait celke-treinar-ia-agro-ollama-init-1`) e falham se o código não for 0.
5. Conferem `/api/health` dentro do backend e mostram `Pronto! Abra http://localhost:<porta>`, o endereço de
   `/api/docs` e os comandos de logs e parada.

Deixe o `scripts/iniciar.sh` executável.

## Verificação

```bash
docker compose config -q && echo compose-ok
cp .env.example .env && sed -i "s/^POSTGRES_PASSWORD=$/POSTGRES_PASSWORD=$(od -An -N24 -tx1 /dev/urandom | tr -d ' \n')/" .env
docker compose up -d ollama postgres ollama-init
docker wait celke-treinar-ia-agro-ollama-init-1        # 0 ao terminar o download; pode levar muito tempo
docker compose ps                                       # ollama e postgres healthy, sem porta publicada
docker compose exec -T ollama ollama list               # o modelo de CHAT_MODEL
docker compose exec -T postgres psql -U celke celke_agro -c "select version()"
docker compose exec -T postgres psql -U celke celke_agro -c "select default_version from pg_available_extensions where name = 'vector'"
```

Nunca mostre o valor de `POSTGRES_PASSWORD`.
