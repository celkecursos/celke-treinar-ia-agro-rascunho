# Etapa 6 — Fine-tuning do modelo de linguagem

## Contexto

O chat já funciona com o modelo base (etapa 4). Nesta etapa o modelo de linguagem é **treinado de verdade** com LoRA:
aprende a escolher a ferramenta certa e preencher os argumentos certos para as perguntas do agro ("safra 2023/24" é
`ano=2024`, "safrinha" é milho, "seca no meio da safra" é veranico). O fine-tuning ensina **comportamento**, nunca
números: os números continuam vindo das ferramentas.

O treino roda na GPU NVIDIA (pensado para uma RTX 3060 de 12 GB). O dataset e a avaliação rodam em qualquer
computador, inclusive na CPU.

## Dataset (`backend/app/finetune/dataset.py`)

- Modelos de frase para cada ferramenta, com 3 redações cada, preenchidos com os municípios cadastrados, culturas,
  anos e meses sorteados (semente fixa): chuva de um mês, chuva mês a mês de um ano, chuva da safra (com o rótulo
  "2023/24" na soja → ano 2024), rendimento no município (com "milho safrinha"), produção na UF e no Brasil,
  correlação com a chuva de um mês da janela e com o veranico, estimativa do IBGE, previsão, gráficos (o mapa de calor
  sem cultura), descobertas, alertas e municípios. Artigos certos: "de milho", "lavoura de soja".
- **A última redação de cada modelo fica só na avaliação**: o modelo é medido com frases que nunca viu.
- Perguntas reais do chat em que todas as ferramentas deram certo (a primeira chamada é o alvo).
- Cada exemplo de treino: `{"messages": [sistema, pergunta, assistente com tool_calls], "tools": TOOLS}`, com o
  **mesmo prompt de sistema do chat** (`system_prompt`).

## Avaliação (`backend/app/finetune/evaluate.py`)

Para cada pergunta da avaliação, o modelo do Ollama recebe o prompt de sistema, a pergunta e as ferramentas
(temperatura 0, sem raciocínio) e a primeira chamada é comparada ao alvo: ferramenta certa; ferramenta e argumentos
certos (texto sem acento e sem diferença de maiúsculas, números como inteiros; argumento a mais não é erro; agrupar
por mês um único mês equivale ao total). Relatório JSON com os percentuais, o tempo por pergunta, o acerto por modelo
de frase e cada erro (esperado × recebido).

Linha de comando no container do backend: `python -m app.finetune exportar --saida /finetuning/data` e
`python -m app.finetune avaliar --modelo <modelo>`.

## Treino (`finetuning/`)

- `requirements.txt` com as versões fixas: `unsloth==2026.11.1`, `unsloth_zoo==2026.11.1`, `torch==2.14.1`,
  `transformers==5.17.0`, `trl==1.15.0`, `peft==0.21.2`, `datasets==4.8.5`, `bitsandbytes==0.50.2`.
- `Dockerfile` a partir de `python:3.12-slim` com `build-essential`, `cmake`, `git`, `curl` e `libcurl4-openssl-dev`
  (a exportação para GGUF compila o llama.cpp), `HF_HOME=/finetuning/cache/huggingface`. `.dockerignore` com `data`,
  `output` e `cache`.
- `treinar.py`: carrega `BASE_MODEL` (padrão `unsloth/Qwen3-8B`) em 4 bits; LoRA com rank 16 nas projeções de atenção
  e MLP; texto de cada exemplo pelo template do próprio tokenizer (`apply_chat_template` com as ferramentas e
  `enable_thinking=False`); `SFTTrainer` com lote 1, acumulação 8, 2 épocas, `adamw_8bit`, taxa 2e-4;
  `train_on_responses_only` (só a resposta do assistente conta no erro); salva o LoRA, exporta o modelo inteiro em
  GGUF `q4_k_m`, copia para `output/celke-agro.gguf` e grava `output/treino.json` (perda inicial e final, tempo).
- `criar_modelo.sh` (roda no container do Ollama): pega o `Modelfile` do modelo base (`ollama show --modelfile`),
  troca o `FROM` pelo GGUF treinado e cria `celke-agro`, mantendo o template de ferramentas do Qwen3.

- `treinar_remoto.sh` (GPU externa, rodado no Linux, no macOS ou no Git Bash): `./finetuning/treinar_remoto.sh
  usuario@ip [porta]`, com `GPU_SSH_KEY` e as variáveis `FINETUNE_*` do `.env`. Confere a GPU com `nvidia-smi`, envia
  `treinar.py`, `requirements.txt` e `treino.jsonl` para `~/celke-finetune`, instala os pacotes do sistema que faltarem
  (com `sudo` se não for root), cria um ambiente Python isolado, instala as dependências fixas, treina e traz
  `celke-agro.gguf` e `treino.json` para `finetuning/output/`. Com `CRIAR_NO_SERVIDOR=1`, cria o `celke-agro` também
  no Ollama do servidor. Termina lembrando de apagar a instância, cobrada por hora.

## Compose

- `finetune-tools` (profile `finetune`): imagem do backend com `entrypoint: ["python", "-m", "app.finetune"]`, o mesmo
  ambiente (`*backend-environment`) e `./finetuning:/finetuning`.
- `finetune-train` (profile `finetune`): build de `./finetuning`, `./finetuning:/finetuning`, `shm_size: 8gb`, GPU
  NVIDIA em `deploy.resources.reservations.devices`, variáveis `FINETUNE_BASE_MODEL`, `FINETUNE_EPOCHS` e
  `FINETUNE_MAX_SEQ_LENGTH` (padrão 4096; os exemplos têm cerca de 2.400 tokens).
- No `ollama`, o volume `./finetuning:/finetuning:ro`.
- `.gitignore`: o conteúdo de `finetuning/data` e `finetuning/output` (com `.gitkeep`) e `finetuning/cache/`.

## Testes

Os modelos de frase só usam ferramentas que existem e com argumentos que passam na validação delas; a última
redação nunca aparece no treino; "2023/24" vira 2024; o dataset usa o prompt do chat e as conversas reais; a nota
ignora argumento a mais e acento e aceita a equivalência do mês; a avaliação conta acertos e erros com um cliente
falso.

## Verificação

```bash
docker compose --profile test run --rm --build backend-tests
docker compose --profile finetune run --rm --build finetune-tools exportar
docker compose --profile finetune run --rm finetune-tools avaliar --modelo qwen3:8b     # o "antes"
```

Com GPU NVIDIA, também:

```bash
docker compose --profile finetune run --rm --build finetune-train
docker compose exec ollama sh /finetuning/criar_modelo.sh qwen3:8b celke-agro
docker compose --profile finetune run --rm finetune-tools avaliar --modelo celke-agro   # o "depois"
```

Com uma GPU externa (por exemplo, uma instância da Hostinger com 24 GB):

```bash
./finetuning/treinar_remoto.sh root@<ip>
docker compose exec ollama sh /finetuning/criar_modelo.sh qwen3:8b celke-agro
docker compose --profile finetune run --rm finetune-tools avaliar --modelo celke-agro
```

Sem GPU local nem externa, registre o treino como pendência e siga: o projeto funciona com o modelo base.
