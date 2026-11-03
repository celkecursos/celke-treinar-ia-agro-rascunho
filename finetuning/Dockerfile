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
