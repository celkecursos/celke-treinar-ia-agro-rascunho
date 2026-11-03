# Fine-tuning do modelo de linguagem

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

Regras desta etapa:

- Crie os arquivos com **exatamente** o conteúdo indicado, sem melhorar nem reformatar. O conteúdo já foi
  testado junto; uma alteração aqui quebra outra etapa.
- Não pergunte nada ao usuário: as decisões estão neste prompt e em `docs/configuracao.md`.
- Mostre ao usuário as seções **Orientação** (antes de começar e ao terminar), com as suas palavras só onde
  houver marcador a trocar. Se o terminal não permitir mostrar agora, inclua no seu relatório final.
- Rode tudo o que está em **Verificação** e corrija o que falhar antes de terminar.
- Nunca mostre o valor de `POSTGRES_PASSWORD`.

Depois, deixe `finetuning/criar_modelo.sh` executável: `chmod +x finetuning/criar_modelo.sh`.

`finetuning/.dockerignore`:

``````text
data
output
cache
``````

`finetuning/Dockerfile`:

``````dockerfile
# Treino LoRA na GPU NVIDIA (docker compose --profile finetune run --rm finetune-train).
# Precisa do driver NVIDIA (Windows: Docker Desktop com WSL 2; Linux: NVIDIA Container Toolkit).
FROM python:3.12-slim
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONUNBUFFERED=1 \
    HF_HOME=/finetuning/cache/huggingface
# compiladores e cmake: a exportação para GGUF compila o llama.cpp na primeira vez
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake git curl libcurl4-openssl-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY treinar.py .
CMD ["python", "treinar.py"]
``````

`finetuning/criar_modelo.sh`:

``````sh
#!/bin/sh
# Cria no Ollama o modelo treinado, com o mesmo modelo de conversa (template com ferramentas) e os mesmos parâmetros
# do modelo base. Roda dentro do container do Ollama:
#   docker compose exec ollama sh /finetuning/criar_modelo.sh qwen3:8b celke-agro
set -eu
base="${1:-qwen3:8b}"
name="${2:-celke-agro}"
gguf=/finetuning/output/celke-agro.gguf

if [ ! -f "$gguf" ]; then
  echo "Não encontrei $gguf. Rode antes o treino: docker compose --profile finetune run --rm finetune-train"
  exit 1
fi
ollama show "$base" --modelfile | sed "s#^FROM .*#FROM $gguf#" > /tmp/Modelfile
ollama create "$name" -f /tmp/Modelfile
echo "Modelo $name criado. Para usar no chat: CHAT_MODEL=$name no .env e rode o script de inicialização de novo."
``````

`finetuning/requirements.txt`:

``````text
# Unsloth: fine-tuning LoRA com 4 bits, cabe numa GPU de 12 GB. As demais versões são as que o pip resolve para ele,
# fixadas para o treino ser reproduzível.
unsloth==2026.11.1
unsloth_zoo==2026.11.1
torch==2.14.1
transformers==5.17.0
trl==1.15.0
peft==0.21.2
datasets==4.8.5
bitsandbytes==0.50.2
``````

`finetuning/treinar.py`:

``````python
"""Fine-tuning LoRA do modelo de linguagem: ensina a escolher a ferramenta e preencher os argumentos.

Entrada: /finetuning/data/treino.jsonl (gerado por `python -m app.finetune exportar` no backend).
Saída: /finetuning/output/celke-agro.gguf (modelo inteiro, já com o LoRA aplicado, em 4 bits) e treino.json (métricas).

Só ensina comportamento: os números continuam vindo das ferramentas. Roda na GPU NVIDIA (12 GB para o 8B).
"""

import json
import os
import shutil
import time
from pathlib import Path

# o Unsloth precisa ser importado antes do transformers e do trl
from unsloth import FastLanguageModel  # isort: skip
from unsloth.chat_templates import train_on_responses_only  # isort: skip
from datasets import Dataset
from trl import SFTConfig, SFTTrainer

DATA = Path(os.environ.get("FINETUNE_DATA", "/finetuning/data"))
OUTPUT = Path(os.environ.get("FINETUNE_OUTPUT", "/finetuning/output"))
# mesmo modelo do Ollama (qwen3:8b), em 4 bits para caber na GPU de 12 GB; para 8 GB, use unsloth/Qwen3-4B
BASE_MODEL = os.environ.get("BASE_MODEL", "unsloth/Qwen3-8B")
MAX_SEQ_LENGTH = int(os.environ.get("MAX_SEQ_LENGTH", "4096"))
EPOCHS = float(os.environ.get("EPOCHS", "2"))
LORA_RANK = int(os.environ.get("LORA_RANK", "16"))
LEARNING_RATE = float(os.environ.get("LEARNING_RATE", "2e-4"))
QUANTIZATION = os.environ.get("GGUF_QUANTIZATION", "q4_k_m")


def main() -> None:
    rows = [json.loads(line) for line in (DATA / "treino.jsonl").read_text(encoding="utf-8").splitlines() if line]
    print(f"{len(rows)} exemplos de treino; modelo base {BASE_MODEL}")

    model, tokenizer = FastLanguageModel.from_pretrained(BASE_MODEL, max_seq_length=MAX_SEQ_LENGTH, load_in_4bit=True)
    # LoRA: treina poucas matrizes pequenas ao lado dos pesos originais, que ficam congelados
    model = FastLanguageModel.get_peft_model(
        model,
        r=LORA_RANK,
        lora_alpha=LORA_RANK,
        lora_dropout=0,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    # o mesmo formato que o Ollama usa na conversa: prompt de sistema, ferramentas, pergunta e a chamada certa
    def to_text(row: dict) -> dict:
        text = tokenizer.apply_chat_template(
            row["messages"], tools=row["tools"], tokenize=False, enable_thinking=False
        )
        return {"text": text}

    dataset = Dataset.from_list(rows).map(to_text, remove_columns=["messages", "tools", "source"])
    longest = max(len(tokenizer(t)["input_ids"]) for t in dataset["text"])
    print(f"Maior exemplo: {longest} tokens (limite {MAX_SEQ_LENGTH})")

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        args=SFTConfig(
            dataset_text_field="text",
            max_length=MAX_SEQ_LENGTH,
            per_device_train_batch_size=1,
            gradient_accumulation_steps=8,
            num_train_epochs=EPOCHS,
            learning_rate=LEARNING_RATE,
            warmup_ratio=0.05,
            lr_scheduler_type="linear",
            optim="adamw_8bit",
            logging_steps=5,
            seed=42,
            output_dir=str(OUTPUT / "checkpoints"),
            report_to="none",
        ),
    )
    # só a resposta do assistente entra na conta do erro: o modelo não aprende a repetir o prompt
    trainer = train_on_responses_only(
        trainer, instruction_part="<|im_start|>user\n", response_part="<|im_start|>assistant\n"
    )

    start = time.time()
    stats = trainer.train()
    losses = [log["loss"] for log in trainer.state.log_history if "loss" in log]
    print(f"Treino em {time.time() - start:.0f} s; perda {losses[0]:.3f} → {losses[-1]:.3f}")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(OUTPUT / "lora"))
    tokenizer.save_pretrained(str(OUTPUT / "lora"))
    # modelo inteiro com o LoRA aplicado, quantizado em GGUF para o Ollama
    gguf_dir = OUTPUT / "gguf"
    model.save_pretrained_gguf(str(gguf_dir), tokenizer, quantization_method=QUANTIZATION)
    candidates = sorted(gguf_dir.rglob("*.gguf"), key=lambda p: p.stat().st_size, reverse=True)
    candidates = [p for p in candidates if QUANTIZATION.lower() in p.name.lower()] or candidates
    if not candidates:
        raise SystemExit("A exportação para GGUF não gerou arquivo. Veja as mensagens acima.")
    shutil.copy(candidates[0], OUTPUT / "celke-agro.gguf")
    (OUTPUT / "treino.json").write_text(
        json.dumps(
            {
                "modelo_base": BASE_MODEL,
                "exemplos": len(rows),
                "epocas": EPOCHS,
                "lora_rank": LORA_RANK,
                "segundos": round(time.time() - start),
                "perda_inicial": losses[0],
                "perda_final": losses[-1],
                "passos": stats.global_step,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Pronto: {OUTPUT / 'celke-agro.gguf'}")


if __name__ == "__main__":
    main()
``````

## Verificação

1. Cadastre Rio Verde (GO) e espere a coleta terminar (cerca de 1 minuto):
   ```bash
   curl -s -X POST http://localhost:<porta>/api/municipalities -H "Content-Type: application/json" -d '{"code":5218805}'
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
   Sem GPU, registre "treino LoRA pendente: precisa de GPU NVIDIA" no relatório e siga.

Mostre ao usuário os percentuais de acerto de antes e de depois.

## Depois de executar

```bash
git add finetuning
git update-index --chmod=+x finetuning/criar_modelo.sh
git commit -m "feat: adiciona o fine-tuning LoRA do modelo de linguagem"
```

## Orientação ao terminar

> **Pronto:** o fine-tuning está preparado. <Com GPU: "O modelo treinado `celke-agro` acertou <depois>% das perguntas
> novas, contra <antes>% do modelo original."> <Sem GPU: "O modelo atual acertou <antes>% das perguntas novas; o
> treino roda num computador com GPU NVIDIA, com os comandos do README."> Continue sem fazer nada.
