"""Mede quantas perguntas da avaliação o modelo acerta: a ferramenta certa e os argumentos certos.

Roda com qualquer modelo do Ollama, antes e depois do fine-tuning, com as mesmas perguntas (nunca vistas no treino).
"""

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import ollama

from app.core.domain import normalize
from app.services.tools import TOOLS


def same_value(expected: Any, got: Any) -> bool:
    if isinstance(expected, str):
        return isinstance(got, str) and normalize(got) == normalize(expected)
    if isinstance(expected, int):
        try:
            return int(got) == expected
        except (TypeError, ValueError):
            return False
    return expected == got


def score(expected_tool: str, expected_args: dict, got_tool: str | None, got_args: dict) -> tuple[bool, bool]:
    """(ferramenta certa, argumentos certos). Argumento a mais não conta como erro (ex.: a UF junto do município)."""
    tool_ok = got_tool == expected_tool
    args_ok = tool_ok and all(
        same_value(v, got_args.get(k)) or equivalent(expected_tool, k, v, got_args) for k, v in expected_args.items()
    )
    return tool_ok, args_ok


def equivalent(tool: str, key: str, expected: Any, got_args: dict) -> bool:
    """Respostas diferentes que dão o mesmo resultado não contam como erro."""
    # chuva de um único mês: agrupar por mês ou somar o total dá o mesmo número
    if tool == "consultar_chuva" and key == "agrupamento" and expected == "total" and got_args.get(key) == "mes":
        start, end = str(got_args.get("inicio", "")), str(got_args.get("fim", ""))
        return start[:7] == end[:7] != ""
    return False


@dataclass
class Evaluation:
    model: str
    total: int
    tool_ok: int
    args_ok: int
    seconds: float
    by_source: dict[str, dict[str, int]]
    misses: list[dict]

    def as_dict(self) -> dict:
        return {
            "modelo": self.model,
            "perguntas": self.total,
            "ferramenta_certa_pct": round(self.tool_ok / self.total * 100, 1) if self.total else 0,
            "ferramenta_e_argumentos_certos_pct": round(self.args_ok / self.total * 100, 1) if self.total else 0,
            "segundos_por_pergunta": round(self.seconds / self.total, 1) if self.total else 0,
            "por_modelo_de_frase": self.by_source,
            "erros": self.misses,
        }


def evaluate(client: ollama.Client, model: str, items: list[dict], num_ctx: int = 8192) -> Evaluation:
    tool_ok = args_ok = 0
    by_source: dict[str, dict[str, int]] = defaultdict(lambda: {"perguntas": 0, "acertos": 0})
    misses = []
    start = time.time()
    for item in items:
        response = client.chat(
            model=model,
            messages=[{"role": "system", "content": item["system"]}, {"role": "user", "content": item["question"]}],
            tools=TOOLS,
            think=False,
            options={"num_ctx": num_ctx, "temperature": 0},
        )
        calls = response.message.tool_calls or []
        got_tool = calls[0].function.name if calls else None
        got_args = dict(calls[0].function.arguments or {}) if calls else {}
        ok_tool, ok_args = score(item["tool"], item["arguments"], got_tool, got_args)
        tool_ok += ok_tool
        args_ok += ok_args
        by_source[item["source"]]["perguntas"] += 1
        by_source[item["source"]]["acertos"] += ok_args
        if not ok_args:
            misses.append(
                {
                    "pergunta": item["question"],
                    "esperado": {"ferramenta": item["tool"], "argumentos": item["arguments"]},
                    "recebido": {"ferramenta": got_tool, "argumentos": got_args},
                }
            )
    return Evaluation(model, len(items), tool_ok, args_ok, time.time() - start, dict(by_source), misses)
