from app.core.errors import OllamaUnavailableError


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
    assert report["summary"] == "Resumo de teste."
    assert report["next_questions"] == ["Pergunta 1?", "Pergunta 2?"]
    # o modelo recebe os fatos já calculados, como dado
    prompt = model.json_calls[-1][-1]["content"]
    assert prompt.startswith("<descobertas>")


def test_report_without_model_keeps_the_facts(client, registered, model):
    model.json_error = OllamaUnavailableError("O Ollama não respondeu.")
    assert client.post("/api/discoveries").status_code == 202
    report = client.get("/api/discoveries").json()
    assert report["status"] == "erro"
    assert report["error_message"] == "O Ollama não respondeu."
    assert report["discoveries"]
    assert report["discoveries"][0]["interpretation"] is None


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
