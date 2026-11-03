"""Gera prompts-iniciais/ com o conteúdo atual dos arquivos do projeto. Ver "Prompts do tutorial" no CLAUDE.md."""
import os
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs" / "prompts-iniciais"
# Fora dos prompts: o que é gerado ou só existe neste computador.
SKIP_DIRS = {".git", ".claude", ".pytest_cache", ".ruff_cache", ".venv", "__pycache__", "node_modules", "dist",
             "prompts-iniciais", "cache"}
SKIP_FILES = {".env", ".DS_Store", "configuracao.md", "progresso.md"}
# Dataset e modelos do fine-tuning são gerados na execução; só as pastas vazias entram.
GENERATED = ("finetuning/data/", "finetuning/output/")
FENCE = "`" * 6
LANG = {".py": "python", ".ts": "ts", ".tsx": "tsx", ".css": "css", ".json": "json", ".yaml": "yaml", ".yml": "yaml",
        ".md": "markdown", ".sh": "sh", ".ps1": "powershell", ".html": "html", ".svg": "xml", ".toml": "toml",
        ".txt": "text", ".conf": "nginx"}


def project_files():
    found = []
    for folder, dirs, names in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for n in names:
            path = (Path(folder) / n).relative_to(REPO).as_posix()
            if n in SKIP_FILES or (path.startswith(GENERATED) and n != ".gitkeep"):
                continue
            found.append(path)
    return sorted(found)


FILES = project_files()


def content(path):
    text = (REPO / path).read_bytes().decode("utf-8").replace("\r\n", "\n")
    # Valores de quem gerou viram marcadores, trocados por quem recria.
    if path == "README.md":
        text = re.sub(r"git clone \S+ celke-treinar-ia-agro", "git clone <url-do-repositório> celke-treinar-ia-agro", text)
    if path == "LICENSE.txt":
        text = re.sub(r"Copyright \(c\) .*", "Copyright (c) <ano> <titular-da-licenca>", text, count=1)
    assert FENCE not in text, path
    return text


def block(path):
    name = Path(path).name
    lang = LANG.get(Path(path).suffix, "text")
    if name == "Dockerfile":
        lang = "dockerfile"
    elif name.startswith("."):
        lang = "text"
    return f"`{path}`:\n\n{FENCE}{lang}\n{content(path)}{'' if content(path).endswith(chr(10)) else chr(10)}{FENCE}\n"


def blocks(paths):
    empty = [p for p in paths if not content(p)]
    full = [p for p in paths if content(p)]
    text = "\n".join(block(p) for p in full)
    if empty:
        text += "\nCrie também estes arquivos **vazios**:\n\n" + "\n".join(f"- `{p}`" for p in empty) + "\n"
    return text


ROOT = [".gitignore", ".gitattributes", ".dockerignore", ".env.example", "compose.yaml", "compose.gpu.yaml",
        "compose.externo.yaml", "compose.dev.yaml", "scripts/iniciar.sh", "scripts/iniciar.ps1", "finetuning/data/.gitkeep",
        "finetuning/output/.gitkeep"]
BACKEND = [f for f in FILES if f.startswith("backend/")]
FRONTEND = [f for f in FILES if f.startswith("frontend/") and f != "frontend/package-lock.json"]
FINETUNE = [f for f in FILES if f.startswith("finetuning/") and f not in ROOT]
DOCS = ["README.md", "CLAUDE.md"] + [f for f in FILES if f.startswith("docs/")]
accounted = set(ROOT + BACKEND + FRONTEND + FINETUNE + DOCS + ["LICENSE.txt", "frontend/package-lock.json"])
assert set(FILES) == accounted, set(FILES) ^ accounted

RULES = """Regras desta etapa:

- Crie os arquivos com **exatamente** o conteúdo indicado, sem melhorar nem reformatar. O conteúdo já foi
  testado junto; uma alteração aqui quebra outra etapa.
- Não pergunte nada ao usuário: as decisões estão neste prompt e em `docs/configuracao.md`.
- Mostre ao usuário as seções **Orientação** (antes de começar e ao terminar), com as suas palavras só onde
  houver marcador a trocar. Se o terminal não permitir mostrar agora, inclua no seu relatório final.
- Rode tudo o que está em **Verificação** e corrija o que falhar antes de terminar.
- Nunca mostre o valor de `POSTGRES_PASSWORD`.
"""

F00 = f"""# Preparação do computador e escolha do modelo de IA

**Etapa:** 0 de 6
**Quem executa:** a sessão principal do agente, porque esta é a única etapa com pergunta ao usuário.

## Orientação antes de começar

> **O que vai acontecer agora:** vou conferir o seu computador e recomendar o modelo de IA.
> **O que você precisa fazer:** selecionar o modelo de IA e, se o Git ainda não estiver configurado, preencher nome e
> e-mail. O resto é automático.
> **Importante:** não instale o Ollama no computador. Ele roda dentro do Docker e é configurado pelo projeto.

## Prompt

Você vai preparar a criação do **Celke Treinar IA Agro**: IA local que coleta chuva (Open-Meteo) e produção de soja e
milho (IBGE), treina um modelo de previsão da safra e um fine-tuning LoRA do modelo de linguagem, e usa o Ollama com
ferramentas para responder, descobrir e avisar (React com `@celke/kole-react`, FastAPI, Ollama 0.40, PostgreSQL e
Docker Compose). Faça os passos na ordem. Só os passos 4 e 6 fazem pergunta.

### 1. Ferramentas

Confira `git --version`, `docker --version`, `docker compose version` e `docker info`. Se algo faltar, **pare**
e mostre só a orientação do caso. Depois de resolver, a pessoa executa o mesmo prompt de novo.

| Caso | Mostre ao usuário |
|---|---|
| Git ausente | "Instale o Git em https://git-scm.com/downloads, abra um terminal novo e execute este prompt de novo." |
| Docker ausente, Windows | "Instale o Docker Desktop em https://www.docker.com/products/docker-desktop/ e mantenha a opção WSL 2 marcada. Reinicie o computador se ele pedir, abra o Docker Desktop, espere aparecer *Engine running* e execute este prompt de novo." |
| Docker ausente, macOS | "Instale o Docker Desktop em https://www.docker.com/products/docker-desktop/, abra o programa, espere aparecer *Engine running* e execute este prompt de novo." |
| Docker ausente, Linux | "Instale o Docker Engine com o plugin Compose: https://docs.docker.com/engine/install/. Depois rode `sudo usermod -aG docker $USER`, entre de novo na sessão e execute este prompt de novo." |
| `docker info` falhou | "O Docker está instalado, mas não está rodando. Abra o Docker Desktop (no Linux, `sudo systemctl start docker`), espere iniciar e execute este prompt de novo." |

### 2. Projeto existente

Se a pasta atual já for um repositório com commits e não houver `progresso.md` na pasta de prompts, **pare**:
"Esta pasta já tem um projeto. Crie uma pasta vazia, coloque `prompts-iniciais` dentro dela e execute de novo."

Rode `docker ps -a --filter label=com.docker.compose.project=celke-treinar-ia-agro --format "{{{{.Names}}}}"` e
`docker volume ls --filter label=com.docker.compose.project=celke-treinar-ia-agro --format "{{{{.Name}}}}"`. Se
listarem algo, **pare**: nunca apague esses dados por conta própria. Mostre: "Este computador já tem uma
instalação do Celke Treinar IA Agro. Para substituí-la **apagando municípios, dados coletados e conversas**, rode, na
pasta dela, `docker compose down -v`. Depois execute este prompt de novo."

### 3. Capacidade do computador

Colete os dados sem perguntar nada:

- **Windows (PowerShell):** `(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB`,
  `(Get-CimInstance Win32_Processor).NumberOfLogicalProcessors` e o espaço livre do disco da pasta atual com
  `Get-PSDrive`.
- **Linux:** `free -g`, `nproc`, `df -BG .`.
- **macOS:** `sysctl -n hw.memsize hw.ncpu`, `df -g .`.
- **Memória e processadores que o Docker enxerga** (é o que vale): `docker info --format "{{{{.MemTotal}}}} {{{{.NCPU}}}}"`
  (`MemTotal` em bytes). No Windows com WSL 2, o padrão costuma ser metade da RAM.
- **GPU:** `nvidia-smi --query-gpu=name,memory.total --format=csv,noheader`. Só se responder, confirme que o
  Docker a alcança: `docker run --rm --gpus all --entrypoint nvidia-smi ollama/ollama:0.40.13 -L`.
  A GPU só conta se os dois funcionarem. AMD, Intel e Apple Silicon contam como **sem GPU**: este projeto só
  liga GPU NVIDIA, e o Docker no macOS não usa a GPU do Mac. O fine-tuning (etapa 4) também precisa da GPU NVIDIA.

### 4. Escolha do modelo

Modelos do Ollama, da família `qwen3`, todos com ferramentas (tool calling). Memória com a janela de contexto de 8192
tokens:

| Modelo | Download | Memória | Para quem | Medição de referência |
|---|---|---|---|---|
| `qwen3:1.7b` | 1,4 GB | cerca de 3 GB | Computador com pouca memória; erra muito a escolha das ferramentas | estimativa |
| `qwen3:4b` | 2,5 GB | 4,3 GB | Mais rápido; erra mais as ferramentas | RTX 3060 |
| `qwen3:8b` | 5,2 GB | 6,7 GB | Padrão do projeto; escolhe bem as ferramentas | CPU Ryzen 7 5700: 7,9 tokens/s, pergunta com ferramentas em cerca de 1 minuto; RTX 3060: 54 tokens/s |
| `qwen3:14b` | 9,3 GB | 10,4 GB | Melhor para gravar o tutorial; pede GPU de 12 GB | RTX 3060: 31 tokens/s |
| `qwen3:30b` | 18,6 GB | cerca de 20 GB | Máximo desta lista; pede GPU de 24 GB | estimativa |

**Modelo recomendado.** Use a primeira linha que couber, de cima para baixo:

| Situação | Recomendado |
|---|---|
| GPU com 24 GB ou mais | `qwen3:30b` |
| GPU com 12 GB ou mais | `qwen3:14b` |
| GPU com 6 GB ou mais | `qwen3:8b` |
| Sem GPU, Docker com 12 GB ou mais | `qwen3:8b` |
| Sem GPU, Docker com 6,5 GB ou mais | `qwen3:4b` |
| Qualquer outro caso | `qwen3:1.7b` |

Depois, confira o disco: o espaço livre precisa ser de pelo menos 10 GB mais o download do modelo (e mais 25 GB se
houver GPU NVIDIA, para o fine-tuning). Se não for, desça para o maior modelo que couber. Se nem o `qwen3:1.7b`
couber, **pare** e diga quantos GB a pessoa precisa liberar.

**Pergunta.** Mostre os dados encontrados e faça **uma única pergunta**, com a ferramenta de pergunta se houver, para a
pessoa selecionar uma opção ou preencher o nome de outro modelo. Espere a resposta. Ofereça sempre três opções: a
**recomendada** (primeira, marcada como recomendada), a imediatamente **inferior** e a imediatamente **superior**. Nos
extremos da tabela, complete com a vizinha seguinte. Na opção superior, diga o risco quando a memória não for
suficiente: "pode ficar muito lento ou não carregar". Modelo:

> **Seu computador:** <RAM> GB de RAM, <memória do Docker> GB para o Docker, <processadores> processadores,
> <GPU e memória, ou "sem GPU NVIDIA">, <espaço livre> GB livres.
>
> **Qual modelo de IA você quer usar?** Ele pode ser trocado depois.
> 1. `<recomendado>` (**recomendado**): <motivo em uma frase, com a memória que ele usa> Download de <tamanho>.
> 2. `<inferior>`: mais leve e rápido, erra mais a escolha das ferramentas. Download de <tamanho>.
> 3. `<superior>`: respostas melhores. <risco, se houver> Download de <tamanho>.
>
> Responda 1, 2 ou 3 (ou o nome de outro modelo do Ollama com ferramentas). Sem preferência? Escolha a 1.

Se a pessoa informar outro modelo, aceite e avise que ele precisa ter a etiqueta *tools* no Ollama e não foi testado
com o projeto.

Se o recomendado for `qwen3:4b` ou `qwen3:1.7b`, acrescente depois das opções, sem transformar em opção: "Sem GPU
boa, o chat pode rodar depois numa GPU externa alugada por hora (por exemplo, a GPU hosting da Hostinger, a partir
de cerca de R$ 2,31/h): o projeto já vem pronto para isso, veja 'GPU externa' no README ao final." A instalação
continua com o modelo local escolhido.

Se a memória do Docker no Windows for menor que a necessária e a RAM do computador comportar o modelo, acrescente
esta orientação, sem alterar nada por conta própria: "Para dar mais memória ao Docker, crie
`%UserProfile%\\.wslconfig` com as linhas `[wsl2]` e `memory=12GB`, rode `wsl --shutdown` e abra o Docker Desktop."

### 5. Decisões automáticas (não pergunte)

- **GPU:** ligada se o passo 3 confirmou a GPU.
- **Fine-tuning (onde treinar o LoRA):**

  | Situação | Decisão |
  |---|---|
  | GPU NVIDIA com 12 GB ou mais | Neste computador, base `unsloth/Qwen3-8B` |
  | GPU NVIDIA com 8 GB ou mais | Neste computador, base `unsloth/Qwen3-4B` (o modelo treinado parte do `qwen3:4b`) |
  | Qualquer outro caso | **GPU externa** (`./finetuning/treinar_remoto.sh`, veja "GPU externa" no README) ou pular: a etapa 4 prepara o dataset e mede o modelo atual, e o treino fica como pendência |

  O treino da previsão da safra não precisa de GPU: roda sempre aqui, em segundos.
- **Porta:** `8091`. Se estiver ocupada, use a primeira livre de `8092` a `8099`.
- **Git:** se a pasta não for um repositório, `git init -b main`. Acrescente `/<pasta de prompts>/` em
  `.git/info/exclude`.
- **Licença:** MIT, com `git config user.name` como titular e o ano atual.

### 6. Nome e e-mail do Git

Confira `git config user.name` e `git config user.email`. Se os dois tiverem valor, não pergunte nada. Se faltar algum,
faça a pergunta abaixo, com a ferramenta de pergunta se houver, pedindo só o que falta, e espere a resposta:

> **Qual nome e e-mail devem aparecer nos commits deste projeto?** O nome também vai na licença. Preencha:
>
> - **Nome:**
> - **E-mail:**

Se o e-mail vier sem `@`, peça de novo. Grave com `git config user.name` e `git config user.email`, só neste repositório.

### 7. Arquivos

Crie o `.env` (UTF-8 sem BOM, com a sua ferramenta de escrita de arquivos), com uma chave aleatória de 48 caracteres
hexadecimais. Gere com `od -An -N24 -tx1 /dev/urandom | tr -d ' \\n'` (Linux, macOS, Git Bash) ou
`$b = New-Object byte[] 24; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); -join ($b | ForEach-Object {{ $_.ToString('x2') }})`
(PowerShell):

```dotenv
POSTGRES_PASSWORD=<chave>
CHAT_MODEL=<modelo escolhido>
```

Se a porta não for `8091`, acrescente `APP_PORT=<porta>`. Com GPU, acrescente `COMPOSE_FILE=compose.yaml;compose.gpu.yaml` no
Windows ou `COMPOSE_FILE=compose.yaml:compose.gpu.yaml` no Linux. Com GPU de 8 GB a menos de 12 GB, acrescente
`FINETUNE_BASE_MODEL=unsloth/Qwen3-4B`.

Crie `docs/configuracao.md`, trocando os valores:

`````markdown
# Configuração deste computador

Decisões tomadas ao criar o projeto. Os segredos ficam só no `.env`.

| Item | Valor |
|---|---|
| Modelo de chat | <modelo> |
| GPU NVIDIA | <nome e memória, ou "não usada"> |
| Fine-tuning (LoRA) | <"neste computador, base unsloth/Qwen3-8B", "neste computador, base unsloth/Qwen3-4B" ou "GPU externa recomendada (treinar_remoto.sh) ou pendente"> |
| Memória para o Docker | <memória> GB |
| Endereço | http://localhost:<porta> |
`````

Crie o `LICENSE.txt`, trocando `<ano>` e `<titular-da-licenca>`:

{blocks(["LICENSE.txt"])}
## Verificação

- O `.env` tem as variáveis (confira sem mostrar o valor da chave).
- `docs/configuracao.md` e `LICENSE.txt` existem, sem marcadores por trocar.

## Depois de executar

Nesta etapa não há commit: o `.gitignore` é criado na próxima.

## Orientação ao terminar

> **Pronto:** escolhido o modelo `<modelo>`. Daqui em diante é automático. **Você não precisa fazer nada**, só deixar o
> Docker aberto e o computador ligado, com internet. O próximo passo baixa imagens e o modelo.
"""

F01 = f"""# Estrutura inicial e serviços de IA no Docker

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

{RULES}
Depois, deixe `scripts/iniciar.sh` executável: `chmod +x scripts/iniciar.sh`.

{blocks(ROOT)}
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
"""

F02 = f"""# Backend: dados, previsão treinada e IA com ferramentas

**Etapa:** 2 de 6
**Requer:** etapa 1

## Orientação antes de começar

> **O que vai acontecer agora:** vou criar a API em Python que coleta a chuva e a produção, treina o modelo de
> previsão da safra e conversa com o modelo de IA usando ferramentas. Leva alguns minutos, e os testes rodam no
> Docker. **O que você precisa fazer:** nada.

## Prompt

Crie o backend do **Celke Treinar IA Agro** em FastAPI: clientes do Open-Meteo e do IBGE com lista fixa de endereços,
cadastro de municípios, coletas com registro (uma por vez em cada fonte), agendador, análises de chuva × rendimento,
modelo de previsão treinado e validado deixando uma safra de fora, chat com 10 ferramentas (streaming em Server-Sent
Events), descobertas com filtro estatístico, alertas da safra e o dataset e a avaliação do fine-tuning
(`python -m app.finetune`). Os testes usam dublês: sem internet e sem Ollama.

{RULES}
{blocks(BACKEND)}
## Verificação

```bash
docker compose --profile test run --rm --build backend-tests
docker compose --profile test rm -fs postgres-test
```

Precisa terminar com Ruff sem erros e todos os testes passando (1 desmarcado: o de integração, da etapa 5).

## Depois de executar

```bash
git add backend
git commit -m "feat: cria o backend com coletas, previsão treinada e IA com ferramentas"
```

## Orientação ao terminar

> **Pronto:** o backend está criado e os testes passaram. Continue sem fazer nada.
"""

F03 = f"""# Frontend React com o Kole

**Etapa:** 3 de 6
**Requer:** etapa 2

## Orientação antes de começar

> **O que vai acontecer agora:** vou criar as telas de Análises, Previsão, Chat, Descobertas, Alertas, Municípios e
> Status com o layout `@celke/kole-react`. **O que você precisa fazer:** nada. Ao final, a aplicação já abre no navegador.

## Prompt

Crie o frontend do **Celke Treinar IA Agro** em React, TypeScript e Vite, com o `@celke/kole-react` (com os gráficos,
instalado do GitHub na tag `v0.4.0`) e nginx com proxy da API.

{RULES}
{blocks(FRONTEND)}
Por último, gere o `frontend/package-lock.json` sem exigir Node no computador. Rode na raiz do projeto, trocando
`<pasta frontend absoluta>` pelo caminho real (no Git Bash do Windows, prefixe o comando com `MSYS_NO_PATHCONV=1`):

```bash
docker run --rm -v "<pasta frontend absoluta>:/app" -w /app node:24-alpine sh -c "apk add --no-cache git > /dev/null && npm install --package-lock-only --no-audit --no-fund"
```

## Verificação

```bash
docker compose --profile test run --rm --build frontend-tests
./scripts/iniciar.sh                                        # no Windows: powershell -ExecutionPolicy Bypass -File scripts\\iniciar.ps1
docker compose ps                                           # todos healthy; só o frontend com porta
curl -s http://localhost:<porta>/api/status                 # backend, ollama e banco online; modelo com ferramentas
curl -s -o /dev/null -w "%{{http_code}}\\n" http://localhost:<porta>/previsao   # 200
```

Use a porta de `docs/configuracao.md`. No Windows PowerShell, escreva `curl.exe`.

## Depois de executar

```bash
git add frontend
git commit -m "feat: cria o frontend com análises, previsão, chat, descobertas e alertas"
```

## Orientação ao terminar

> **Pronto:** a aplicação já abre em http://localhost:<porta>, mas ainda vou testar tudo. Continue sem fazer nada.
"""

F04 = f"""# Fine-tuning do modelo de linguagem

**Etapa:** 4 de 6
**Requer:** etapa 3

## Orientação antes de começar

> **O que vai acontecer agora:** vou preparar o fine-tuning: o treino LoRA que ensina o modelo de IA a escolher as
> ferramentas certas. Com GPU NVIDIA, eu meço o acerto do modelo, treino e meço de novo. Sem GPU, eu preparo e meço o
> modelo atual, e o treino fica para um computador com GPU. **O que você precisa fazer:** nada.

## Prompt

Crie a pasta `finetuning/` do **Celke Treinar IA Agro**: container de treino com o Unsloth (versões fixas), o script de
treino e o script que cria o modelo treinado no Ollama. O dataset e a avaliação já estão no backend
(`python -m app.finetune`).

{RULES}
Depois, deixe os scripts executáveis: `chmod +x finetuning/criar_modelo.sh finetuning/treinar_remoto.sh`.

{blocks(FINETUNE)}
## Verificação

1. Cadastre Rio Verde (GO) e espere a coleta terminar (cerca de 1 minuto):
   ```bash
   curl -s -X POST http://localhost:<porta>/api/municipalities -H "Content-Type: application/json" -d '{{"code":5218805}}'
   curl -s http://localhost:<porta>/api/municipalities/5218805      # repita até "status": "pronto"
   ```
2. Gere o dataset e meça o modelo atual (o "antes"; na CPU, cerca de 10 minutos):
   ```bash
   docker compose --profile finetune run --rm --build finetune-tools exportar
   docker compose --profile finetune run --rm finetune-tools avaliar --modelo <modelo de docs/configuracao.md>
   ```
3. **Só com GPU NVIDIA**, treine, crie o modelo e meça de novo (o "depois"):
   ```bash
   docker compose --profile finetune run --rm --build finetune-train
   docker compose exec ollama sh /finetuning/criar_modelo.sh <modelo de docs/configuracao.md> celke-agro
   docker compose --profile finetune run --rm finetune-tools avaliar --modelo celke-agro
   ```
   Sem GPU local, registre "treino LoRA pendente: rodar numa GPU externa com ./finetuning/treinar_remoto.sh
   usuario@ip (README, GPU externa)" no relatório e siga.

Mostre ao usuário os percentuais de acerto de antes e de depois.

## Depois de executar

```bash
git add finetuning
git update-index --chmod=+x finetuning/criar_modelo.sh finetuning/treinar_remoto.sh
git commit -m "feat: adiciona o fine-tuning LoRA do modelo de linguagem"
```

## Orientação ao terminar

> **Pronto:** o fine-tuning está preparado. <Com GPU: "O modelo treinado `celke-agro` acertou <depois>% das perguntas
> novas, contra <antes>% do modelo original."> <Sem GPU: "O modelo atual acertou <antes>% das perguntas novas. Para
> treinar, alugue uma GPU por hora (por exemplo, na Hostinger) e rode `./finetuning/treinar_remoto.sh root@<ip>`:
> veja 'GPU externa' no README."> Continue sem fazer nada.
"""

F05 = """# Integração ponta a ponta

**Etapa:** 5 de 6
**Requer:** etapa 4

## Orientação antes de começar

> **O que vai acontecer agora:** vou testar o fluxo completo com os dados públicos e o modelo real: coletar,
> analisar, treinar a previsão, perguntar no chat, reiniciar e ver se os dados continuam. **O que você precisa
> fazer:** nada.

## Prompt

Teste o **Celke Treinar IA Agro** como um usuário faria. Não há arquivos novos. Use os scripts criados na etapa 1, e no
Windows o `iniciar.ps1`. Se algo falhar, corrija a causa, repita a verificação e relate o que mudou.
Não apague nada além do que você mesmo criar neste teste.

## Verificação

1. Duas vezes, para confirmar que a segunda não baixa nada: `./scripts/iniciar.sh` ou
   `powershell -ExecutionPolicy Bypass -File scripts\\iniciar.ps1`. Termina com "Pronto! Abra http://localhost:<porta>".
2. `docker compose --profile test run --rm --build backend-tests pytest -m integration -v` (1 passou) e
   `docker compose --profile test rm -fs postgres-test`.
3. `GET /api/collections`: coletas de chuva, produção e estimativa com origem `cadastro`. `POST /api/collections/producao`
   duas vezes seguidas: 202 e depois 409; ao terminar, a mensagem "Já está atualizado…".
4. `GET /api/forecasts/5218805/milho`: há treino, com o erro do modelo e o da tendência. `POST /api/forecasts/train` e,
   depois de alguns segundos, o histórico tem um treino a mais, com origem `botao`.
5. Pergunte no chat (use `curl.exe`, `-N` e o JSON em arquivo no Windows):
   ```bash
   curl -N -X POST http://localhost:<porta>/api/chat -H "Content-Type: application/json" -d '{"question":"A chuva de abril influencia o rendimento do milho em Rio Verde?"}'
   ```
   Confira o evento `tool_call` com `correlacao_chuva_rendimento`, `"variavel": "chuva_do_mes"` e `"mes": 4`, e a
   resposta com r e a fonte, sem raciocínio na tela.
6. Persistência: `docker compose down` (**sem** `-v`), rode o script de novo e confira que `/api/municipalities`,
   `/api/collections`, `/api/forecasts/5218805/milho` e `/api/conversations` continuam com os dados.
7. Exclua, pelo id, as conversas criadas neste teste.

## Depois de executar

Só há commit se algo foi corrigido, com a mensagem `fix: <o que foi corrigido>`.

## Orientação ao terminar

> **Pronto:** o fluxo completo foi testado com os dados públicos e o modelo real. Falta só a documentação. Continue sem
> fazer nada.
"""

F06 = f"""# Documentação e entrega

**Etapa:** 6 de 6
**Requer:** etapa 5

## Orientação antes de começar

> **O que vai acontecer agora:** vou criar o README e o guia para agentes de IA e fazer a entrega final.
> **O que você precisa fazer:** nada por enquanto. No final, mostro como testar no navegador.

## Prompt

Crie a documentação do **Celke Treinar IA Agro**, deixe os prompts no projeto e crie a branch de homologação. Os
arquivos de `docs/prompts` são as mesmas etapas em texto, para o tutorial, e `docs/gerador-prompts` mantém estes
prompts atualizados: crie-os como estão, sem executá-los.

{RULES}
Troque `<url-do-repositório>` no `README.md` pela URL do `origin`, se houver. Sem `origin`, mantenha o marcador.

{blocks(DOCS)}
Por fim, se a pasta de prompts não for `docs/prompts-iniciais/`, copie-a para lá, sem o `progresso.md`. Se esse caminho
estiver em `.git/info/exclude`, troque a linha por `/docs/prompts-iniciais/progresso.md`.

## Verificação

```bash
docker compose config -q && echo ok
docker compose ps
git status --short    # .env não aparece
```

Confira que os links internos do README existem (`.env.example`, `LICENSE.txt`, `docs/prompts-iniciais/README.md`,
`docs/prompts/README.md`).

## Depois de executar

```bash
git add README.md CLAUDE.md docs
git commit -m "docs: adiciona o README, o guia para agentes e os prompts"
git branch homolog
```

Mensagens sem `Co-Authored-By` nem menção a ferramenta de IA. Não faça push.

## Orientação ao terminar

Mostre, trocando os marcadores:

> **O Celke Treinar IA Agro está pronto em http://localhost:<porta>** com o modelo `<modelo>`.
>
> **Agora é com você, no navegador:**
> 1. Em **Status e coletas**, confira se tudo está verde.
> 2. Em **Municípios**, cadastre outro município: a chuva e a produção são baixadas em cerca de 1 minuto.
> 3. Em **Previsão (treino)**, veja o modelo treinado com as safras: as variáveis escolhidas, o erro medido e a
>    previsão da próxima safra.
> 4. Em **Chat**, pergunte, por exemplo, "A chuva de abril influencia o rendimento do milho em Rio Verde?". A primeira
>    resposta demora mais, porque o modelo é carregado.
> 5. Em **Descobertas** e **Alertas**, veja o que a IA encontrou e o que ela avisa sobre a safra em andamento.
>
> **Comandos úteis:** parar com `docker compose stop`; voltar com `docker compose start`; apagar tudo, inclusive dados e
> modelos, com `docker compose down -v`.
>
> **Fine-tuning:** os comandos estão no README, em "Fine-tuning do modelo de linguagem (GPU)". Sem GPU boa, use uma
> GPU externa alugada por hora, para o chat e para o treino: veja "GPU externa (Hostinger e similares)".
>
> **Enviar ao GitHub (opcional):** crie um repositório vazio e rode `git remote add origin <url>` e
> `git push -u origin main homolog`.
"""

README = """# Prompts iniciais

Prompts para criar o **Celke Treinar IA Agro** do zero com um agente de IA com acesso ao terminal (Claude Code ou
similar): IA local que coleta chuva e produção de soja e milho de fontes públicas, treina um modelo de previsão da
safra e um fine-tuning LoRA do modelo de linguagem, com backend Python, frontend React com o layout
`@celke/kole-react` e Docker.

**Esta pasta basta sozinha.** Você não precisa de nenhum outro arquivo do projeto: os prompts trazem o código, o README, a
licença, o guia para agentes, os scripts e a configuração do Docker. O `package-lock.json` e os segredos do `.env` são gerados
durante a execução.

## O que você precisa antes

| O quê | Observação |
|---|---|
| Claude Code (ou agente similar) | Com acesso ao terminal |
| Docker Desktop (Windows, macOS) ou Docker Engine (Linux) | Se faltar, o prompt mostra como instalar |
| Git | Se faltar, o prompt mostra como instalar |
| Internet | Para baixar imagens, o modelo e os dados públicos |
| Disco | Cerca de 10 GB mais o modelo (mais 25 GB para o fine-tuning, com GPU) |
| GPU NVIDIA (opcional) | Acelera o chat e é necessária para o treino LoRA; sem ela, dá para alugar uma por hora (GPU externa) |

**Não instale o Ollama, o Python nem o Node.** Tudo roda no Docker.

## Como usar

1. Crie uma pasta vazia para o projeto, em qualquer lugar, e copie só esta pasta `prompts-iniciais` para dentro dela.
2. Abra o Docker e espere ele iniciar.
3. Abra o Claude Code na pasta do projeto e execute:

   ```text
   Execute o prompt prompts-iniciais/prompt-para-replicar-projeto.md
   ```

4. Selecione o modelo de IA na pergunta e, se o Git não estiver configurado, preencha nome e e-mail. O prompt confere a
   memória, a GPU e o disco do seu computador e recomenda um modelo, com outras opções, inferior e superior.
5. Espere. O agente avisa o que está fazendo e o que você precisa fazer. No fim, ele mostra como testar no navegador.

Se parar no meio, execute o mesmo comando numa sessão nova: o andamento fica em `prompts-iniciais/progresso.md`.

Para gravar o tutorial etapa por etapa, execute os prompts da tabela um a um, cada um numa sessão nova, seguindo a
**Verificação** e o **Depois de executar** de cada um. Cada etapa precisa da anterior concluída.

| Ordem | Prompt | Resultado |
|---|---|---|
| 0 | [Preparação e escolha do modelo](f00-01-preparacao-e-modelo.md) | Computador conferido, modelo escolhido, `.env` e licença |
| 1 | [Estrutura inicial e Docker](f01-01-estrutura-e-docker.md) | Compose, scripts, Ollama, PostgreSQL e modelo baixado |
| 2 | [Backend](f02-01-backend.md) | Coletas, agendador, análises, previsão treinada, chat com ferramentas, descobertas, alertas e testes |
| 3 | [Frontend React com o Kole](f03-01-frontend-kole.md) | Análises, Previsão, Chat, Descobertas, Alertas, Municípios e Status |
| 4 | [Fine-tuning do modelo de linguagem](f04-01-fine-tuning.md) | Dataset, avaliação antes e depois e treino LoRA (na GPU) |
| 5 | [Integração ponta a ponta](f05-01-integracao.md) | Fluxo completo com os dados públicos e o modelo real, persistência |
| 6 | [Documentação e entrega](f06-01-documentacao.md) | README, guia para agentes, prompts em `docs/` e commit final |

## O que já está decidido

Para você ter o mínimo de perguntas, os prompts já decidem: tecnologias e versões, porta (`8091` ou a próxima livre), uso da
GPU NVIDIA quando disponível, licença MIT com o seu nome do Git, senha aleatória e commits locais.
Você só responde: **qual modelo de IA usar** (selecionando uma opção) e, se o Git ainda não estiver configurado, **o seu nome
e e-mail** (preenchendo os campos).
"""

REPLICAR = """# Prompt para replicar o projeto

Cria o Celke Treinar IA Agro completo numa execução só: a sessão do agente coordena, e cada etapa da tabela do
[README](README.md) é executada com contexto limpo.

## Antes de executar

Uma pasta vazia para o projeto, com `prompts-iniciais` dentro dela, e o Docker aberto. Na pasta do projeto, digite:

```text
Execute o prompt prompts-iniciais/prompt-para-replicar-projeto.md
```

## Prompt

Você vai construir o **Celke Treinar IA Agro** executando, **na ordem**, as etapas da tabela do `README.md` da pasta de
prompts. Execute tudo automaticamente. Só pare nos casos de **Quando parar**. A pessoa pode não ser técnica: em toda
mensagem, deixe claro o que está acontecendo e **o que ela precisa fazer** (muitas vezes, nada).

Nomes usados abaixo:

- **raiz**: o diretório atual, onde o projeto é criado.
- **pasta de prompts**: a pasta que contém este arquivo. Use caminhos relativos à raiz.

### Ao começar

1. Leia `progresso.md` na pasta de prompts. Se existir, diga de qual etapa vai continuar e pule as concluídas.
2. Mostre ao usuário:
   > **Vou criar o Celke Treinar IA Agro no seu computador.** São 7 etapas, e a mais demorada é o download do modelo de IA.
   > **O que você precisa fazer:** logo no início, selecionar o modelo e, se for preciso, preencher nome e e-mail do Git.
   > Depois, só deixar o Docker aberto.
   > Avisarei sempre que precisar de você. Se parar no meio, é só executar este prompt de novo.

### Etapas

1. **Etapa 0:** execute `f00-01-preparacao-e-modelo.md` você mesmo, nesta sessão, porque ela conversa com o usuário.
2. **Etapas 1 a 6:** para cada uma, nesta ordem:
   1. Mostre ao usuário a seção **Orientação antes de começar**, trocando os marcadores pelos valores de
      `docs/configuracao.md`.
   2. Dispare um subagente, em sequência e nunca em paralelo, com esta instrução. Sem subagentes disponíveis, execute você
      mesmo:
      > Leia `<pasta de prompts>/<arquivo>.md` e execute a seção `## Prompt` exatamente como está escrita, na raiz deste
      > repositório. Crie os arquivos com **exatamente** o conteúdo indicado. Rode a seção `## Verificação` e corrija o que
      > falhar. Não faça commit. Você não consegue falar com o usuário: não faça perguntas; a sua resposta final vai para o
      > coordenador. Responda com: arquivos criados, resultado de cada verificação, pendências e qualquer desvio do prompt.
   3. Leia o relatório e rode de novo os comandos principais da **Verificação**. Se algo falhar, mande corrigir e verifique de
      novo, em até três tentativas.
   4. Execute a seção `## Depois de executar`, sem `Co-Authored-By` nem menção a ferramenta de IA nas mensagens.
   5. Registre em `progresso.md`: etapa, arquivo, commit, `concluída` e pendências.
   6. Mostre ao usuário a seção **Orientação ao terminar**.

Se uma etapa levar muito tempo, como no download do modelo, avise o usuário de tempos em tempos, com o que está em andamento.

### Quando parar

- A etapa 0 pediu, ou falta a resposta das perguntas dela.
- Uma verificação falhou três vezes seguidas.
- O Docker parou de responder, acabou o espaço em disco ou caiu a internet.

Ao parar, diga em linguagem simples o que aconteceu, **o que a pessoa precisa fazer** e que depois basta executar este prompt de
novo. Não invente valores nem apague volumes ou dados que já existiam. O treino LoRA sem GPU NVIDIA não é motivo para parar:
é uma pendência registrada.

### Regras

- Não pule etapas nem "melhore" os arquivos: o conteúdo já foi testado junto.
- Nunca mostre a chave do `.env`.
- Não faça push.
- No fim, mostre a **Orientação ao terminar** da etapa 6 e as pendências do `progresso.md`.
"""

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in {
        "README.md": README,
        "prompt-para-replicar-projeto.md": REPLICAR,
        "f00-01-preparacao-e-modelo.md": F00,
        "f01-01-estrutura-e-docker.md": F01,
        "f02-01-backend.md": F02,
        "f03-01-frontend-kole.md": F03,
        "f04-01-fine-tuning.md": F04,
        "f05-01-integracao.md": F05,
        "f06-01-documentacao.md": F06,
    }.items():
        (OUT / name).write_text(text, encoding="utf-8", newline="\n")
        print(name, len(text.encode()))
