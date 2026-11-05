# Guia para agentes de IA e desenvolvedores

Convenções deste repositório. Leia o `README.md` antes de começar: ele descreve a arquitetura, o método, os
comandos e as variáveis de ambiente.

| Pasta | Projeto | Stack |
|---|---|---|
| `backend/` | API, coletas, agendador, análises, previsão treinada, descobertas, alertas, chat com ferramentas e dataset/avaliação do fine-tuning | Python 3.13, FastAPI, Pydantic, httpx, Ollama, PostgreSQL 18 com pgvector (psycopg 3) |
| `finetuning/` | Treino LoRA na GPU e criação do modelo no Ollama | Python 3.12, Unsloth (versões fixas), Docker com GPU NVIDIA |
| `frontend/` | Análises, Previsão, Chat, Descobertas, Alertas, Municípios, Status e Modelo de IA | React 19, TypeScript, Vite, React Router, `@celke/kole-react` |
| raiz | Docker Compose, scripts de inicialização | Docker Compose |
| `docs/prompts-iniciais/` | Prompts que recriam o projeto do zero, sozinhos, com o conteúdo exato dos arquivos (gerados) | Markdown |
| `docs/prompts/` | As mesmas etapas descritas em texto, para o tutorial | Markdown |
| `docs/gerador-prompts/` | Gera e confere `docs/prompts-iniciais/` | Python |

## Branches e commits

- `main` = versão estável, `homolog` = homologação. Trabalhe numa branch própria a partir de `homolog`
  (`feature/nome` ou `fix/nome`) e entregue por Pull Request para `homolog`.
- Commit, push e Pull Request só quando o desenvolvedor pedir. Mensagens no padrão Conventional Commits em
  português, **sem** coautoria nem menção a ferramenta de IA.

## Regra central: o código calcula, o modelo interpreta

- Somas, médias, tendência, desvio, correlação, p-valor e q-valor ficam no código (`services/statistics.py`,
  `services/seasons.py`, `services/analysis_service.py`). O modelo nunca recebe dados crus para calcular.
- O modelo só escolhe ferramentas da lista fechada de `services/tools.py` e escreve texto. Nada de SQL escrito pelo
  modelo, nada de execução de comandos.
- Ferramenta nova: modelo Pydantic dos argumentos, entrada em `TOOL_SPECS` (descrição clara para o modelo) e em
  `ToolExecutor._handlers`, resultado com os números já calculados, `fonte` e um `summary` curto para a tela. Nomes
  de campo do resultado precisam ser explícitos (`desvio_da_media_historica_do_municipio_pct`, não `desvio_pct`): o
  modelo confunde nomes ambíguos.
- Termos e fases das culturas vão no `GLOSSARY` de `core/domain.py`, usado em todos os prompts.
- Dois treinamentos de verdade, cada um com medição:
  - **Previsão da safra** (`services/forecast_model.py`, `services/forecast_service.py`): regressão treinada com as
    safras do município, retreinada a cada coleta com dado novo; validação deixando uma safra de fora, sempre
    comparada à tendência sozinha. Se a chuva não reduzir o erro em `MIN_GAIN`, o modelo fica só com a tendência e a
    tela diz isso. Cada treino é guardado em `forecast_models`.
  - **Fine-tuning LoRA do modelo de linguagem** (`backend/app/finetune/` e `finetuning/`): ensina a escolher
    ferramentas, nunca números. A última redação de cada modelo de frase fica só na avaliação. Mudou uma
    ferramenta? Atualize os modelos de frase de `app/finetune/dataset.py` (o teste confere que os argumentos passam na
    validação da ferramenta).

## Regras gerais

- Tudo roda no Docker. Não exija Python nem Node instalados para executar ou testar.
- Interface, mensagens de erro e documentação em português do Brasil; nomes de classes, funções, variáveis e
  arquivos em inglês. As props do Kole são em português e ficam como estão.
- Nada de segredos no código, no compose ou na documentação. Configuração só por variável de ambiente.
- Mudou uma variável? Atualize `config.py`, `compose.yaml`, `.env.example` e a tabela do README juntos.
- Só a porta do frontend é publicada, em `127.0.0.1`. Ollama, PostgreSQL e backend não têm porta publicada no
  `compose.yaml` (a do backend existe só no `compose.dev.yaml`).
- GPU externa: toda pelo painel, nada no `.env`. O backend abre o túnel SSH (`services/gpu_tunnel.py`, asyncssh) com
  a chave que ele gera no volume `backend-ssh`: a chave privada nunca sai pela API, a senha do servidor (instalar a
  chave) nunca é guardada, e a chave do servidor é conferida depois da primeira conexão. A porta do túnel
  (`GPU_TUNNEL_PORT`) fica só na rede do Docker; nunca publique a porta do Ollama do servidor. Os dois Ollama ficam no
  ar e a página Modelo de IA (`/modelo-ia`, botão Configurar no card Serviços do Status) escolhe qual usar e o modelo de cada um (`services/model_selector.py`, guardado em
  `app_settings`). O fine-tuning remoto é o `finetuning/treinar_remoto.sh` (sem argumento, usa o servidor do painel).
- O backend só acessa os endereços de `ALLOWED_HOSTS` em `services/public_data.py` e, por SSH, o servidor da GPU
  externa cadastrado no painel.
- Nas fontes públicas, o backend usa HTTPS e só envia parâmetros de consulta (nomes de municípios, coordenadas,
  datas, códigos do IBGE).

## Backend

- Camadas: `api/` (rotas finas, sem regra de negócio) → `services/` (regras) → `repositories/` (SQL com parâmetros
  `%s`). Os objetos compartilhados são criados em `core/container.py`.
- Erros de negócio herdam de `AppError` (`core/errors.py`) e viram `{"erro": {"codigo", "mensagem"}}` com o código
  HTTP da classe. Mensagens para o usuário, em português e com a ação a tomar.
- Esquema do PostgreSQL idempotente em `repositories/database.py`, criado na inicialização. Banco vetorial = pgvector
  no próprio PostgreSQL (imagem `pgvector/pgvector`, `CREATE EXTENSION IF NOT EXISTS vector` no esquema): nada de
  Qdrant, ChromaDB ou outro serviço para vetores.
- Coletas (`services/collection_service.py`): uma por vez em cada fonte (trava por fonte; o botão recebe 409 se a
  fonte estiver coletando). Toda coleta grava o registro em `collection_runs` com origem (`agendada`, `botao`,
  `cadastro`), situação, registros e mensagem. Sem dado novo, a situação é `sem_novidade`, com a mensagem "Já está
  atualizado…". Coleta com dado novo chama `InsightService.refresh` (alertas e descobertas).
- Agendador (`services/scheduler.py`): decide pelo registro no banco (`is_due`), então reiniciar não repete coleta.
  Chuva todo dia a partir de `RAIN_COLLECT_HOUR`; produção e estimativa a partir de `MONTHLY_COLLECT_DAY`.
- Chat (`services/chat_service.py`) em Server-Sent Events: `conversation`, `thinking` (uma vez), `tool_call`,
  `tool_result`, `chart`, `token`, `discard`, `done` ou `error`. Qualquer evento novo precisa ser tratado também em
  `frontend/src/services/sse.ts`. A pergunta é gravada antes do streaming e a resposta no fim, com as ferramentas e
  os gráficos. O histórico enviado ao modelo vem do banco, nunca do navegador, com as chamadas e só o resumo dos
  resultados. A conversa precisa caber em `CHAT_NUM_CTX` (`_fit_context` encurta os resultados mais antigos): toda
  ferramenta nova devolve resultado enxuto, e comparação entre municípios é uma ferramenta só.
- Gráficos: o backend monta a especificação em `services/charts.py` com os nomes das props do Kole em snake_case;
  o frontend só converte para camelCase (`components/chartProps.ts`).
- Testes unitários usam os dublês de `tests/fakes.py` (fontes públicas, modelo, executor) e o serviço
  `postgres-test` (em memória, tabelas limpas antes de cada teste). Testes com as APIs e o modelo reais ficam em
  `tests/integration/` com `@pytest.mark.integration`.
- Antes de entregar: `docker compose --profile test run --rm --build backend-tests` (Ruff e pytest).

## Frontend

- Use os componentes reais do `@celke/kole-react` (veja o README do pacote e os tipos em
  `node_modules/@celke/kole-react/dist`). Não invente componentes nem props.
- O Kole vem do npm (`"@celke/kole-react": "^0.4.1"`, com os gráficos). Para atualizar: `npm i @celke/kole-react`
  pelo Docker e gere o `package-lock.json` de novo.
- Estilos próprios só em `src/styles.css`, com as variáveis do tema do Kole; nada de cor fixa.
- Ícones pelo nome: os que não vêm registrados no Kole são registrados em `src/main.tsx` com `registrarIcones`.
- Toda chamada à API passa por `src/services/api.ts`.
- Antes de entregar: `docker compose --profile test run --rm --build frontend-tests` (tsc e Vitest).

## Prompts do tutorial

`docs/prompts/` recria o projeto do zero. Mudou algo que um prompt cria? Atualize o prompt da etapa
correspondente no mesmo commit. Os prompts são escritos como originais: sem datas, sem histórico de correções e sem
caminhos de outros projetos.

`docs/prompts-iniciais/` é gerado: não edite à mão. O texto das orientações fica em
`docs/gerador-prompts/gerar_prompts.py`, e o conteúdo dos arquivos vem do próprio projeto. Mudou um arquivo? Gere
de novo no mesmo commit e confira (o segundo comando precisa terminar com `diferentes 0`):

```bash
docker run --rm -v "${PWD}:/repo" -w /repo python:3.13-slim python docs/gerador-prompts/gerar_prompts.py
docker run --rm -v "${PWD}:/repo" -w /repo python:3.13-slim python docs/gerador-prompts/testar_prompts.py
```
