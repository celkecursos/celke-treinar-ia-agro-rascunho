from fastapi import APIRouter, status

from app.api.deps import ContainerDep
from app.schemas.status import OllamaSelection, OllamaStatus, PullStatus

router = APIRouter(prefix="/ollama", tags=["Modelo de IA"])


@router.get("", response_model=OllamaStatus, summary="Ollama e modelo em uso, com os modelos de cada Ollama")
def ollama_status(c: ContainerDep) -> OllamaStatus:
    return c.ollama.status()


@router.post("/selection", response_model=OllamaStatus, summary="Troca o Ollama (local ou GPU externa) e o modelo")
def select_model(body: OllamaSelection, c: ContainerDep) -> OllamaStatus:
    return c.ollama.select(body.location, body.model)


@router.post(
    "/pull",
    response_model=PullStatus,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Baixa um modelo no Ollama escolhido (em segundo plano)",
)
def pull_model(body: OllamaSelection, c: ContainerDep) -> PullStatus:
    return c.ollama.pull(body.location, body.model)
