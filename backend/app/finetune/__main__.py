"""Linha de comando do fine-tuning (roda no container do backend):

python -m app.finetune exportar --saida /finetuning/data
python -m app.finetune avaliar --modelo qwen3:8b --dados /finetuning/data --saida /finetuning/data
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import ollama

from app.core.config import get_settings
from app.finetune.dataset import build_dataset, write_jsonl
from app.finetune.evaluate import evaluate
from app.repositories.crop_repository import CropRepository
from app.repositories.database import Database
from app.repositories.municipality_repository import MunicipalityRepository


def export(out: Path) -> int:
    settings = get_settings()
    database = Database(settings.database_conninfo)
    municipalities = [(m.name, m.state) for m in MunicipalityRepository(database).all()]
    if not municipalities:
        print("Cadastre ao menos um município antes de gerar o dataset.", file=sys.stderr)
        return 1
    last_year = CropRepository(database).last_year() or date.today().year - 1
    train, evaluation = build_dataset(database, municipalities, settings.history_start_year, last_year, date.today())
    out.mkdir(parents=True, exist_ok=True)
    write_jsonl(out / "treino.jsonl", train)
    write_jsonl(out / "avaliacao.jsonl", evaluation)
    sources = sorted({row["source"] for row in train})
    print(f"Treino: {len(train)} exemplos ({', '.join(sources)})")
    print(f"Avaliação: {len(evaluation)} perguntas com redações que não estão no treino")
    print(f"Arquivos em {out}")
    return 0


def run_evaluation(model: str, data: Path, out: Path, limit: int | None) -> int:
    settings = get_settings()
    items = [json.loads(line) for line in (data / "avaliacao.jsonl").read_text(encoding="utf-8").splitlines() if line]
    if limit:
        items = items[:limit]
    client = ollama.Client(host=settings.ollama_url, timeout=settings.ollama_timeout_seconds)
    print(f"Avaliando {model} com {len(items)} perguntas (pode levar alguns minutos na CPU)...")
    result = evaluate(client, model, items, settings.chat_num_ctx).as_dict()
    out.mkdir(parents=True, exist_ok=True)
    report = out / f"avaliacao-{model.replace(':', '-').replace('/', '-')}.json"
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Ferramenta certa: {result['ferramenta_certa_pct']}%")
    print(f"Ferramenta e argumentos certos: {result['ferramenta_e_argumentos_certos_pct']}%")
    print(f"Tempo por pergunta: {result['segundos_por_pergunta']} s")
    print(f"Relatório: {report}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.finetune")
    commands = parser.add_subparsers(dest="command", required=True)
    exporter = commands.add_parser("exportar", help="gera treino.jsonl e avaliacao.jsonl")
    exporter.add_argument("--saida", type=Path, default=Path("/finetuning/data"))
    evaluator = commands.add_parser("avaliar", help="mede o acerto de um modelo do Ollama")
    evaluator.add_argument("--modelo", required=True)
    evaluator.add_argument("--dados", type=Path, default=Path("/finetuning/data"))
    evaluator.add_argument("--saida", type=Path, default=Path("/finetuning/data"))
    evaluator.add_argument("--limite", type=int, default=None)
    args = parser.parse_args()
    if args.command == "exportar":
        return export(args.saida)
    return run_evaluation(args.modelo, args.dados, args.saida, args.limite)


if __name__ == "__main__":
    sys.exit(main())
