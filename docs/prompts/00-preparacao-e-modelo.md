# Etapa 0 — Preparação do computador e escolha do modelo de IA

## Contexto

Antes de criar o projeto, confira o computador e escolha o modelo de IA que cabe nele. Esta é a única etapa com
pergunta ao usuário: execute-a na sessão principal do agente. Não instale o Ollama no computador: ele roda no Docker.

## 1. Ferramentas

Confira `git --version`, `docker --version`, `docker compose version` e `docker info`. Se algo faltar, pare e diga
como instalar (Docker Desktop com WSL 2 no Windows e no macOS; Docker Engine com o plugin Compose no Linux).

## 2. Capacidade do computador

Sem perguntar nada: RAM, processadores e disco livre da pasta (`free -g`, `nproc` e `df -BG .` no Linux;
`Get-CimInstance` e `Get-PSDrive` no Windows; `sysctl` e `df -g` no macOS); a memória e os processadores que o Docker
enxerga (`docker info --format "{{.MemTotal}} {{.NCPU}}"`), que é o que vale; a GPU
(`nvidia-smi --query-gpu=name,memory.total --format=csv,noheader`) e se o Docker a alcança
(`docker run --rm --gpus all --entrypoint nvidia-smi ollama/ollama:0.40.13 -L`). AMD, Intel e Apple Silicon contam
como sem GPU: o projeto só liga GPU NVIDIA.

## 3. Modelo do chat

Modelos do Ollama da família `qwen3`, todos com ferramentas (tool calling). Use a primeira linha que couber:

| Situação | Recomendado | Referência |
|---|---|---|
| GPU com 24 GB ou mais | `qwen3:30b` | estimativa |
| GPU com 12 GB ou mais | `qwen3:14b` | RTX 3060: 31 tokens/s |
| GPU com 6 GB ou mais | `qwen3:8b` | RTX 3060: 54 tokens/s |
| Sem GPU, Docker com 12 GB ou mais | `qwen3:8b` | Ryzen 7 5700: 7,9 tokens/s, pergunta com ferramentas em cerca de 1 minuto |
| Sem GPU, Docker com 6,5 GB ou mais | `qwen3:4b` | erra mais a escolha das ferramentas |
| Qualquer outro caso | `qwen3:1.7b` | erra muito a escolha das ferramentas |

Confira o disco: pelo menos 10 GB mais o download do modelo (e mais 25 GB com GPU NVIDIA, para o fine-tuning).
Pergunte uma vez, com três opções: a recomendada, a inferior e a superior (com o risco, se a memória não bastar).
Se o recomendado for `qwen3:4b` ou menor, avise que o chat pode rodar depois numa **GPU externa** alugada por hora
(por exemplo, a GPU hosting da Hostinger): o projeto já vem pronto para isso.

## 4. Onde treinar (decisão automática)

| Situação | Fine-tuning LoRA |
|---|---|
| GPU NVIDIA com 12 GB ou mais | Neste computador, base `unsloth/Qwen3-8B` |
| GPU NVIDIA com 8 GB ou mais | Neste computador, base `unsloth/Qwen3-4B` (`FINETUNE_BASE_MODEL` no `.env`) |
| Qualquer outro caso | GPU externa (`./finetuning/treinar_remoto.sh`) ou pendente |

O modelo de previsão da safra não precisa de GPU: treina aqui, em segundos.

## 5. Arquivos

- `.env` com `POSTGRES_PASSWORD` (48 caracteres hexadecimais aleatórios) e `CHAT_MODEL`; `APP_PORT` se a 8091 estiver
  ocupada; `COMPOSE_FILE` com o `compose.gpu.yaml` se houver GPU; `FINETUNE_BASE_MODEL` se for o 4B.
- `docs/configuracao.md` com o modelo, a GPU, onde treinar, a memória do Docker e o endereço.
- `LICENSE.txt` MIT com o nome do Git e o ano. Se nome ou e-mail do Git faltarem, pergunte.
- Se a pasta não for um repositório, `git init -b main`.

## Verificação

O `.env` tem as variáveis (sem mostrar a senha), e `docs/configuracao.md` e `LICENSE.txt` existem sem marcadores.
