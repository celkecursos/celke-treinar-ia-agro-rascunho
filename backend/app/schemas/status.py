from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.gpu import GpuStatus

# local = Ollama deste computador; externo = GPU externa pelo túnel SSH (services/gpu_tunnel.py)
OllamaLocation = Literal["local", "externo"]
# Nome como o Ollama usa: "qwen3:14b", "hf.co/usuario/modelo:Q4_K_M", "celke-agro"
MODEL_NAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._\-/:]{0,199}$"


class Health(BaseModel):
    status: str


class ModelStatus(BaseModel):
    name: str
    installed: bool
    tools: bool | None = None


class InstalledModelInfo(BaseModel):
    name: str
    size_gb: float | None = None
    parameter_size: str | None = None


class PullStatus(BaseModel):
    """Download de um modelo pelo painel. Fica na memória do backend: some ao reiniciar."""

    model: str
    status: Literal["baixando", "concluido", "erro"]
    message: str | None = None
    percent: float | None = None


class OllamaServer(BaseModel):
    location: OllamaLocation
    label: str
    # externo só fica configurado com o servidor cadastrado no card "GPU externa"
    configured: bool
    online: bool
    models: list[InstalledModelInfo] = []
    # modelo escolhido para este Ollama (usado quando ele for o Ollama em uso)
    chat_model: str
    error: str | None = None
    pull: PullStatus | None = None


class OllamaStatus(BaseModel):
    """O Ollama e o modelo em uso no chat, nas descobertas, nos alertas e na explicação da previsão."""

    online: bool
    chat_model: ModelStatus
    location: OllamaLocation
    error: str | None = None
    servers: list[OllamaServer] = []


class OllamaSelection(BaseModel):
    location: OllamaLocation
    model: str = Field(pattern=MODEL_NAME_PATTERN)


class ServiceStatus(BaseModel):
    online: bool
    error: str | None = None


class DatabaseStatus(ServiceStatus):
    # versão da extensão pgvector no PostgreSQL; None se o banco estiver fora do ar ou sem a extensão
    vector_version: str | None = None


class SchedulerStatus(BaseModel):
    enabled: bool
    timezone: str
    rain_hour: int
    monthly_day: int


class SystemStatus(BaseModel):
    backend: ServiceStatus
    ollama: OllamaStatus
    gpu: GpuStatus
    database: DatabaseStatus
    scheduler: SchedulerStatus
