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
