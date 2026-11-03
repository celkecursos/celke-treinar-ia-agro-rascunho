from datetime import date

import pytest

from app.core.errors import SourceUnavailableError
from tests.fakes import DeferredExecutor


def runs(client):
    return client.get("/api/collections").json()["runs"]


def test_register_downloads_history_references_and_production(client, registered, rain, ibge):
    assert registered["name"] == "Rio Verde"
    assert registered["state"] == "GO"
    assert registered["principal"] is True
    assert registered["status"] == "pronto"
    assert registered["rain_first_day"] == "2010-01-01"
    assert registered["production_last_year"] == 2024
    # a chuva média da UF usa os municípios que mais plantam soja (Jataí e Mineiros), só como referência
    assert client.get("/api/municipalities").json()["items"] == [registered]
    assert {c[2] for c in rain.archive_calls} == {date(2010, 1, 1)}
    assert len(rain.archive_calls) == 3
    levels = {call[0] for call in ibge.pam_calls}
    assert levels == {"municipio", "uf", "brasil"}
    assert {(r["source"], r["trigger"], r["status"]) for r in runs(client)} == {
        ("chuva", "cadastro", "concluida"),
        ("producao", "cadastro", "concluida"),
        ("estimativa", "cadastro", "concluida"),
    }


def test_register_twice_is_refused(client, registered):
    response = client.post("/api/municipalities", json={"code": 5218805})
    assert response.status_code == 409
    assert "já está cadastrado" in response.json()["erro"]["mensagem"]


def test_register_reference_municipality_reuses_its_data(client, registered, rain):
    calls = len(rain.archive_calls)
    response = client.post("/api/municipalities", json={"code": 5211909})
    assert response.status_code == 201
    assert response.json()["principal"] is True
    # Jataí já tinha a chuva como referência: só os dias que faltam são buscados
    assert all(c[2] > date(2024, 1, 1) for c in rain.archive_calls[calls:])


def test_register_without_coordinates(client, rain):
    rain.coordinates.pop("Londrina")
    response = client.post("/api/municipalities", json={"code": 4113700})
    assert response.status_code == 422
    assert "coordenadas" in response.json()["erro"]["mensagem"]


def test_register_error_is_shown_on_the_municipality(client, rain):
    rain.error = SourceUnavailableError("Não foi possível acessar o Open-Meteo.")
    m = client.post("/api/municipalities", json={"code": 5218805}).json()
    assert m["status"] == "erro"
    assert "Open-Meteo" in m["status_message"]
    assert runs(client)[0]["status"] == "erro"


def test_button_collects_only_missing_days(client, registered, rain):
    calls = len(rain.archive_calls)
    response = client.post("/api/collections/chuva")
    assert response.status_code == 202
    assert response.json()["trigger"] == "botao"
    # o arquivo já tinha tudo até 5 dias atrás: só busca do dia seguinte em diante
    assert all(c[2] > date(2024, 12, 1) for c in rain.archive_calls[calls:])


def test_button_without_news_says_it_is_up_to_date(client, registered):
    client.post("/api/collections/producao")
    last = runs(client)[0]
    assert last["source"] == "producao"
    assert last["status"] == "sem_novidade"
    assert last["message"] == "Já está atualizado: último ano disponível 2024."


def test_button_brings_new_year(client, registered, ibge):
    ibge.last_year = 2025
    client.post("/api/collections/producao")
    last = runs(client)[0]
    assert last["status"] == "concluida"
    assert client.get(f"/api/municipalities/{registered['code']}").json()["production_last_year"] == 2025


def test_button_needs_a_municipality(client):
    response = client.post("/api/collections/chuva")
    assert response.status_code == 422
    assert "Cadastre um município" in response.json()["erro"]["mensagem"]


def test_one_collection_per_source_at_a_time(client, registered, container):
    deferred = DeferredExecutor()
    container.collections._executor = deferred
    assert client.post("/api/collections/chuva").status_code == 202
    overview = client.get("/api/collections").json()
    assert next(s for s in overview["sources"] if s["source"] == "chuva")["running"] is True
    second = client.post("/api/collections/chuva")
    assert second.status_code == 409
    assert "em andamento" in second.json()["erro"]["mensagem"]
    # outra fonte pode coletar ao mesmo tempo
    assert client.post("/api/collections/estimativa").status_code == 202
    deferred.run_all()
    assert client.post("/api/collections/chuva").status_code == 202


def test_overview_shows_last_data_and_schedule(client, registered):
    sources = {s["source"]: s for s in client.get("/api/collections").json()["sources"]}
    assert sources["chuva"]["last_data"] == "14/12/2024"
    assert sources["producao"]["last_data"] == "2024"
    assert sources["estimativa"]["last_data"] == "nov/2024"
    assert sources["chuva"]["schedule"] == "Agendamento desligado"


def test_remove_municipality_keeps_references_of_other_registered(client, registered, container):
    client.post("/api/municipalities", json={"code": 5211909})
    assert client.delete("/api/municipalities/5218805").status_code == 204
    codes = container.municipalities.codes()
    assert 5218805 not in codes
    assert 5211909 in codes  # cadastrado e referência
    assert client.delete("/api/municipalities/5211909").status_code == 204
    assert container.municipalities.codes() == []
    assert client.delete("/api/municipalities/5211909").status_code == 404


def test_state_municipalities_from_ibge(client):
    items = client.get("/api/ibge/states/go/municipalities").json()["items"]
    assert {"code": 5218805, "name": "Rio Verde"} in items
    assert client.get("/api/ibge/states/XX/municipalities").status_code == 404


@pytest.mark.parametrize("code", [123, 99999999])
def test_invalid_code(client, code):
    assert client.post("/api/municipalities", json={"code": code}).status_code == 422
