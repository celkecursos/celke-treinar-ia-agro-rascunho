from pydantic import BaseModel


class Health(BaseModel):
    status: str


class ModelStatus(BaseModel):
    name: str
    installed: bool
    tools: bool | None = None


class OllamaStatus(BaseModel):
    online: bool
    chat_model: ModelStatus
    error: str | None = None


class ServiceStatus(BaseModel):
    online: bool
    error: str | None = None


class SchedulerStatus(BaseModel):
    enabled: bool
    timezone: str
    rain_hour: int
    monthly_day: int


class SystemStatus(BaseModel):
    backend: ServiceStatus
    ollama: OllamaStatus
    database: ServiceStatus
    scheduler: SchedulerStatus
