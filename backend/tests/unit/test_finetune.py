from datetime import date
from types import SimpleNamespace

from app.finetune.dataset import TEMPLATES, Context, build_dataset, synthetic_examples
from app.finetune.evaluate import evaluate, score
from app.services.tools import TOOLS

PLACES = [("Rio Verde", "GO"), ("Londrina", "PR")]


def test_every_template_targets_a_real_tool_with_valid_arguments(container):
    names = {t["function"]["name"] for t in TOOLS}
    examples = synthetic_examples(Context(PLACES, 2000, 2025))
    assert {e.tool for e in examples} <= names
    assert {e.source for e in examples} == {t[0] for t in TEMPLATES}
    # os argumentos passam na validação das próprias ferramentas
    executor = container.chat._tools
    for e in examples:
        model, _ = executor._handlers[e.tool]
        model(**e.arguments)


def test_last_phrase_of_each_template_is_only_in_evaluation():
    examples = synthetic_examples(Context(PLACES, 2000, 2025))
    train = {e.question for e in examples if e.split == "treino"}
    evaluation = [e for e in examples if e.split == "avaliacao"]
    assert evaluation
    assert not train & {e.question for e in evaluation}
    for template_id, _, phrases in TEMPLATES:
        start = phrases[-1].split("{")[0]
        assert all(e.question.startswith(start) for e in evaluation if e.source == template_id)


def test_soy_season_label_maps_to_harvest_year():
    examples = [e for e in synthetic_examples(Context(PLACES, 2000, 2025)) if e.tool == "chuva_da_safra"]
    soy = next(e for e in examples if e.arguments["cultura"] == "soja")
    year = soy.arguments["ano_inicio"]
    assert f"{year - 1}/{str(year)[2:]}" in soy.question


def test_dataset_uses_chat_system_prompt_and_real_conversations(container, registered, model, client):
    from tests.fakes import tool_call
    from tests.helpers import ask

    model.rounds = [[tool_call("listar_municipios")]]
    ask(client, "Quais cidades você conhece?")
    train, evaluation = build_dataset(container.database, PLACES, 2000, 2025, date(2024, 12, 15))
    first = train[0]["messages"]
    assert [m["role"] for m in first] == ["system", "user", "assistant"]
    assert "Rio Verde (GO)" in first[0]["content"]
    assert first[2]["tool_calls"][0]["function"]["name"]
    assert train[0]["tools"] == TOOLS
    real = [row for row in train if row["source"] == "conversa"]
    assert real[0]["messages"][1]["content"] == "Quais cidades você conhece?"
    assert evaluation[0]["system"] == first[0]["content"]


def test_score_ignores_extra_arguments_and_accents():
    assert score(
        "previsao_safra",
        {"municipio": "Jataí", "cultura": "soja"},
        "previsao_safra",
        {"municipio": "jatai", "cultura": "soja", "uf": "GO"},
    ) == (True, True)
    assert score(
        "previsao_safra",
        {"municipio": "Jataí", "cultura": "soja"},
        "previsao_safra",
        {"municipio": "Jataí", "cultura": "milho"},
    ) == (True, False)
    assert score("consultar_chuva", {"ano_inicio": 2024}, "chuva_da_safra", {}) == (False, False)
    assert score("chuva_da_safra", {"ano_inicio": 2024}, "chuva_da_safra", {"ano_inicio": "2024"}) == (True, True)


def test_evaluate_counts_hits_and_misses():
    def chat(**kwargs):
        question = kwargs["messages"][-1]["content"]
        call = SimpleNamespace(function=SimpleNamespace(name="listar_municipios", arguments={}))
        return SimpleNamespace(message=SimpleNamespace(tool_calls=[call] if "cidades" in question else []))

    items = [
        {
            "question": "Quais cidades?",
            "tool": "listar_municipios",
            "arguments": {},
            "source": "municipios",
            "system": "s",
        },
        {"question": "Há alertas?", "tool": "ver_alertas", "arguments": {}, "source": "alertas", "system": "s"},
    ]
    result = evaluate(SimpleNamespace(chat=chat), "teste", items).as_dict()
    assert result["ferramenta_e_argumentos_certos_pct"] == 50
    assert result["erros"][0]["recebido"]["ferramenta"] is None


def test_one_month_by_month_is_the_same_as_total():
    expected = {"municipio": "Rio Verde", "inicio": "2023-11-01", "fim": "2023-11-30", "agrupamento": "total"}
    got = {**expected, "agrupamento": "mes"}
    assert score("consultar_chuva", expected, "consultar_chuva", got) == (True, True)
    year = {**got, "inicio": "2023-01-01", "fim": "2023-12-31"}
    assert score(
        "consultar_chuva", {**expected, "inicio": "2023-01-01", "fim": "2023-12-31"}, "consultar_chuva", year
    ) == (True, False)


def test_phrases_use_the_right_article():
    for _, _, phrases in TEMPLATES:
        for phrase in phrases:
            assert "da {cultura}" not in phrase and "na {cultura}" not in phrase and " a {cultura}" not in phrase
