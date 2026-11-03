"""Especificações de gráfico, entregues pelo frontend aos componentes do Kole.

Formato comum: `tipo` (linha, barras, combinado, dispersao, mapa_calor), `titulo`, `descricao`, `dados` e as opções do
componente com nomes em português (`eixo_x`, `eixo_y`, `series`, `barras`, `linhas`, `referencias`, `faixas`…). O
frontend só troca o formato de nome (snake_case → camelCase do Kole); as contas já vêm feitas daqui.
"""

from datetime import date

from app.core.domain import MONTH_ABBR, Crop
from app.services.seasons import Month, MonthlyRain, Season

RAIN = {"rotulo": "Chuva", "unidade": "mm"}
YIELD = {"rotulo": "Rendimento", "unidade": "kg/ha"}


def _rows(seasons: list[Season], *fields: str) -> list[dict]:
    return [{"ano": str(s.year), **{f: getattr(s, f) for f in fields}} for s in seasons]


def rain_vs_yield(seasons: list[Season], crop: Crop, place: str) -> dict:
    """O gráfico central: chuva da janela em barras e rendimento (com a tendência) em linha, ano a ano."""
    return {
        "tipo": "combinado",
        "titulo": f"Chuva da safra × rendimento {crop.of} em {place}",
        "descricao": f"Chuva da janela da safra (barras) e rendimento {crop.of} por ano, com a tendência.",
        "dados": _rows(seasons, "rain_mm", "yield_kg_ha", "trend_kg_ha"),
        "eixo_x": {"chave": "ano", "tipo": "categoria", "rotulo": "Safra"},
        "eixo_y": RAIN,
        "eixo_y_direito": YIELD,
        "barras": [{"chave": "rain_mm", "rotulo": "Chuva da safra"}],
        "linhas": [
            {"chave": "yield_kg_ha", "rotulo": "Rendimento"},
            {"chave": "trend_kg_ha", "rotulo": "Tendência", "tracejada": True},
        ],
    }


def yield_comparison(seasons: list[Season], crop: Crop, place: str, state: str) -> dict:
    return {
        "tipo": "linha",
        "titulo": f"Rendimento {crop.of}: {place}, {state} e Brasil",
        "descricao": f"Rendimento médio {crop.of} por ano no município, na UF e no país.",
        "dados": _rows(seasons, "yield_kg_ha", "yield_state_kg_ha", "yield_brazil_kg_ha"),
        "eixo_x": {"chave": "ano", "tipo": "categoria", "rotulo": "Ano"},
        "eixo_y": YIELD,
        "series": [
            {"chave": "yield_kg_ha", "rotulo": place},
            {"chave": "yield_state_kg_ha", "rotulo": state},
            {"chave": "yield_brazil_kg_ha", "rotulo": "Brasil"},
        ],
    }


def yield_anomaly(seasons: list[Season], crop: Crop, place: str) -> dict:
    return {
        "tipo": "barras",
        "titulo": f"Rendimento {crop.of} acima ou abaixo da tendência em {place}",
        "descricao": "Diferença entre o rendimento de cada ano e o esperado pela tendência, em porcentagem.",
        "dados": _rows(seasons, "yield_anomaly_pct"),
        "eixo_x": {"chave": "ano", "tipo": "categoria", "rotulo": "Safra"},
        "eixo_y": {"rotulo": "Desvio da tendência", "unidade": "%"},
        "series": [{"chave": "yield_anomaly_pct", "rotulo": "Desvio"}],
        "divergente": True,
    }


def scatter(
    points: list[tuple[int, float, float]], crop: Crop, place: str, x_label: str, x_unit: str, note: str
) -> dict:
    """Cada ponto é uma safra: (ano, variável de chuva, desvio do rendimento em %)."""
    return {
        "tipo": "dispersao",
        "titulo": f"{x_label} × desvio do rendimento {crop.of} em {place}",
        "descricao": f"Cada ponto é uma safra: {x_label.lower()} no eixo horizontal e desvio do rendimento no vertical.",
        "dados": [{"ano": str(y), "x": x, "y": v, "ruim": v <= -10} for y, x, v in points],
        "eixo_x": {"rotulo": x_label, "unidade": x_unit},
        "eixo_y": {"rotulo": "Desvio da tendência", "unidade": "%"},
        "chave_x": "x",
        "chave_y": "y",
        "chave_rotulo": "ano",
        "chave_destaque": "ruim",
        "rotulo_pontos": "Safras",
        "rotulo_destaque": "10% ou mais abaixo da tendência",
        "regressao": True,
        "nota": note,
    }


def scatter_points(seasons: list[Season], field: str) -> list[tuple[int, float, float]]:
    return [
        (s.year, getattr(s, field), s.yield_anomaly_pct)
        for s in seasons
        if getattr(s, field) is not None and s.yield_anomaly_pct is not None
    ]


def monthly_rain(monthly: dict[Month, MonthlyRain], normals: dict[int, float], place: str, months: int = 24) -> dict:
    complete = [m for m, v in monthly.items() if v.complete][-months:]
    return {
        "tipo": "linha",
        "titulo": f"Chuva mensal em {place}",
        "descricao": f"Chuva de cada mês nos últimos {len(complete)} meses completos e a média histórica do mês.",
        "dados": [
            {"mes": f"{y}-{m:02d}", "chuva": monthly[(y, m)].total, "media": normals.get(m)} for y, m in complete
        ],
        "eixo_x": {"chave": "mes", "tipo": "data", "rotulo": "Mês"},
        "eixo_y": RAIN,
        "series": [
            {"chave": "chuva", "rotulo": "Chuva do mês"},
            {"chave": "media", "rotulo": "Média histórica do mês", "tracejada": True},
        ],
        "area": True,
    }


def season_progress(
    daily: list[tuple[date, float]], crop: Crop, start: date, normal_by_day: list[float], place: str
) -> dict:
    """Chuva acumulada da safra em andamento × média acumulada das safras passadas (usada nos alertas)."""
    rows = []
    acc = 0.0
    by_day = dict(daily)
    for i, normal in enumerate(normal_by_day):
        day = date.fromordinal(start.toordinal() + i)
        value = by_day.get(day)
        if value is not None:
            acc += value
        rows.append(
            {
                "dia": day.isoformat(),
                "acumulada": round(acc, 1) if value is not None else None,
                "normal": round(normal, 1),
            }
        )
    return {
        "tipo": "linha",
        "titulo": f"Chuva acumulada da safra de {crop.name.lower()} em {place}",
        "descricao": "Chuva acumulada desde o início da janela da safra e a média acumulada das safras passadas.",
        "dados": rows,
        "eixo_x": {"chave": "dia", "tipo": "data", "rotulo": "Dia"},
        "eixo_y": {"rotulo": "Chuva acumulada", "unidade": "mm"},
        "series": [
            {"chave": "acumulada", "rotulo": "Esta safra"},
            {"chave": "normal", "rotulo": "Média das safras passadas", "tracejada": True},
        ],
        "pontos": False,
    }


def heatmap(monthly: dict[Month, MonthlyRain], place: str) -> dict:
    years = sorted({y for y, _ in monthly}, reverse=True)
    return {
        "tipo": "mapa_calor",
        "titulo": f"Chuva por mês e ano em {place}",
        "descricao": "Cada célula é a chuva de um mês; meses incompletos ficam sem cor.",
        "linhas": [str(y) for y in years],
        "colunas": MONTH_ABBR,
        "valores": [
            {"linha": str(y), "coluna": MONTH_ABBR[m - 1], "valor": v.total if v.complete else None}
            for (y, m), v in monthly.items()
        ],
        "unidade": "mm",
        "rotulo_linhas": "Ano",
    }


def state_references(references: list[tuple[str, float]], state: str, year: int) -> dict:
    return {
        "tipo": "barras",
        "titulo": f"Municípios de referência da chuva média de {state}",
        "descricao": f"Os municípios que mais plantaram soja em {state} em {year}; a chuva da UF é a média deles, ponderada pela área.",
        "dados": [{"municipio": name, "area": area} for name, area in references],
        "eixo_x": {"chave": "municipio", "tipo": "categoria", "rotulo": "Município"},
        "eixo_y": {"rotulo": "Área plantada de soja", "unidade": "ha"},
        "series": [{"chave": "area", "rotulo": "Área plantada"}],
        "orientacao": "horizontal",
        "legenda": False,
    }
