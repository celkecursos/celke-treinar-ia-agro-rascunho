from fastapi import APIRouter, Response, status

from app.api.deps import ContainerDep
from app.schemas.forecasts import ForecastView

router = APIRouter(prefix="/forecasts", tags=["Previsão da safra"])


@router.get(
    "/{code}/{crop}",
    response_model=ForecastView,
    summary="Último treino do modelo de previsão (variáveis, erro da validação, previsões) e o histórico de treinos",
)
def forecast(code: int, crop: str, c: ContainerDep) -> ForecastView:
    return c.forecasts.view(code, crop)


@router.post(
    "/train",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Treina de novo os modelos de todos os municípios (em segundo plano). Recusa com 409 se já houver treino",
)
def train(c: ContainerDep) -> Response:
    c.forecasts.train_in_background()
    return Response(status_code=status.HTTP_202_ACCEPTED)
