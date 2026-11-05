from app.core.errors import OllamaUnavailableError
from app.services.insight_service import INTERPRET_BATCH


def test_discoveries_after_registration(client, registered, model):
    report = client.get("/api/discoveries").json()
    assert report["status"] == "pronto"
    assert report["tests"] > 0
    kinds = [d["kind"] for d in report["discoveries"]]
    assert "correlacao" in kinds
    assert "tendencia" in kinds
    first = report["discoveries"][0]
    assert first["kind"] == "correlacao"
    assert first["chart"]["tipo"] == "dispersao"
    assert first["stats"]["q"] <= 0.10
    assert first["interpretation"] == "Interpretação d1"
    assert all(d["interpretation"] for d in report["discoveries"])
    assert report["summary"] == "Resumo de teste."
    assert report["next_questions"] == ["Pergunta 1?", "Pergunta 2?"]
    # o modelo recebe os fatos já calculados, como dado, em lotes pequenos e depois todos para o resumo
    # (as outras chamadas em JSON são dos alertas e do treino da previsão)
    prompts = [call[-1]["content"] for call in model.json_calls if call[-1]["content"].startswith("<descobertas>")]
    batches = [p.count("<descoberta ") for p in prompts[:-1]]
    assert len(batches) > 1 and max(batches) <= INTERPRET_BATCH
    assert prompts[-1].count("<descoberta ") == len(report["discoveries"])


def test_report_without_model_keeps_the_facts(client, registered, model):
    model.json_error = OllamaUnavailableError("O Ollama não respondeu.")
    assert client.post("/api/discoveries").status_code == 202
    report = client.get("/api/discoveries").json()
    assert report["status"] == "erro"
    assert report["error_message"] == "O Ollama não respondeu."
    assert report["discoveries"]
    assert report["discoveries"][0]["interpretation"] is None


def test_a_failed_batch_keeps_the_others(client, registered, model):
    original = model.chat_json
    calls = {"n": 0}

    def flaky(messages, schema):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OllamaUnavailableError("O Ollama demorou demais para responder.")
        return original(messages, schema)

    model.chat_json = flaky
    assert client.post("/api/discoveries").status_code == 202
    report = client.get("/api/discoveries").json()
    interpreted = [d for d in report["discoveries"] if d["interpretation"]]
    assert 0 < len(interpreted) < len(report["discoveries"])
    assert report["summary"] == "Resumo de teste."
    assert report["error_message"].startswith(f"A IA interpretou {len(interpreted)} de {len(report['discoveries'])}")


def test_no_discoveries_yet(client):
    response = client.get("/api/discoveries")
    assert response.status_code == 404
    assert "Ainda não há descobertas" in response.json()["erro"]["mensagem"]


def test_alerts_for_dry_season_in_progress(client, registered, container):
    # sem chuva desde novembro na safra de soja em andamento
    with container.database.connection() as conn:
        conn.execute("UPDATE weather_daily SET precipitation_mm = 0 WHERE day >= '2024-11-01'")
    container.insights.update_alerts()
    alerts = client.get("/api/alerts").json()["items"]
    kinds = {(a["crop"], a["kind"]) for a in alerts}
    assert ("soja", "chuva_abaixo") in kinds
    assert ("soja", "veranico") in kinds
    deficit = next(a for a in alerts if a["kind"] == "chuva_abaixo")
    assert deficit["severity"] == "err"
    assert deficit["facts"]["safra"] == 2025
    assert deficit["chart"]["tipo"] == "linha"
    assert deficit["explanation"] == "Explicação de teste."


def test_alerts_are_deactivated_when_they_stop(client, registered, container):
    with container.database.connection() as conn:
        conn.execute("UPDATE weather_daily SET precipitation_mm = 0 WHERE day >= '2024-11-01'")
    container.insights.update_alerts()
    assert client.get("/api/alerts").json()["items"]
    with container.database.connection() as conn:
        conn.execute("UPDATE weather_daily SET precipitation_mm = 30 WHERE day >= '2024-11-01'")
    container.insights.update_alerts()
    assert client.get("/api/alerts").json()["items"] == []
    assert client.get("/api/alerts?include_inactive=true").json()["items"]
