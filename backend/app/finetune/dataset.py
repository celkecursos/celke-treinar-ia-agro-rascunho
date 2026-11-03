"""Dataset do fine-tuning: perguntas e a chamada de ferramenta certa para cada uma.

O fine-tuning ensina **comportamento** (escolher a ferramenta e preencher os argumentos), nunca números: os números
continuam vindo das ferramentas. Duas origens:

- perguntas geradas por modelos de frase, com os municípios cadastrados, culturas, anos e meses variados;
- perguntas reais do chat cujas ferramentas deram certo (tabela `messages`).

Cada modelo de frase tem várias redações. A última redação de cada modelo fica **só na avaliação**: o modelo treinado
é medido com frases que nunca viu, e não com as mesmas do treino.
"""

import calendar
import json
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.core.domain import MONTH_NAMES, STATES_BY_ACRONYM
from app.repositories.database import Database
from app.services.chat_service import system_prompt
from app.services.tools import TOOLS

SEED = 42
DRAWS_PER_TEMPLATE = 12
EVALUATION_DRAWS = 4  # por modelo de frase: a medição precisa caber em poucos minutos na CPU


@dataclass
class Example:
    question: str
    tool: str
    arguments: dict[str, Any]
    source: str  # modelo de frase ou "conversa"
    split: str = "treino"

    def messages(self, system: str) -> list[dict]:
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": self.question},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"type": "function", "function": {"name": self.tool, "arguments": self.arguments}}],
            },
        ]


@dataclass
class Context:
    municipalities: list[tuple[str, str]]  # (nome, UF)
    first_year: int
    last_year: int
    rng: random.Random = field(default_factory=lambda: random.Random(SEED))

    def place(self) -> tuple[str, str]:
        return self.rng.choice(self.municipalities)

    def year(self) -> int:
        return self.rng.randint(self.first_year + 1, self.last_year)


def month_range(year: int, month: int) -> tuple[str, str]:
    return date(year, month, 1).isoformat(), date(year, month, calendar.monthrange(year, month)[1]).isoformat()


def _rain_month(c: Context, phrase: str) -> Example:
    (name, uf), year, month = c.place(), c.year(), c.rng.randint(1, 12)
    start, end = month_range(year, month)
    question = phrase.format(m=name, uf=uf, mes=MONTH_NAMES[month - 1], ano=year)
    return Example(
        question, "consultar_chuva", {"municipio": name, "inicio": start, "fim": end, "agrupamento": "total"}, ""
    )


def _rain_year_by_month(c: Context, phrase: str) -> Example:
    (name, uf), year = c.place(), c.year()
    question = phrase.format(m=name, uf=uf, ano=year)
    args = {"municipio": name, "inicio": f"{year}-01-01", "fim": f"{year}-12-31", "agrupamento": "mes"}
    return Example(question, "consultar_chuva", args, "")


def _season_rain(c: Context, phrase: str) -> Example:
    (name, uf), year = c.place(), c.year()
    crop = c.rng.choice(["soja", "milho"])
    # "safra 2023/24" da soja = ano 2024 da PAM; o milho 2ª safra é do próprio ano
    label = f"{year - 1}/{str(year)[2:]}" if crop == "soja" else str(year)
    question = phrase.format(m=name, uf=uf, cultura=crop, safra=label)
    return Example(
        question, "chuva_da_safra", {"municipio": name, "cultura": crop, "ano_inicio": year, "ano_fim": year}, ""
    )


def _yield_city(c: Context, phrase: str) -> Example:
    (name, uf), year = c.place(), c.year()
    crop = c.rng.choice(["soja", "milho"])
    crop_text = {"soja": "a soja", "milho": c.rng.choice(["o milho", "o milho safrinha"])}[crop]
    question = phrase.format(m=name, uf=uf, cultura=crop_text, ano=year)
    args = {"cultura": crop, "nivel": "municipio", "municipio": name, "ano_inicio": year, "ano_fim": year}
    return Example(question, "consultar_producao", args, "")


def _production_state(c: Context, phrase: str) -> Example:
    _, uf = c.place()
    crop = c.rng.choice(["soja", "milho"])
    question = phrase.format(estado=STATES_BY_ACRONYM[uf].name, cultura=crop)
    return Example(question, "consultar_producao", {"cultura": crop, "nivel": "uf", "uf": uf}, "")


def _production_brazil(c: Context, phrase: str) -> Example:
    year, crop = c.year(), c.rng.choice(["soja", "milho"])
    question = phrase.format(cultura=crop, ano=year)
    return Example(
        question, "consultar_producao", {"cultura": crop, "nivel": "brasil", "ano_inicio": year, "ano_fim": year}, ""
    )


def _correlation_month(c: Context, phrase: str) -> Example:
    name, uf = c.place()
    crop = c.rng.choice(["soja", "milho"])
    months = [10, 11, 12, 1, 2, 3] if crop == "soja" else [1, 2, 3, 4]
    month = c.rng.choice(months)
    question = phrase.format(m=name, uf=uf, cultura=crop, mes=MONTH_NAMES[month - 1])
    args = {"municipio": name, "cultura": crop, "variavel": "chuva_do_mes", "mes": month}
    return Example(question, "correlacao_chuva_rendimento", args, "")


def _correlation_dry(c: Context, phrase: str) -> Example:
    name, uf = c.place()
    crop = c.rng.choice(["soja", "milho"])
    question = phrase.format(m=name, uf=uf, cultura=crop)
    return Example(
        question, "correlacao_chuva_rendimento", {"municipio": name, "cultura": crop, "variavel": "veranico"}, ""
    )


def _estimate(c: Context, phrase: str) -> Example:
    _, uf = c.place()
    crop = c.rng.choice(["soja", "milho"])
    question = phrase.format(estado=STATES_BY_ACRONYM[uf].name, cultura=crop)
    return Example(question, "estimativa_safra", {"cultura": crop, "uf": uf}, "")


def _forecast(c: Context, phrase: str) -> Example:
    name, uf = c.place()
    crop = c.rng.choice(["soja", "milho"])
    question = phrase.format(m=name, uf=uf, cultura=crop)
    return Example(question, "previsao_safra", {"municipio": name, "cultura": crop}, "")


def _chart(c: Context, phrase: str, kind: str) -> Example:
    name, uf = c.place()
    crop = c.rng.choice(["soja", "milho"])
    question = phrase.format(m=name, uf=uf, cultura=crop)
    args = {"tipo": kind, "municipio": name}
    if kind != "mapa_de_calor":  # o mapa de calor é só de chuva: a cultura não muda nada
        args["cultura"] = crop
    return Example(question, "mostrar_grafico", args, "")


def _discoveries(c: Context, phrase: str) -> Example:
    name, uf = c.place()
    return Example(phrase.format(m=name, uf=uf), "ver_descobertas", {"municipio": name}, "")


def _fixed(tool: str) -> Callable[[Context, str], Example]:
    def build(c: Context, phrase: str) -> Example:
        return Example(phrase, tool, {}, "")

    return build


# (id, gerador, redações): a última redação de cada um fica só na avaliação
TEMPLATES: list[tuple[str, Callable[[Context, str], Example], list[str]]] = [
    (
        "chuva_mes",
        _rain_month,
        [
            "Quanto choveu em {m} em {mes} de {ano}?",
            "Qual foi o total de chuva de {mes} de {ano} em {m} ({uf})?",
            "Me diga a chuva acumulada em {m} no mês de {mes}/{ano}.",
        ],
    ),
    (
        "chuva_ano_por_mes",
        _rain_year_by_month,
        [
            "Mostre a chuva de cada mês de {ano} em {m}.",
            "Como a chuva se distribuiu ao longo de {ano} em {m} ({uf}), mês a mês?",
            "Quero a chuva mensal de {m} em {ano}.",
        ],
    ),
    (
        "chuva_safra",
        _season_rain,
        [
            "Como foi a chuva na safra {safra} de {cultura} em {m}?",
            "Choveu bem na safra {safra} de {cultura} em {m} ({uf})?",
            "Quanta chuva teve a safra {safra} de {cultura} em {m}?",
        ],
    ),
    (
        "rendimento_municipio",
        _yield_city,
        [
            "Qual foi o rendimento d{cultura} em {m} em {ano}?",
            "Quantos kg por hectare deu {cultura} em {m} ({uf}) no ano de {ano}?",
            "Como foi a produtividade d{cultura} em {m} em {ano}?",
        ],
    ),
    (
        "producao_uf",
        _production_state,
        [
            "Mostre a produção de {cultura} em {estado} nos últimos anos.",
            "Quanto {estado} produziu de {cultura} por ano?",
            "Qual a evolução da produção de {cultura} no estado de {estado}?",
        ],
    ),
    (
        "producao_brasil",
        _production_brazil,
        [
            "Quanto o Brasil produziu de {cultura} em {ano}?",
            "Qual foi a produção nacional de {cultura} em {ano}?",
            "Produção de {cultura} do país em {ano}?",
        ],
    ),
    (
        "correlacao_mes",
        _correlation_month,
        [
            "A chuva de {mes} influencia o rendimento de {cultura} em {m}?",
            "Existe relação entre a chuva de {mes} e a produtividade de {cultura} em {m} ({uf})?",
            "Chover mais em {mes} ajuda a lavoura de {cultura} em {m}?",
        ],
    ),
    (
        "correlacao_veranico",
        _correlation_dry,
        [
            "O veranico afeta o rendimento de {cultura} em {m}?",
            "Os dias seguidos sem chuva derrubam a produtividade de {cultura} em {m} ({uf})?",
            "Qual o efeito da seca no meio da safra na lavoura de {cultura} em {m}?",
        ],
    ),
    (
        "estimativa",
        _estimate,
        [
            "Qual a estimativa do IBGE para a safra de {cultura} deste ano em {estado}?",
            "O que o IBGE prevê para a lavoura de {cultura} em {estado} este ano?",
            "Qual o levantamento mais recente da safra de {cultura} em {estado}?",
        ],
    ),
    (
        "previsao",
        _forecast,
        [
            "Qual a previsão para a próxima safra de {cultura} em {m}?",
            "Quanto o modelo prevê de rendimento de {cultura} em {m} ({uf})?",
            "O que esperar da próxima colheita de {cultura} em {m}?",
        ],
    ),
    (
        "grafico_chuva_rendimento",
        lambda c, p: _chart(c, p, "chuva_x_rendimento"),
        [
            "Mostre o gráfico de chuva e rendimento de {cultura} em {m}.",
            "Quero ver a chuva da safra junto com o rendimento de {cultura} em {m} num gráfico.",
            "Faça um gráfico comparando chuva e produtividade de {cultura} em {m}.",
        ],
    ),
    (
        "grafico_mapa_calor",
        lambda c, p: _chart(c, p, "mapa_de_calor"),
        [
            "Mostre o mapa de calor da chuva em {m}.",
            "Quero ver a chuva de todos os meses e anos de {m} num gráfico só.",
            "Gráfico de chuva por mês e ano em {m}, por favor.",
        ],
    ),
    (
        "descobertas",
        _discoveries,
        [
            "O que o sistema descobriu sobre {m}?",
            "Quais relações entre chuva e safra foram encontradas em {m} ({uf})?",
            "Tem alguma descoberta nova para {m}?",
        ],
    ),
    (
        "alertas",
        _fixed("ver_alertas"),
        ["Tem algum alerta de seca agora?", "Algum município está com chuva abaixo do normal?", "Há alertas ativos?"],
    ),
    (
        "municipios",
        _fixed("listar_municipios"),
        ["Quais municípios estão cadastrados?", "De quais cidades você tem dados?", "Liste os municípios disponíveis."],
    ),
]


def synthetic_examples(c: Context) -> list[Example]:
    examples: list[Example] = []
    for template_id, build, phrases in TEMPLATES:
        variable = "{" in "".join(phrases)
        for index, phrase in enumerate(phrases):
            last = index == len(phrases) - 1
            draws = (EVALUATION_DRAWS if last else DRAWS_PER_TEMPLATE) if variable else 1
            for _ in range(draws):
                example = build(c, phrase)
                example.source = template_id
                example.split = "avaliacao" if last else "treino"
                examples.append(example)
    # sem repetir a mesma pergunta
    unique = {(e.question, e.split): e for e in examples}
    return list(unique.values())


def conversation_examples(database: Database) -> list[Example]:
    """Perguntas reais do chat em que todas as ferramentas deram certo: a primeira chamada é o alvo."""
    with database.connection() as conn:
        rows = conn.execute(
            "SELECT u.content AS question, a.tool_calls FROM messages a"
            " JOIN LATERAL (SELECT content FROM messages u WHERE u.conversation_id = a.conversation_id"
            " AND u.role = 'user' AND u.seq < a.seq ORDER BY u.seq DESC LIMIT 1) u ON true"
            " WHERE a.role = 'assistant' AND a.state = 'concluida' AND jsonb_array_length(a.tool_calls) > 0"
        ).fetchall()
    examples = []
    for row in rows:
        calls = row["tool_calls"]
        if all(c.get("ok") for c in calls) and calls[0]["name"] != "mostrar_grafico":
            examples.append(Example(row["question"], calls[0]["name"], calls[0]["arguments"], "conversa"))
    return examples


def build_dataset(
    database: Database, municipalities: list[tuple[str, str]], first_year: int, last_year: int, today: date
):
    """Exemplos de treino e de avaliação, com o prompt de sistema do chat e a lista de ferramentas."""
    system = system_prompt(today, [f"{n} ({uf})" for n, uf in municipalities])
    examples = synthetic_examples(Context(municipalities, first_year, last_year))
    examples += conversation_examples(database)
    train = [
        {"messages": e.messages(system), "tools": TOOLS, "source": e.source} for e in examples if e.split == "treino"
    ]
    evaluation = [
        {"question": e.question, "tool": e.tool, "arguments": e.arguments, "source": e.source, "system": system}
        for e in examples
        if e.split == "avaliacao"
    ]
    # embaralhada: um limite na avaliação ainda pega todos os tipos de pergunta
    random.Random(SEED).shuffle(evaluation)
    return train, evaluation


def write_jsonl(path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
