from fastapi import APIRouter, Response, status

from app.api.deps import ContainerDep
from app.schemas.municipalities import IbgeMunicipalityList, Municipality, MunicipalityCreate, MunicipalityList

router = APIRouter(tags=["Municípios"])


@router.get("/municipalities", response_model=MunicipalityList, summary="Municípios cadastrados")
def list_municipalities(c: ContainerDep) -> MunicipalityList:
    return MunicipalityList(items=c.municipalities.all())


@router.post(
    "/municipalities",
    response_model=Municipality,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastra o município e começa a baixar o histórico de chuva e produção (em segundo plano)",
)
def create_municipality(body: MunicipalityCreate, c: ContainerDep) -> Municipality:
    return c.collections.register(body.code)


@router.get("/municipalities/{code}", response_model=Municipality, summary="Um município, com o período dos dados")
def get_municipality(code: int, c: ContainerDep) -> Municipality:
    return c.analyses.municipality(code)


@router.delete(
    "/municipalities/{code}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Exclui o município cadastrado e os dados que só ele usava",
)
def delete_municipality(code: int, c: ContainerDep) -> Response:
    c.collections.remove(code)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/ibge/states/{state}/municipalities",
    response_model=IbgeMunicipalityList,
    summary="Municípios de uma UF (lista do IBGE), para o cadastro",
)
def state_municipalities(state: str, c: ContainerDep) -> IbgeMunicipalityList:
    return IbgeMunicipalityList(items=c.collections.state_municipalities(state))
