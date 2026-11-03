from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.container import Container
from app.main import create_app
from app.repositories.collection_repository import CollectionRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.crop_repository import CropRepository
from app.repositories.database import TABLES, Database
from app.repositories.forecast_repository import ForecastRepository
from app.repositories.insight_repository import InsightRepository
from app.repositories.municipality_repository import MunicipalityRepository
from app.repositories.weather_repository import WeatherRepository
from app.services.analysis_service import AnalysisService
from app.services.chat_service import ChatService
from app.services.collection_service import CollectionService
from app.services.conversation_service import ConversationService
from app.services.forecast_service import ForecastService
from app.services.insight_service import InsightService
from app.services.scheduler import Scheduler
from app.services.tools import ToolExecutor
from tests.fakes import FakeIbge, FakeModel, FakeRainSource, ImmediateExecutor

TODAY = date(2024, 12, 15)
TZ = ZoneInfo("America/Sao_Paulo")


class FakeOllamaStatus:
    """Só o que as rotas de estado usam do OllamaService."""

    def __init__(self, installed: bool = True, tools: bool = True, error=None):
        self.installed = installed
        self.tools = tools
        self.error = error

    def is_installed(self, model, installed=None):
        if self.error:
            raise self.error
        return self.installed

    def capabilities(self):
        return ["completion", "tools"] if self.tools else ["completion"]


@pytest.fixture(scope="session")
def database():
    """PostgreSQL de teste (serviço postgres-test do compose, em memória). Uma conexão para a sessão toda."""
    db = Database(Settings().database_conninfo)
    db.create_schema()
    yield db
    db.close()


@pytest.fixture(autouse=True)
def clean_database(database):
    with database.connection() as conn:
        conn.execute(f"TRUNCATE {TABLES}")


@pytest.fixture
def settings() -> Settings:
    return Settings(
        history_start_year=2010,
        state_reference_count=2,
        scheduler_enabled=False,
        discovery_min_years=6,
        max_tool_rounds=3,
    )


@pytest.fixture
def clock():
    return lambda: datetime(TODAY.year, TODAY.month, TODAY.day, 8, 0, tzinfo=TZ)


@pytest.fixture
def rain() -> FakeRainSource:
    return FakeRainSource(TODAY)


@pytest.fixture
def ibge() -> FakeIbge:
    return FakeIbge()


@pytest.fixture
def model() -> FakeModel:
    return FakeModel()


@pytest.fixture
def executor():
    return ImmediateExecutor()


@pytest.fixture
def container(settings, database, rain, ibge, model, executor, clock) -> Container:
    municipalities = MunicipalityRepository(database)
    weather = WeatherRepository(database)
    crops = CropRepository(database)
    runs = CollectionRepository(database)
    insights_repository = InsightRepository(database)
    analyses = AnalysisService(municipalities, weather, crops)
    forecasts = ForecastService(
        settings,
        municipalities,
        crops,
        analyses,
        ForecastRepository(database),
        model,
        "modelo-teste",
        ImmediateExecutor(),
        lambda: TODAY,
    )
    insights = InsightService(
        settings,
        municipalities,
        insights_repository,
        analyses,
        model,
        "modelo-teste",
        ImmediateExecutor(),
        lambda: TODAY,
        forecasts,
    )
    collections = CollectionService(
        settings, municipalities, weather, crops, runs, rain, ibge, executor, clock, on_new_data=insights.refresh
    )
    tools = ToolExecutor(municipalities, weather, crops, insights_repository, analyses, forecasts)
    return Container(
        settings=settings,
        database=database,
        municipalities=municipalities,
        runs=runs,
        insights_repository=insights_repository,
        ollama=FakeOllamaStatus(),  # type: ignore[arg-type]
        analyses=analyses,
        forecasts=forecasts,
        collections=collections,
        insights=insights,
        chat=ChatService(settings, ConversationRepository(database), municipalities, tools, model, lambda: TODAY),
        conversations=ConversationService(ConversationRepository(database)),
        scheduler=Scheduler(settings, collections, runs, clock),
        executors=[],
    )


@pytest.fixture
def client(settings, container):
    with TestClient(create_app(settings, container)) as test_client:
        yield test_client


@pytest.fixture
def registered(client):
    """Rio Verde (GO) cadastrado, com chuva e produção coletadas (o executor dos testes roda na hora)."""
    response = client.post("/api/municipalities", json={"code": 5218805})
    assert response.status_code == 201, response.text
    return response.json()
