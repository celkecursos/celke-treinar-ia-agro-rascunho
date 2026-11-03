from app.core.errors import ModelNotInstalledError
from app.services.ollama_service import ChatChunk
from tests.fakes import tool_call
from tests.helpers import ask, parse_sse


def names(events):
    return [name for name, _ in events]


def test_chat_calls_tool_then_answers(client, registered, model):
    model.rounds = [
        [tool_call("consultar_chuva", municipio="Rio Verde", uf="GO", inicio="2024-01-01", fim="2024-01-31")],
        [ChatChunk("content", "Choveu bastante "), ChatChunk("content", "em janeiro (Open-Meteo).")],
    ]
    events = parse_sse(ask(client, "Quanto choveu em Rio Verde em janeiro de 2024?").text)
    assert names(events) == ["conversation", "tool_call", "tool_result", "token", "token", "done"]
    result = events[2][1]
    assert result["ok"] is True
    assert result["name"] == "consultar_chuva"
    assert result["source"] == "Open-Meteo (reanálise ERA5)"
    # o resultado da ferramenta volta ao modelo como mensagem `tool`, com o total já calculado
    messages, tools = model.chat_calls[1]
    assert tools is not None
    assert messages[-1]["role"] == "tool"
    assert '"total_mm"' in messages[-1]["content"]
    assert messages[-2]["tool_calls"][0]["function"]["name"] == "consultar_chuva"
    conversation = client.get(f"/api/conversations/{events[0][1]['id']}").json()
    assert conversation["messages"][1]["content"] == "Choveu bastante em janeiro (Open-Meteo)."
    assert conversation["messages"][1]["tool_calls"][0]["summary"].startswith("Chuva em Rio Verde (GO)")


def test_system_prompt_has_date_and_registered_municipalities(client, registered, model):
    ask(client, "Oi")
    system = model.chat_calls[0][0][0]
    assert system["role"] == "system"
    assert "2024-12-15" in system["content"]
    assert "Rio Verde (GO)" in system["content"]
    assert "Não invente nem estime números" in system["content"]


def test_chat_shows_chart_from_tool(client, registered, model):
    model.rounds = [[tool_call("mostrar_grafico", tipo="chuva_x_rendimento", municipio="Rio Verde", cultura="soja")]]
    events = parse_sse(ask(client, "Mostre a chuva e o rendimento").text)
    chart = next(data for name, data in events if name == "chart")
    assert chart["tipo"] == "combinado"
    conversation = client.get(f"/api/conversations/{events[0][1]['id']}").json()
    assert conversation["messages"][1]["charts"][0]["tipo"] == "combinado"


def test_tool_error_goes_back_to_the_model(client, registered, model):
    model.rounds = [[tool_call("consultar_chuva", municipio="Cidade Nenhuma", inicio="2024-01-01", fim="2024-01-31")]]
    events = parse_sse(ask(client, "Quanto choveu em Cidade Nenhuma?").text)
    result = next(data for name, data in events if name == "tool_result")
    assert result["ok"] is False
    assert "não está cadastrado" in result["summary"]
    assert "não está cadastrado" in model.chat_calls[1][0][-1]["content"]


def test_last_round_has_no_tools(client, registered, model, settings):
    model.rounds = [[tool_call("listar_municipios")] for _ in range(settings.max_tool_rounds)]
    events = parse_sse(ask(client, "Liste").text)
    assert names(events).count("tool_call") == settings.max_tool_rounds
    assert model.chat_calls[-1][1] is None
    assert events[-1] == ("done", {})


def test_thinking_is_announced_once_and_not_shown(client, model):
    events = parse_sse(ask(client, "Oi").text)
    assert names(events).count("thinking") == 1
    answer = "".join(d["text"] for n, d in events if n == "token")
    assert "pensando" not in answer


def test_empty_answer_gets_a_message(client, model):
    model.rounds = [[]]
    events = parse_sse(ask(client, "Oi").text)
    assert "Não consegui responder" in "".join(d["text"] for n, d in events if n == "token")


def test_error_is_saved_and_retry_regenerates(client, model):
    model.error = ModelNotInstalledError("O modelo não está instalado.")
    events = parse_sse(ask(client, "Oi").text)
    assert events[-1][0] == "error"
    conversation_id = events[0][1]["id"]
    assert client.get(f"/api/conversations/{conversation_id}").json()["messages"][1]["state"] == "erro"
    model.error = None
    events = parse_sse(ask(client, "Oi", conversation_id=conversation_id, retry=True).text)
    assert events[-1] == ("done", {})
    messages = client.get(f"/api/conversations/{conversation_id}").json()["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[1]["state"] == "concluida"


def test_history_comes_from_the_database(client, model, settings):
    first = parse_sse(ask(client, "Primeira").text)
    conversation_id = first[0][1]["id"]
    ask(client, "Segunda", conversation_id=conversation_id)
    messages = model.chat_calls[-1][0]
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    assert messages[1]["content"] == "Primeira"


def test_conversations_list_and_delete(client):
    conversation_id = parse_sse(ask(client, "Pergunta").text)[0][1]["id"]
    assert client.get("/api/conversations").json()["items"][0]["id"] == conversation_id
    assert client.delete(f"/api/conversations/{conversation_id}").status_code == 204
    assert client.get(f"/api/conversations/{conversation_id}").status_code == 404
