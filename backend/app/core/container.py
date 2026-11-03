from concurrent.futures import Executor, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import Settings
from app.repositories.collection_repository import CollectionRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.crop_repository import CropRepository
from app.repositories.database import Database
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
from app.services.ollama_service import OllamaService
from app.services.public_data import Ibge, OpenMeteo, PublicDataClient
from app.services.scheduler import Scheduler
from app.services.tools import ToolExecutor


@dataclass
class Container:
    """Objetos compartilhados pela aplicação (criados uma vez, na inicialização)."""

    settings: Settings
    database: Database
    municipalities: MunicipalityRepository
    runs: CollectionRepository
    insights_repository: InsightRepository
    ollama: OllamaService
    analyses: AnalysisService
    forecasts: ForecastService
    collections: CollectionService
    insights: InsightService
    chat: ChatService
    conversations: ConversationService
    scheduler: Scheduler
    executors: list[Executor]


def build_container(settings: Settings) -> Container:
    timezone = ZoneInfo(settings.scheduler_timezone)

    def clock() -> datetime:
        return datetime.now(timezone)

    database = Database(settings.database_conninfo)
    municipalities = MunicipalityRepository(database)
    weather = WeatherRepository(database)
    crops = CropRepository(database)
    runs = CollectionRepository(database)
    insights_repository = InsightRepository(database)
    conversations = ConversationRepository(database)
    ollama = OllamaService(
        host=settings.ollama_url,
        timeout=settings.ollama_timeout_seconds,
        chat_model=settings.chat_model,
        num_ctx=settings.chat_num_ctx,
        temperature=settings.chat_temperature,
        think=settings.chat_think,
    )
    client = PublicDataClient(settings.http_timeout_seconds)
    analyses = AnalysisService(municipalities, weather, crops)
    # Coletas: o cadastro de um município e uma coleta pelo botão podem rodar juntos (fontes diferentes).
    collection_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="coleta")
    # Descobertas e alertas usam o modelo: uma geração por vez.
    insight_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="descobertas")
    forecasts = ForecastService(
        settings,
        municipalities,
        crops,
        analyses,
        ForecastRepository(database),
        ollama,
        settings.chat_model,
        insight_executor,
        lambda: clock().date(),
    )
    insights = InsightService(
        settings,
        municipalities,
        insights_repository,
        analyses,
        ollama,
        settings.chat_model,
        insight_executor,
        lambda: clock().date(),
        forecasts,
    )
    collections = CollectionService(
        settings,
        municipalities,
        weather,
        crops,
        runs,
        OpenMeteo(client),
        Ibge(client),
        collection_executor,
        clock,
        on_new_data=insights.refresh,
    )
    tools = ToolExecutor(municipalities, weather, crops, insights_repository, analyses, forecasts)
    chat = ChatService(settings, conversations, municipalities, tools, ollama, lambda: clock().date())
    return Container(
        settings=settings,
        database=database,
        municipalities=municipalities,
        runs=runs,
        insights_repository=insights_repository,
        ollama=ollama,
        analyses=analyses,
        forecasts=forecasts,
        collections=collections,
        insights=insights,
        chat=chat,
        conversations=ConversationService(conversations),
        scheduler=Scheduler(settings, collections, runs, clock),
        executors=[collection_executor, insight_executor],
    )
