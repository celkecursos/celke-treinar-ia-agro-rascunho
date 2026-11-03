# Preparação do computador e escolha do modelo de IA

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

Rode `docker ps -a --filter label=com.docker.compose.project=celke-treinar-ia-agro --format "{{.Names}}"` e
`docker volume ls --filter label=com.docker.compose.project=celke-treinar-ia-agro --format "{{.Name}}"`. Se
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
- **Memória e processadores que o Docker enxerga** (é o que vale): `docker info --format "{{.MemTotal}} {{.NCPU}}"`
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

Se a memória do Docker no Windows for menor que a necessária e a RAM do computador comportar o modelo, acrescente
esta orientação, sem alterar nada por conta própria: "Para dar mais memória ao Docker, crie
`%UserProfile%\.wslconfig` com as linhas `[wsl2]` e `memory=12GB`, rode `wsl --shutdown` e abra o Docker Desktop."

### 5. Decisões automáticas (não pergunte)

- **GPU:** ligada se o passo 3 confirmou a GPU.
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
hexadecimais. Gere com `od -An -N24 -tx1 /dev/urandom | tr -d ' \n'` (Linux, macOS, Git Bash) ou
`$b = New-Object byte[] 24; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); -join ($b | ForEach-Object { $_.ToString('x2') })`
(PowerShell):

```dotenv
POSTGRES_PASSWORD=<chave>
CHAT_MODEL=<modelo escolhido>
```

Se a porta não for `8091`, acrescente `APP_PORT=<porta>`. Com GPU, acrescente `COMPOSE_FILE=compose.yaml;compose.gpu.yaml` no
Windows ou `COMPOSE_FILE=compose.yaml:compose.gpu.yaml` no Linux. Com GPU de menos de 12 GB, acrescente
`FINETUNE_BASE_MODEL=unsloth/Qwen3-4B`.

Crie `docs/configuracao.md`, trocando os valores:

`````markdown
# Configuração deste computador

Decisões tomadas ao criar o projeto. Os segredos ficam só no `.env`.

| Item | Valor |
|---|---|
| Modelo de chat | <modelo> |
| GPU NVIDIA | <nome e memória, ou "não usada"> |
| Fine-tuning | <"na GPU" ou "sem GPU: pula o treino"> |
| Memória para o Docker | <memória> GB |
| Endereço | http://localhost:<porta> |
`````

Crie o `LICENSE.txt`, trocando `<ano>` e `<titular-da-licenca>`:

`LICENSE.txt`:

``````text
Copyright (c) <ano> <titular-da-licenca>

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
``````

## Verificação

- O `.env` tem as variáveis (confira sem mostrar o valor da chave).
- `docs/configuracao.md` e `LICENSE.txt` existem, sem marcadores por trocar.

## Depois de executar

Nesta etapa não há commit: o `.gitignore` é criado na próxima.

## Orientação ao terminar

> **Pronto:** escolhido o modelo `<modelo>`. Daqui em diante é automático. **Você não precisa fazer nada**, só deixar o
> Docker aberto e o computador ligado, com internet. O próximo passo baixa imagens e o modelo.
