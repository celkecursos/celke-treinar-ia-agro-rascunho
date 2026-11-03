from typing import Any

from pydantic import BaseModel

from app.schemas.municipalities import Municipality

# Especificação de gráfico, no formato que o frontend entrega aos componentes do Kole (ver services/charts.py).
Chart = dict[str, Any]


class SeasonRow(BaseModel):
    """Uma safra: ano da colheita (PAM), chuva da janela e rendimento."""

    year: int
    rain_mm: float | None = None
    rain_state_mm: float | None = None
    rain_anomaly_pct: float | None = None
    dry_spell_days: int | None = None
    planting_rain_mm: float | None = None
    production_t: float | None = None
    yield_kg_ha: float | None = None
    yield_state_kg_ha: float | None = None
    yield_brazil_kg_ha: float | None = None
    trend_kg_ha: float | None = None
    yield_anomaly_pct: float | None = None


class Correlation(BaseModel):
    r: float
    p: float
    n: int


class IndicatorItem(BaseModel):
    rotulo: str
    valor: str
    descricao: str | None = None
    variacao: float | None = None
    variacao_boa: str | None = None
    tendencia: list[float] | None = None


class Analysis(BaseModel):
    municipality: Municipality
    crop: str
    crop_name: str
    window: str
    seasons: list[SeasonRow]
    correlation: Correlation | None = None
    indicators: list[IndicatorItem]
    charts: list[Chart]
    notes: list[str]


class Estimate(BaseModel):
    product: str
    product_name: str
    level: str
    territory_code: int
    territory_name: str
    period: int
    period_label: str
    production_t: float | None = None
    yield_kg_ha: float | None = None
    planted_area_ha: float | None = None
    harvested_area_ha: float | None = None
    # Comparação com o rendimento esperado pela tendência da PAM (só na soja e no milho total)
    expected_yield_kg_ha: float | None = None


class EstimateList(BaseModel):
    items: list[Estimate]
