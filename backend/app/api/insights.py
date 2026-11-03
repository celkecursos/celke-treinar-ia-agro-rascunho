from fastapi import APIRouter, Response, status

from app.api.deps import ContainerDep
from app.core.errors import NotFoundError
from app.schemas.insights import AlertList, DiscoveryReport

router = APIRouter(tags=["Descobertas e alertas"])


@router.get("/discoveries", response_model=DiscoveryReport, summary="Relatório de descobertas mais recente")
def latest_report(c: ContainerDep) -> DiscoveryReport:
    report = c.insights.latest()
    if report is None:
        raise NotFoundError("Ainda não há descobertas. Elas são geradas depois das coletas de chuva e produção.")
    return report


@router.post(
    "/discoveries",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Gera o relatório de novo (em segundo plano). Recusa com 409 se já houver um sendo gerado",
)
def regenerate(c: ContainerDep) -> Response:
    c.insights.regenerate()
    return Response(status_code=status.HTTP_202_ACCEPTED)


@router.get("/alerts", response_model=AlertList, summary="Alertas da safra em andamento")
def alerts(c: ContainerDep, include_inactive: bool = False) -> AlertList:
    return AlertList(items=c.insights_repository.alerts(active_only=not include_inactive))
