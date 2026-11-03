from datetime import datetime
from typing import Literal

from pydantic import BaseModel

CollectionSource = Literal["chuva", "producao", "estimativa"]
CollectionTrigger = Literal["agendada", "botao", "cadastro"]
RunStatus = Literal["executando", "concluida", "sem_novidade", "erro"]


class CollectionRun(BaseModel):
    id: str
    source: CollectionSource
    trigger: CollectionTrigger
    status: RunStatus
    records: int
    message: str | None = None
    started_at: datetime
    finished_at: datetime | None = None


class SourceStatus(BaseModel):
    source: CollectionSource
    name: str
    provider: str
    schedule: str
    # Data do dado mais recente guardado: dia (chuva), ano (produção) ou mês do levantamento (estimativa)
    last_data: str | None = None
    running: bool = False
    last_run: CollectionRun | None = None


class CollectionOverview(BaseModel):
    sources: list[SourceStatus]
    runs: list[CollectionRun]
