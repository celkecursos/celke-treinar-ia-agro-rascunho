import pytest

from app.services.tools import TOOLS, correlation_words


@pytest.fixture
def tools(container, registered):
    return container.chat._tools


def test_every_tool_is_declared_with_parameters():
    names = [t["function"]["name"] for t in TOOLS]
    assert len(names) == len(set(names)) == 10
    for tool in TOOLS:
        assert tool["type"] == "function"
        assert tool["function"]["parameters"]["type"] == "object"


def test_rain_by_month_with_normals(tools):
    result = tools.run(
        "consultar_chuva", {"municipio": "rio verde", "inicio": "2023-10-01", "fim": "2024-03-31", "agrupamento": "mes"}
    )
    assert result.ok
    assert len(result.content["por_mes"]) == 6
    assert result.content["dias_com_dado"] == result.content["dias_no_periodo"] == 183
    assert set(result.content["media_historica_do_mes_mm"]) == {f"{m:02d}" for m in range(1, 13)}


def test_invalid_arguments_are_explained(tools):
    assert "Argumento inválido" in tools.run("consultar_chuva", {"municipio": "Rio Verde"}).summary
    assert not tools.run("consultar_chuva", {"municipio": "Rio Verde", "inicio": "2024-02-01", "fim": "2024-01-01"}).ok
    result = tools.run(
        "consultar_chuva", {"municipio": "Rio Verde", "inicio": "2023-01-01", "fim": "2024-01-01", "agrupamento": "dia"}
    )
    assert "máximo" in result.summary
    assert not tools.run("ferramenta_inventada", {}).ok


def test_optional_null_arguments_are_ignored(tools):
    result = tools.run("chuva_da_safra", {"municipio": "Rio Verde", "uf": None, "cultura": "soja", "ano_inicio": ""})
    assert result.ok
    assert result.content["janela"] == "outubro a março"


def test_production_at_each_level(tools):
    city = tools.run("consultar_producao", {"cultura": "soja", "nivel": "municipio", "municipio": "Rio Verde"})
    state = tools.run("consultar_producao", {"cultura": "soja", "nivel": "uf", "uf": "GO"})
    country = tools.run("consultar_producao", {"cultura": "milho", "nivel": "brasil", "ano_inicio": 2020})
    assert city.ok and state.ok and country.ok
    assert city.content["anos"][-1]["desvio_da_tendencia_pct"] is not None
    assert state.content["territorio"] == "Goiás"
    assert [a["ano"] for a in country.content["anos"]] == [2020, 2021, 2022, 2023, 2024]


def test_correlation_comes_computed(tools):
    result = tools.run("correlacao_chuva_rendimento", {"municipio": "Rio Verde", "cultura": "soja"})
    assert result.ok
    assert result.content["r"] > 0.5  # os dados sintéticos acompanham a chuva da safra
    assert "correlação" in result.content["leitura"]
    assert len(result.content["safras_mais_abaixo_da_tendencia"]) == 3


def test_estimate_by_state(tools):
    result = tools.run("estimativa_safra", {"cultura": "milho", "uf": "GO"})
    assert result.ok
    assert {e["product"] for e in result.content["estimativas"]} == {"milho_1", "milho_2"}
    assert not tools.run("estimativa_safra", {"cultura": "soja", "uf": "PR"}).ok


def test_chart_tool(tools):
    result = tools.run("mostrar_grafico", {"tipo": "mapa_de_calor", "municipio": "Rio Verde"})
    assert result.chart["tipo"] == "mapa_calor"


def test_correlation_words():
    assert correlation_words(0.65, 0.01) == "correlação forte e positiva, estatisticamente significativa (p < 0,05)"
    assert correlation_words(-0.1, 0.5).startswith("correlação muito fraca e negativa")


def test_correlation_of_one_month(tools):
    result = tools.run(
        "correlacao_chuva_rendimento",
        {"municipio": "Rio Verde", "cultura": "milho", "variavel": "chuva_do_mes", "mes": 4},
    )
    assert result.ok
    assert result.content["variavel"] == "chuva de abril"
    outside = tools.run(
        "correlacao_chuva_rendimento",
        {"municipio": "Rio Verde", "cultura": "milho", "variavel": "chuva_do_mes", "mes": 8},
    )
    assert not outside.ok
    assert "janeiro, fevereiro, março, abril" in outside.summary
