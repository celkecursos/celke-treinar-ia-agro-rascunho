#!/usr/bin/env sh
# Fine-tuning LoRA numa GPU externa (por exemplo, uma instância de GPU da Hostinger) por SSH: envia o dataset, treina
# no servidor e traz o modelo treinado para finetuning/output/. Na raiz do projeto (Linux, macOS ou Git Bash no
# Windows):
#   ./finetuning/treinar_remoto.sh                               # o servidor e a chave cadastrados na página Modelo de IA
#   ./finetuning/treinar_remoto.sh root@<ip-do-servidor> [porta-ssh]   # outro servidor, com a sua chave (GPU_SSH_KEY)
# Antes, gere o dataset: docker compose --profile finetune run --rm finetune-tools exportar
# Com CRIAR_NO_SERVIDOR=1, cria também o modelo celke-agro no Ollama do servidor (para o chat na GPU externa).
# A instância é cobrada por hora: apague-a no painel quando terminar.
set -eu
cd "$(dirname "$0")/.."

if [ $# -ge 1 ]; then
  destino="$1"
  porta="${2:-${GPU_SSH_PORT:-22}}"
  chave="${GPU_SSH_KEY:-$HOME/.ssh/id_ed25519}"
else
  # Sem argumentos: usa a GPU externa da página Modelo de IA (card GPU externa) e a chave que o servidor
  # já aceita, copiada do volume do backend para um arquivo temporário apagado no fim.
  servidor=$(docker compose exec -T backend python -c "
import json, urllib.request
g = json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/gpu', timeout=10))
print(f\"{g['user']}@{g['host']} {g['port']}\" if g['configured'] else '')
" 2>/dev/null || true)
  if [ -z "$servidor" ]; then
    echo "Nenhuma GPU externa cadastrada. Cadastre em Status e coletas > Configurar > GPU externa, ou rode:"
    echo "  ./finetuning/treinar_remoto.sh usuario@ip-do-servidor [porta-ssh]"
    exit 1
  fi
  destino="${servidor% *}"
  porta="${servidor##* }"
  chave=$(mktemp)
  trap 'rm -f "$chave"' EXIT INT TERM
  docker compose exec -T backend cat /data/ssh/id_ed25519 > "$chave"
  chmod 600 "$chave"
  echo "GPU externa da página Modelo de IA: $destino (porta $porta)"
fi
# valores do .env, se existirem (sem sobrescrever os que já vieram do ambiente)
if [ -f .env ]; then
  for nome in FINETUNE_BASE_MODEL FINETUNE_EPOCHS FINETUNE_MAX_SEQ_LENGTH CHAT_MODEL; do
    valor=$(grep -E "^$nome=" .env | tail -1 | cut -d= -f2- || true)
    eval "atual=\${$nome:-}"
    if [ -z "$atual" ] && [ -n "$valor" ]; then export "$nome=$valor"; fi
  done
fi
base="${FINETUNE_BASE_MODEL:-unsloth/Qwen3-8B}"
epocas="${FINETUNE_EPOCHS:-2}"
tamanho="${FINETUNE_MAX_SEQ_LENGTH:-4096}"
modelo_ollama="${CHAT_MODEL:-qwen3:8b}"
# o ~ é expandido no servidor, não aqui
# shellcheck disable=SC2088
pasta='~/celke-finetune'

remoto() {
  ssh -p "$porta" -i "$chave" -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 "$destino" "$@"
}
copiar() {
  scp -P "$porta" -i "$chave" -o StrictHostKeyChecking=accept-new "$@"
}

if [ ! -f finetuning/data/treino.jsonl ]; then
  echo "Gere o dataset antes: docker compose --profile finetune run --rm finetune-tools exportar"
  exit 1
fi

echo "1/4 Conferindo a GPU do servidor..."
if ! remoto nvidia-smi --query-gpu=name,memory.total --format=csv,noheader; then
  echo "O servidor não respondeu ou não tem GPU NVIDIA com driver. Confira o IP, a chave SSH e o tipo da instância."
  exit 1
fi

echo "2/4 Enviando o dataset e o script de treino..."
remoto "mkdir -p $pasta/data $pasta/output"
copiar finetuning/treinar.py finetuning/requirements.txt "$destino:$pasta/"
copiar finetuning/data/treino.jsonl "$destino:$pasta/data/"

echo "3/4 Instalando e treinando no servidor (a primeira vez baixa cerca de 10 GB; o treino leva de 20 a 60 minutos)."
echo "    Modelo base: $base, $epocas época(s). Não feche este terminal."
remoto "set -e
cd $pasta
admin=''; [ \"\$(id -u)\" = 0 ] || admin=sudo
if ! command -v cmake > /dev/null || ! python3 -c 'import ensurepip' 2> /dev/null; then
  \$admin env DEBIAN_FRONTEND=noninteractive apt-get update -qq
  \$admin env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-venv python3-dev build-essential cmake git curl libcurl4-openssl-dev > /dev/null
fi
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
FINETUNE_DATA=\$PWD/data FINETUNE_OUTPUT=\$PWD/output HF_HOME=\$PWD/cache \
  BASE_MODEL='$base' EPOCHS='$epocas' MAX_SEQ_LENGTH='$tamanho' .venv/bin/python treinar.py"

echo "4/4 Trazendo o modelo treinado..."
mkdir -p finetuning/output
copiar "$destino:$pasta/output/celke-agro.gguf" "$destino:$pasta/output/treino.json" finetuning/output/

if [ "${CRIAR_NO_SERVIDOR:-0}" = 1 ]; then
  echo "Criando o modelo celke-agro no Ollama do servidor (a partir de $modelo_ollama)..."
  remoto "ollama show '$modelo_ollama' --modelfile | sed 's#^FROM .*#FROM '\$HOME'/celke-finetune/output/celke-agro.gguf#' > /tmp/Modelfile && ollama create celke-agro -f /tmp/Modelfile"
fi

echo ""
echo "Pronto: finetuning/output/celke-agro.gguf e finetuning/output/treino.json"
echo "Modelo neste computador: docker compose exec ollama sh /finetuning/criar_modelo.sh $modelo_ollama celke-agro"
echo "Medir o depois: docker compose --profile finetune run --rm finetune-tools avaliar --modelo celke-agro"
echo "Lembre de apagar a instância no painel da Hostinger: ela é cobrada por hora."
