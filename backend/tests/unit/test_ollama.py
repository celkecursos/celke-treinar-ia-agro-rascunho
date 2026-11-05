from app.core.errors import ModelNotInstalledError, OllamaUnavailableError
from app.repositories.setting_repository import SettingRepository
from app.services.model_selector import ModelSelector
from tests.fakes import ImmediateExecutor


def test_default_is_local(client):
    data = client.get("/api/ollama").json()
    assert data["location"] == "local"
    assert data["chat_model"] == {"name": "qwen3:8b", "installed": True, "tools": True}
    assert [s["location"] for s in data["servers"]] == ["local", "externo"]
    assert all(s["configured"] and s["online"] for s in data["servers"])
    assert data["servers"][0]["models"] == [{"name": "qwen3:8b", "size_gb": 5.2, "parameter_size": "8.2B"}]


def test_without_external_gpu(client, gpu):
    gpu.configured = False
    data = client.get("/api/status").json()["ollama"]
    assert data["location"] == "local"
    external = data["servers"][1]
    assert external["configured"] is False
    assert "Cadastre o servidor" in external["error"]
    response = client.post("/api/ollama/selection", json={"location": "externo", "model": "qwen3:8b"})
    assert response.status_code == 422
    assert "não cadastrada" in response.json()["erro"]["mensagem"]


def test_external_gpu_disconnected(client, gpu, selector):
    gpu.connected, gpu.message = False, "Sem conexão com root@203.0.113.10"
    selector.select("local", "qwen3:8b")
    data = client.get("/api/ollama").json()
    assert data["online"] is True
    assert data["servers"][1]["online"] is False
    assert data["servers"][1]["error"] == "Sem conexão com root@203.0.113.10"
    response = client.post("/api/ollama/selection", json={"location": "externo", "model": "qwen3:8b"})
    assert response.status_code == 503


def test_select_saves_choice_and_routes_calls(client, ollama_servers, selector, gpu, database):
    ollama_servers["externo"].models["qwen3:32b"] = ["completion", "tools"]
    response = client.post("/api/ollama/selection", json={"location": "externo", "model": "qwen3:32b"})
    assert response.status_code == 200, response.text
    assert response.json()["chat_model"]["name"] == "qwen3:32b"

    assert list(selector.chat_stream([{"role": "user", "content": "oi"}]))[0].text == "externo:qwen3:32b"
    response = client.post("/api/ollama/selection", json={"location": "local", "model": "qwen3:8b"})
    assert response.json()["location"] == "local"
    assert selector.name == "qwen3:8b"
    selector.chat_json([], {})
    assert ollama_servers["local"].chat_calls == ["qwen3:8b"]

    # a escolha fica no banco: um backend novo (reiniciado) continua com ela, e lembra o modelo de cada Ollama
    restarted = ModelSelector(ollama_servers, gpu, SettingRepository(database), "qwen3:8b", ImmediateExecutor())  # type: ignore[arg-type]
    assert restarted.current() == ("local", "qwen3:8b")
    assert restarted.status().servers[1].chat_model == "qwen3:32b"


def test_saved_external_choice_falls_back_to_local(selector, gpu):
    selector.select("externo", "qwen3:8b")
    assert selector.current() == ("externo", "qwen3:8b")
    gpu.configured = False  # servidor removido no painel
    assert selector.current() == ("local", "qwen3:8b")


def test_select_rejects_missing_model_and_model_without_tools(client, ollama_servers):
    response = client.post("/api/ollama/selection", json={"location": "local", "model": "qwen3:14b"})
    assert response.status_code == 422
    assert "não está instalado" in response.json()["erro"]["mensagem"]

    ollama_servers["local"].models["gemma3:4b"] = ["completion"]
    response = client.post("/api/ollama/selection", json={"location": "local", "model": "gemma3:4b"})
    assert response.status_code == 422
    assert "ferramentas" in response.json()["erro"]["mensagem"]

    response = client.post("/api/ollama/selection", json={"location": "local", "model": "qwen3; rm -rf /"})
    assert response.status_code == 422


def test_select_with_offline_server(client, ollama_servers, selector):
    selector.select("externo", "qwen3:8b")
    ollama_servers["externo"].error = OllamaUnavailableError("GPU externa desligada")
    response = client.post("/api/ollama/selection", json={"location": "externo", "model": "qwen3:8b"})
    assert response.status_code == 503
    data = client.get("/api/ollama").json()
    assert data["online"] is False
    assert data["error"] == "GPU externa desligada"
    assert data["servers"][0]["online"] is True


def test_pull_downloads_model(client, ollama_servers):
    response = client.post("/api/ollama/pull", json={"location": "externo", "model": "qwen3:14b"})
    assert response.status_code == 202, response.text
    pull = client.get("/api/ollama").json()["servers"][1]["pull"]
    assert pull == {"model": "qwen3:14b", "status": "concluido", "message": "Modelo baixado", "percent": 100.0}
    assert "qwen3:14b" in ollama_servers["externo"].models
    response = client.post("/api/ollama/selection", json={"location": "externo", "model": "qwen3:14b"})
    assert response.status_code == 200


def test_pull_error_keeps_progress(client, ollama_servers):
    ollama_servers["local"].pull_error = ModelNotInstalledError("O modelo qwen9 não existe na biblioteca do Ollama.")
    client.post("/api/ollama/pull", json={"location": "local", "model": "qwen9"})
    pull = client.get("/api/ollama").json()["servers"][0]["pull"]
    assert pull["status"] == "erro"
    assert pull["percent"] == 50.0
    assert "não existe" in pull["message"]


def test_pull_conflict(client, selector):
    from app.schemas.status import PullStatus

    selector._pulls["local"] = PullStatus(model="qwen3:14b", status="baixando")
    response = client.post("/api/ollama/pull", json={"location": "local", "model": "qwen3:32b"})
    assert response.status_code == 409
