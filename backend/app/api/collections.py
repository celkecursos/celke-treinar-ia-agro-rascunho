from fastapi import APIRouter, status

from app.api.deps import ContainerDep
from app.schemas.collections import CollectionOverview, CollectionRun, CollectionSource

router = APIRouter(prefix="/collections", tags=["Coletas"])


@router.get("", response_model=CollectionOverview, summary="Fontes, último dado de cada uma e registro das coletas")
def overview(c: ContainerDep) -> CollectionOverview:
    return c.collections.overview()


@router.post(
    "/{source}",
    response_model=CollectionRun,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Busca agora (botão): chuva, producao ou estimativa. Recusa com 409 se a fonte já estiver coletando",
)
def collect(source: CollectionSource, c: ContainerDep) -> CollectionRun:
    return c.collections.trigger(source, "botao")
