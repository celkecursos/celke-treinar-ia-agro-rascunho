from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.schemas.analyses import Chart


class Discovery(BaseModel):
    id: str
    municipality_code: int
    municipality_name: str
    crop: str
    kind: str
    title: str
    fact: str
    stats: dict[str, Any]
    chart: Chart | None = None
    interpretation: str | None = None
    hypothesis: str | None = None


class DiscoveryReport(BaseModel):
    id: str
    status: Literal["gerando", "pronto", "erro"]
    model: str
    tests: int
    summary: str | None = None
    next_questions: list[str] = []
    error_message: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
    discoveries: list[Discovery] = []


class Alert(BaseModel):
    id: str
    municipality_code: int
    municipality_name: str
    crop: str
    kind: str
    season_year: int
    severity: Literal["warn", "err"]
    title: str
    message: str
    facts: dict[str, Any]
    chart: Chart | None = None
    explanation: str | None = None
    active: bool
    created_at: datetime
    updated_at: datetime


class AlertList(BaseModel):
    items: list[Alert]
