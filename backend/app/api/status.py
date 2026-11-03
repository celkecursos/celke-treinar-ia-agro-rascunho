from fastapi import APIRouter

from app.api.deps import ContainerDep
from app.core.errors import AppError
from app.schemas.status import Health, ModelStatus, OllamaStatus, SchedulerStatus, ServiceStatus, SystemStatus

router = APIRouter(tags=["Estado"])


@router.get("/health", response_model=Health, summary="Saúde da API")
def health() -> Health:
    return Health(status="ok")


def _ollama_status(c: ContainerDep) -> OllamaStatus:
    name = c.settings.chat_model
    try:
        installed = c.ollama.is_installed(name)
    except AppError as exc:
        return OllamaStatus(online=False, chat_model=ModelStatus(name=name, installed=False), error=exc.message)
    tools = None
    if installed:
        try:
            tools = "tools" in c.ollama.capabilities()
        except AppError:
            tools = None
    return OllamaStatus(online=True, chat_model=ModelStatus(name=name, installed=installed, tools=tools))


@router.get("/status", response_model=SystemStatus, summary="Estado dos serviços e do agendador")
def system_status(c: ContainerDep) -> SystemStatus:
    try:
        c.database.ping()
        database = ServiceStatus(online=True)
    except AppError as exc:
        database = ServiceStatus(online=False, error=exc.message)
    s = c.settings
    return SystemStatus(
        backend=ServiceStatus(online=True),
        ollama=_ollama_status(c),
        database=database,
        scheduler=SchedulerStatus(
            enabled=s.scheduler_enabled,
            timezone=s.scheduler_timezone,
            rain_hour=s.rain_collect_hour,
            monthly_day=s.monthly_collect_day,
        ),
    )
