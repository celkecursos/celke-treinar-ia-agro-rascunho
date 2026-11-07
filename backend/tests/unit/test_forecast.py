import random

import pytest

from app.services.forecast_model import fit, leave_one_out, mae, solve, train
from app.services.forecast_service import ibge_comparison


def test_solve_linear_system():
    assert solve([[2, 1], [1, 3]], [5, 10]) == pytest.approx([1, 3])
    with pytest.raises(ValueError):
        solve([[1, 2], [2, 4]], [1, 2])


def test_fit_recovers_coefficients():
    rows = [[2000 + i, (i * 37) % 11] for i in range(20)]
    target = [100 + 3 * r[0] - 2 * r[1] for r in rows]
    model = fit(rows, target)
    assert model.coefficients == pytest.approx((3, -2), abs=1e-3)
    assert model.predict([2030, 5]) == pytest.approx(100 + 3 * 2030 - 10, abs=0.5)


def test_leave_one_out_never_sees_the_season():
    rows = [[float(i)] for i in range(10)]
    target = [2.0 * i for i in range(10)]
    target[5] = 100.0  # um ano fora do padrão
    backtest = leave_one_out(rows, target, list(range(10)))
    # o modelo que prevê o ano 5 não o viu: erra feio nele
    assert abs(backtest[5].predicted - 100) > 50


def samples(rain_effect: float, noise: float = 30, n: int = 25):
    rng = random.Random(7)
    items = []
    for i in range(n):
        rain = 800 + rng.uniform(-300, 300)
        dry = rng.uniform(0, 20)
        items.append(
            {
                "ano": 2000 + i,
                "rendimento": 3000 + 40 * i + rain_effect * (rain - 800) + rng.gauss(0, noise),
                "chuva_safra": rain,
                "veranico": dry,
            }
        )
    return items


def test_train_picks_the_rain_that_matters():
    result = train(samples(rain_effect=2.0), ["chuva_safra", "veranico"], min_samples=8)
    assert result is not None
    assert "chuva_safra" in result.features
    assert result.gain_pct > 50
    assert result.error < result.baseline_error
    assert result.candidates == 4  # tendência, 2 variáveis sozinhas e 1 par


def test_train_keeps_trend_only_when_rain_does_not_help():
    result = train(samples(rain_effect=0.0), ["chuva_safra", "veranico"], min_samples=8)
    assert result is not None
    assert result.features == ()
    assert mae(result.backtest) == pytest.approx(mae(result.baseline_backtest))


def test_train_needs_enough_seasons():
    assert train(samples(1.0, n=5), ["chuva_safra"], min_samples=8) is None


def test_forecast_after_registration(client, registered):
    view = client.get("/api/forecasts/5218805/soja").json()
    assert view["latest"]["trigger"] == "coleta"
    result = view["latest"]["result"]
    assert result["uses_rain"] is True  # os dados sintéticos acompanham a chuva da safra
    assert result["equation"].startswith("rendimento (kg/ha) = ")
    assert "+ -" not in result["equation"]
    assert result["error_kg_ha"] < result["baseline_error_kg_ha"]
    assert len(result["backtest"]) == result["seasons_used"]
    assert view["latest"]["explanation"] == "Explicação de teste."
    # hoje (dez/2024) a janela da soja 2025 está em andamento: previsão com cenários
    current = next(f for f in result["forecasts"] if f["season_year"] == 2025)
    assert current["status"] == "em_andamento"
    assert [s["name"] for s in current["scenarios"]] == ["seco", "normal", "chuvoso"]
    assert current["low_kg_ha"] <= current["predicted_kg_ha"] <= current["high_kg_ha"]
    assert current["ibge_state_kg_ha"] is None  # a estimativa sintética é de 2024
    assert [c["tipo"] for c in result["charts"]] == ["linha", "barras"]
    assert view["history"][0]["features"]


def test_ibge_comparison_comes_computed():
    # casos em que o modelo, comparando sozinho, trocou a direção ou usou o erro do modelo no lugar
    assert ibge_comparison(4127, 3783) == (9.1, "acima")
    assert ibge_comparison(2934, 1887) == (55.5, "acima")
    assert ibge_comparison(3455, 3879) == (-10.9, "abaixo")
    assert ibge_comparison(3879, 3879) == (0.0, "igual")


def test_train_button_and_history(client, registered):
    assert client.post("/api/forecasts/train").status_code == 202
    view = client.get("/api/forecasts/5218805/milho").json()
    assert view["latest"]["trigger"] == "botao"
    assert len(view["history"]) >= 2


def test_forecast_tool(container, registered):
    result = container.chat._tools.run("previsao_safra", {"municipio": "Rio Verde", "cultura": "soja"})
    assert result.ok
    assert result.content["erro_medio_do_modelo_pct"] < result.content["erro_medio_so_tendencia_pct"]
    assert result.content["previsoes"]


def test_forecast_of_unknown_municipality(client):
    assert client.get("/api/forecasts/1234567/soja").status_code == 404


def test_train_button_only_trains_the_selected_pair(client, registered):
    before = {crop: len(client.get(f"/api/forecasts/5218805/{crop}").json()["history"]) for crop in ("soja", "milho")}
    assert client.post("/api/forecasts/5218805/milho/train").status_code == 202
    milho = client.get("/api/forecasts/5218805/milho").json()
    assert len(milho["history"]) == before["milho"] + 1
    assert milho["latest"]["trigger"] == "botao"
    assert len(client.get("/api/forecasts/5218805/soja").json()["history"]) == before["soja"]


def test_train_button_validates_municipality_and_crop(client, registered):
    assert client.post("/api/forecasts/1234567/milho/train").status_code == 404
    assert client.post("/api/forecasts/5218805/arroz/train").status_code == 404
