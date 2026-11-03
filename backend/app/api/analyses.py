from fastapi import APIRouter

from app.api.deps import ContainerDep
from app.schemas.analyses import Analysis, EstimateList

router = APIRouter(tags=["Análises"])


@router.get(
    "/analyses/{code}/{crop}",
    response_model=Analysis,
    summary="Chuva × rendimento de um município e cultura (soja ou milho), com indicadores e gráficos",
)
def analysis(code: int, crop: str, c: ContainerDep) -> Analysis:
    return c.analyses.analysis(code, crop)


@router.get("/estimates", response_model=EstimateList, summary="Última estimativa da safra (LSPA) por UF e Brasil")
def estimates(c: ContainerDep) -> EstimateList:
    return EstimateList(items=c.analyses.estimates())
