from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.analyses import Chart


class ModelFeature(BaseModel):
    key: str
    label: str
    unit: str
    # kg/ha a mais no rendimento para cada unidade a mais da variável
    coefficient: float


class BacktestRow(BaseModel):
    """Validação: cada safra prevista por um modelo treinado sem ela."""

    year: int
    actual: float
    predicted: float
    trend_only: float


class Scenario(BaseModel):
    name: Literal["seco", "normal", "chuvoso"]
    seasons: int
    rain_mm: float
    predicted_kg_ha: float


class SeasonForecast(BaseModel):
    season_year: int
    # chuva_completa = a janela já terminou e falta só o número do IBGE; em_andamento = ainda chove na janela
    status: Literal["chuva_completa", "em_andamento"]
    rain_until: date | None = None
    rain_mm: float | None = None
    predicted_kg_ha: float
    low_kg_ha: float
    high_kg_ha: float
    trend_kg_ha: float
    vs_trend_pct: float
    scenarios: list[Scenario] = []
    ibge_state_kg_ha: float | None = None
    ibge_period_label: str | None = None


class TrainedForecast(BaseModel):
    municipality_code: int
    municipality_name: str
    crop: str
    crop_name: str
    seasons_used: int
    first_year: int
    last_year: int
    features: list[ModelFeature]
    year_coefficient: float
    intercept: float
    equation: str
    uses_rain: bool
    candidates: int
    error_kg_ha: float
    error_pct: float
    baseline_error_kg_ha: float
    baseline_error_pct: float
    gain_pct: float
    backtest: list[BacktestRow]
    forecasts: list[SeasonForecast]
    charts: list[Chart]


class ForecastRecord(BaseModel):
    id: str
    trigger: Literal["coleta", "botao"]
    model: str
    trained_at: datetime
    explanation: str | None = None
    result: TrainedForecast


class ForecastHistoryItem(BaseModel):
    id: str
    trigger: Literal["coleta", "botao"]
    trained_at: datetime
    seasons_used: int
    features: list[str]
    error_pct: float
    baseline_error_pct: float


class ForecastView(BaseModel):
    latest: ForecastRecord | None = None
    history: list[ForecastHistoryItem] = []
    training: bool = False
