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
