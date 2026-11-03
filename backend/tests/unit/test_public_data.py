from datetime import date

import httpx
import pytest

from app.core.errors import SourceUnavailableError
from app.services.public_data import Ibge, OpenMeteo, PublicDataClient, _strip_state


def client_for(handler, retries=0):
    return PublicDataClient(timeout=5, transport=httpx.MockTransport(handler), retries=retries)


def test_archive_skips_missing_days():
    def handler(request):
        assert request.url.host == "archive-api.open-meteo.com"
        assert request.url.params["daily"] == "precipitation_sum"
        return httpx.Response(
            200, json={"daily": {"time": ["2024-01-01", "2024-01-02"], "precipitation_sum": [3.5, None]}}
        )

    rain = OpenMeteo(client_for(handler)).archive(-17.8, -50.9, date(2024, 1, 1), date(2024, 1, 2))
    assert rain == [(date(2024, 1, 1), 3.5)]


def test_recent_leaves_out_today():
    def handler(request):
        return httpx.Response(
            200, json={"daily": {"time": ["2024-01-01", "2024-01-02"], "precipitation_sum": [1.0, 2.0]}}
        )

    assert OpenMeteo(client_for(handler)).recent(-17.8, -50.9, 10) == [(date(2024, 1, 1), 1.0)]


def test_geocode_matches_name_and_state():
    results = [
        {"name": "Rio Verde", "country_code": "US", "admin1": "Arizona", "latitude": 33.7, "longitude": -111.6},
        {
            "name": "Rio Verde",
            "country_code": "BR",
            "admin1": "Goiás",
            "latitude": -17.79,
            "longitude": -50.92,
            "population": 241494,
        },
        {"name": "Rio Verde", "country_code": "BR", "admin1": "Bahia", "latitude": -12.1, "longitude": -40.2},
    ]
    meteo = OpenMeteo(client_for(lambda r: httpx.Response(200, json={"results": results})))
    assert meteo.geocode("Rio Verde", "GO") == (-17.79, -50.92)
    assert meteo.geocode("Rio Verde", "PR") is None


def test_pam_parses_values_and_groups_by_year():
    header = {"D1C": "Município (Código)"}
    rows = [
        {"D1C": "5218805", "D2C": "214", "D3C": "2023", "D4C": "40124", "V": "1770300"},
        {"D1C": "5218805", "D2C": "112", "D3C": "2023", "D4C": "40124", "V": "4200"},
        {"D1C": "5218805", "D2C": "8331", "D3C": "2023", "D4C": "40124", "V": "..."},
        {"D1C": "5218805", "D2C": "214", "D3C": "2023", "D4C": "40122", "V": "-"},
        {"D1C": "5218805", "D2C": "112", "D3C": "2023", "D4C": "40122", "V": "0"},
    ]

    def handler(request):
        assert "/t/5457/n6/5218805/" in request.url.path
        assert "/p/2020-2023/" in request.url.path
        return httpx.Response(200, json=[header, *rows])

    result = {(c.crop, c.year): c for c in Ibge(client_for(handler)).pam("municipio", [5218805], 2020, 2023)}
    soja = result[("soja", 2023)]
    assert soja.production_t == 1770300
    assert soja.yield_kg_ha == 4200
    assert soja.planted_area_ha is None
    assert result[("milho", 2023)].production_t == 0
    assert result[("milho", 2023)].yield_kg_ha is None


def test_only_allowed_hosts():
    client = client_for(lambda r: httpx.Response(200, json={}))
    with pytest.raises(SourceUnavailableError, match="não permitido"):
        client.get_json("https://exemplo.com.br/x", source="teste")
    with pytest.raises(SourceUnavailableError, match="não permitido"):
        client.get_json("http://apisidra.ibge.gov.br/values", source="teste")


def test_retries_and_explains_errors(monkeypatch):
    monkeypatch.setattr("app.services.public_data.time.sleep", lambda _: None)
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503) if len(calls) < 2 else httpx.Response(200, json={"ok": True})

    assert client_for(handler, retries=2).get_json("https://apisidra.ibge.gov.br/values/x", source="o IBGE") == {
        "ok": True
    }
    with pytest.raises(SourceUnavailableError, match="limite de pedidos"):
        client_for(lambda r: httpx.Response(429), retries=1).get_json("https://apisidra.ibge.gov.br/v", source="o IBGE")


def test_strip_state_from_sidra_names():
    assert _strip_state("Rio Verde - GO") == "Rio Verde"
    assert _strip_state("Rio Verde (GO)") == "Rio Verde"
    assert _strip_state("Santa Rita do Trivelato - XY") == "Santa Rita do Trivelato"
