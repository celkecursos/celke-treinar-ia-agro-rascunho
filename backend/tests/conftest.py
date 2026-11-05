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
from app.repositories.setting_repository import SettingRepository
from app.repositories.weather_repository import WeatherRepository
from app.services.analysis_service import AnalysisService
from app.services.chat_service import ChatService
from app.services.collection_service import CollectionService
from app.services.conversation_service import ConversationService
from app.services.forecast_service import ForecastService
from app.services.gpu_tunnel import GpuTunnel
from app.services.insight_service import InsightService
from app.services.model_selector import ModelSelector
from app.services.scheduler import Scheduler
from app.services.tools import ToolExecutor
from tests.fakes import FakeGpu, FakeIbge, FakeModel, FakeOllamaServer, FakeRainSource, ImmediateExecutor

TODAY = date(2024, 12, 15)
TZ = ZoneInfo("America/Sao_Paulo")


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
def ollama_servers() -> dict[str, FakeOllamaServer]:
    """Os dois Ollama: o deste computador e o da GPU externa."""
    return {"local": FakeOllamaServer("local"), "externo": FakeOllamaServer("externo")}


@pytest.fixture
def gpu() -> FakeGpu:
    """A GPU externa cadastrada e conectada; os testes mudam `configured` e `connected`."""
    return FakeGpu()


@pytest.fixture
def selector(ollama_servers, gpu, database) -> ModelSelector:
    return ModelSelector(ollama_servers, gpu, SettingRepository(database), "qwen3:8b", ImmediateExecutor())  # type: ignore[arg-type]


@pytest.fixture
def gpu_tunnel(database, tmp_path) -> GpuTunnel:
    """O túnel de verdade, com a chave numa pasta temporária (não conecta até alguém pedir)."""
    tunnel = GpuTunnel(SettingRepository(database), tmp_path / "ssh", 0, listen_host="127.0.0.1", connect_timeout=5)
    yield tunnel
    tunnel.stop()


@pytest.fixture
def executor():
    return ImmediateExecutor()


@pytest.fixture
def container(settings, database, rain, ibge, model, executor, clock, selector, gpu_tunnel) -> Container:
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
        ImmediateExecutor(),
        lambda: TODAY,
    )
    insights = InsightService(
        settings,
        municipalities,
        insights_repository,
        analyses,
        model,
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
        ollama=selector,
        gpu=gpu_tunnel,
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
