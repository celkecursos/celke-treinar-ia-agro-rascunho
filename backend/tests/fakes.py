"""Dublês das fontes públicas, do modelo e do executor: os testes unitários não usam internet nem o Ollama.

Os dados sintéticos são determinísticos: a chuva tem estação chuvosa e seca, e o rendimento cresce com a tendência
e acompanha a chuva da safra, para a varredura de descobertas ter o que encontrar.
"""

import math
import re
from collections.abc import Iterator
from concurrent.futures import Executor, Future
from datetime import date, timedelta

from app.core.domain import CROPS, LSPA_PRODUCTS
from app.core.errors import AppError
from app.repositories.crop_repository import CropEstimate, CropYear
from app.services.ollama_service import ChatChunk, InstalledModel, PullProgress, same_model

# mm por dia de chuva, por mês: chuvoso de outubro a março, seco no meio do ano
MONTH_BASE = {1: 9, 2: 8, 3: 7, 4: 4, 5: 1.5, 6: 0.3, 7: 0.1, 8: 0.3, 9: 2, 10: 5, 11: 8, 12: 9}

MUNICIPALITIES = {
    5218805: ("Rio Verde", "GO"),
    5211909: ("Jataí", "GO"),
    5213103: ("Mineiros", "GO"),
    4113700: ("Londrina", "PR"),
}


def year_factor(year: int) -> float:
    """Ano mais ou menos chuvoso (entre 0,6 e 1,4)."""
    return 1 + 0.4 * math.sin(year * 1.7)


def season_factor(year: int) -> float:
    """Chuva da janela da soja do ano `year`: metade do ano anterior (out a dez), metade do próprio ano."""
    return (year_factor(year - 1) + year_factor(year)) / 2


def synthetic_rain(code: int, start: date, end: date) -> list[tuple[date, float]]:
    days = []
    day = start
    while day <= end:
        rains = (day.toordinal() * 7 + code) % 3 == 0
        mm = round(MONTH_BASE[day.month] * 3 * year_factor(day.year), 1) if rains else 0.0
        days.append((day, mm))
        day += timedelta(days=1)
    return days


class FakeRainSource:
    def __init__(self, today: date = date(2024, 12, 15)):
        self.today = today
        self.archive_calls: list[tuple[float, float, date, date]] = []
        self.error: AppError | None = None
        self.coordinates = {name: (-17.8 - i, -50.9 - i) for i, (name, _) in enumerate(MUNICIPALITIES.values())}

    def _code(self, latitude: float) -> int:
        return int(abs(latitude) * 1000)

    def archive(self, latitude, longitude, start, end):
        if self.error:
            raise self.error
        self.archive_calls.append((latitude, longitude, start, end))
        return synthetic_rain(self._code(latitude), start, min(end, self.today - timedelta(days=5)))

    def recent(self, latitude, longitude, past_days):
        if self.error:
            raise self.error
        return synthetic_rain(
            self._code(latitude), self.today - timedelta(days=past_days), self.today - timedelta(days=1)
        )

    def geocode(self, name, state_acronym):
        return self.coordinates.get(name)


class FakeIbge:
    def __init__(self, last_year: int = 2024):
        self.last_year = last_year
        self.pam_calls: list[tuple[str, list[int], int, int]] = []
        self.lspa_calls: list[tuple[str, list[int], int]] = []

    def municipality(self, code):
        if code not in MUNICIPALITIES:
            raise AppError(f"O IBGE não tem município com o código {code}.")
        return MUNICIPALITIES[code]

    def municipalities_of_state(self, state_acronym):
        return [(c, n) for c, (n, uf) in MUNICIPALITIES.items() if uf == state_acronym]

    def pam_last_year(self):
        return self.last_year

    def pam(self, level, codes, start, end):
        self.pam_calls.append((level, list(codes), start, end))
        rows = []
        for code in codes if level != "brasil" else [1]:
            for year in range(start, end + 1):
                for crop in CROPS.values():
                    trend = (3000 if crop.key == "soja" else 5000) + 40 * (year - 2000)
                    factor = season_factor(year) if crop.key == "soja" else year_factor(year)
                    yield_kg = round(trend * (1 + 0.6 * (factor - 1)))
                    rows.append(
                        CropYear(level, code, crop.key, year, 100_000.0, 99_000.0, yield_kg * 99.0, float(yield_kg))
                    )
        return rows

    def top_soy_municipalities(self, state_code, year, count):
        return [(5211909, "Jataí", 300_000.0), (5213103, "Mineiros", 200_000.0)][:count] if state_code == 52 else []

    def lspa(self, level, codes, months):
        self.lspa_calls.append((level, list(codes), months))
        return [
            CropEstimate(level, code if level != "brasil" else 1, product, 202411, 1e6, 9e5, 3.6e6, 3600.0)
            for code in codes
            for product in LSPA_PRODUCTS.values()
        ]


class FakeModel:
    """Chat roteirizado: cada item de `rounds` é uma rodada (lista de pedaços). Depois do roteiro, responde texto."""

    name = "modelo-teste"

    def __init__(self, rounds: list[list[ChatChunk]] | None = None, answer: str = "Resposta de teste."):
        self.rounds = list(rounds or [])
        self.answer = answer
        self.chat_calls: list[tuple[list[dict], list[dict] | None]] = []
        self.json_calls: list[list[dict]] = []
        self.error: AppError | None = None
        self.json_error: AppError | None = None

    def chat_stream(self, messages, tools=None) -> Iterator[ChatChunk]:
        self.chat_calls.append(([dict(m) for m in messages], tools))
        if self.error:
            raise self.error
        if self.rounds:
            yield from self.rounds.pop(0)
            return
        yield ChatChunk("thinking", "pensando")
        for word in re.findall(r"\S+\s*", self.answer):
            yield ChatChunk("content", word)

    def chat_json(self, messages, schema):
        self.json_calls.append(messages)
        if self.json_error:
            raise self.json_error
        if "descobertas" in schema["properties"]:
            ids = re.findall(r'<descoberta id="(d\d+)"', messages[-1]["content"])
            return {
                "descobertas": [
                    {"id": i, "interpretacao": f"Interpretação {i}", "hipotese": f"Hipótese {i}"} for i in ids
                ]
            }
        if "proximas_perguntas" in schema["properties"]:
            return {"resumo": "Resumo de teste.", "proximas_perguntas": ["Pergunta 1?", "Pergunta 2?"]}
        return {"explicacao": "Explicação de teste."}  # alertas e treino da previsão


class FakeGpu:
    """O túnel da GPU externa visto pelo `ModelSelector`: cadastrado, conectado e a mensagem."""

    def __init__(self, configured: bool = True, connected: bool = True, message: str | None = None):
        self.configured = configured
        self.connected = connected
        self.message = message


class FakeOllamaServer:
    """Um servidor Ollama falso para o `ModelSelector`: modelos instalados, capacidades, download e erro de conexão."""

    def __init__(self, location: str, models: dict[str, list[str]] | None = None):
        self.location = location
        # nome do modelo -> capacidades
        self.models = dict(models if models is not None else {"qwen3:8b": ["completion", "tools"]})
        self.error: AppError | None = None
        self.pull_error: AppError | None = None
        self.chat_calls: list[str] = []

    def installed_models(self) -> list[InstalledModel]:
        if self.error:
            raise self.error
        return [InstalledModel(name, 5_200_000_000, "8.2B") for name in self.models]

    def is_installed(self, model, installed=None) -> bool:
        return any(same_model(m.name, model) for m in (installed or self.installed_models()))

    def capabilities(self, model) -> list[str]:
        return self.models[model]

    def pull(self, model) -> Iterator[PullProgress]:
        yield PullProgress("pulling manifest")
        yield PullProgress("pulling abc", "sha256:abc", 50, 100)
        if self.pull_error:
            raise self.pull_error
        yield PullProgress("pulling abc", "sha256:abc", 100, 100)
        yield PullProgress("success")
        self.models[model] = ["completion", "tools"]

    def chat_stream(self, model, messages, tools=None) -> Iterator[ChatChunk]:
        self.chat_calls.append(model)
        yield ChatChunk("content", f"{self.location}:{model}")

    def chat_json(self, model, messages, schema) -> dict:
        self.chat_calls.append(model)
        return {}


def tool_call(name: str, **arguments) -> ChatChunk:
    return ChatChunk("tool_call", name=name, arguments=arguments)


class ImmediateExecutor(Executor):
    """Executa a tarefa na hora, para o teste ver o resultado."""

    def submit(self, fn, /, *args, **kwargs):
        future: Future = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except Exception as exc:  # como no executor real: o erro fica no Future
            future.set_exception(exc)
        return future


class DeferredExecutor(Executor):
    """Guarda as tarefas sem executar: para testar o que acontece enquanto a coleta está em andamento."""

    def __init__(self):
        self.jobs = []

    def submit(self, fn, /, *args, **kwargs):
        self.jobs.append((fn, args, kwargs))
        return Future()

    def run_all(self):
        while self.jobs:
            fn, args, kwargs = self.jobs.pop(0)
            fn(*args, **kwargs)
