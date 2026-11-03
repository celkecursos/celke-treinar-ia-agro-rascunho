from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

MunicipalityStatus = Literal["coletando", "pronto", "erro"]


class MunicipalityCreate(BaseModel):
    code: int = Field(ge=1_000_000, le=9_999_999, description="Código IBGE do município (7 dígitos).")


class Municipality(BaseModel):
    code: int
    name: str
    state: str
    state_code: int
    latitude: float
    longitude: float
    principal: bool
    status: MunicipalityStatus
    status_message: str | None = None
    created_at: datetime
    rain_first_day: date | None = None
    rain_last_day: date | None = None
    rain_days: int = 0
    production_last_year: int | None = None


class MunicipalityList(BaseModel):
    items: list[Municipality]


class IbgeMunicipality(BaseModel):
    code: int
    name: str


class IbgeMunicipalityList(BaseModel):
    items: list[IbgeMunicipality]
