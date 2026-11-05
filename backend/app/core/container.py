from concurrent.futures import Executor, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.core.config import Settings
from app.repositories.collection_repository import CollectionRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.crop_repository import CropRepository
from app.repositories.database import Database
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
from app.services.ollama_service import Location, OllamaService
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
    ollama: ModelSelector
    gpu: GpuTunnel
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
    setting_repository = SettingRepository(database)
    gpu = GpuTunnel(setting_repository, Path(settings.ssh_key_dir), settings.gpu_tunnel_port)
    # o Ollama da GPU externa fica na porta do túnel, dentro do próprio container do backend
    hosts: dict[Location, str] = {
        "local": settings.ollama_url,
        "externo": f"http://127.0.0.1:{settings.gpu_tunnel_port}",
    }
    servers = {
        location: OllamaService(
            location=location,
            host=host,
            timeout=settings.ollama_timeout_seconds,
            num_ctx=settings.chat_num_ctx,
            temperature=settings.chat_temperature,
            think=settings.chat_think,
        )
        for location, host in hosts.items()
    }
    # Downloads de modelos pelo painel: um por Ollama
    pull_executor = ThreadPoolExecutor(max_workers=len(servers), thread_name_prefix="download-modelo")
    ollama = ModelSelector(servers, gpu, setting_repository, settings.chat_model, pull_executor)
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
        insight_executor,
        lambda: clock().date(),
    )
    insights = InsightService(
        settings,
        municipalities,
        insights_repository,
        analyses,
        ollama,
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
        gpu=gpu,
        analyses=analyses,
        forecasts=forecasts,
        collections=collections,
        insights=insights,
        chat=chat,
        conversations=ConversationService(conversations),
        scheduler=Scheduler(settings, collections, runs, clock),
        executors=[collection_executor, insight_executor, pull_executor],
    )
