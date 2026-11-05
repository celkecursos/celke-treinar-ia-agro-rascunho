def test_analysis_has_seasons_indicators_and_charts(client, registered):
    data = client.get("/api/analyses/5218805/soja").json()
    assert data["crop_name"] == "Soja"
    assert data["window"] == "out a mar"
    assert [c["tipo"] for c in data["charts"]] == [
        "combinado",
        "dispersao",
        "barras",
        "linha",
        "linha",
        "mapa_calor",
        "barras",
    ]
    season = next(s for s in data["seasons"] if s["year"] == 2020)
    assert season["rain_mm"] > 0
    assert season["rain_state_mm"] > 0
    assert season["yield_state_kg_ha"] > 0
    assert season["yield_brazil_kg_ha"] > 0
    assert data["correlation"]["n"] >= 10
    assert data["indicators"][0]["rotulo"].startswith("Chuva da safra")


def test_analysis_errors(client, registered):
    assert client.get("/api/analyses/5218805/arroz").status_code == 404
    assert client.get("/api/analyses/1234567/soja").status_code == 404


def test_estimates(client, registered):
    items = client.get("/api/estimates").json()["items"]
    assert items[0]["territory_name"] == "Brasil"
    soja = next(e for e in items if e["product"] == "soja" and e["level"] == "uf")
    assert soja["territory_name"] == "Goiás"
    assert soja["period_label"] == "nov/2024"
    assert soja["expected_yield_kg_ha"] > 0


def test_status(client):
    data = client.get("/api/status").json()
    assert data["backend"]["online"] is True
    assert data["database"]["online"] is True
    assert data["database"]["vector_version"].startswith("0.8.")
    assert data["ollama"]["chat_model"]["tools"] is True
    assert data["scheduler"]["enabled"] is False
    assert client.get("/api/health").json() == {"status": "ok"}
