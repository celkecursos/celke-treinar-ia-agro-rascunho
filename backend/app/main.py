import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import analyses, chat, collections, conversations, forecasts, insights, municipalities, status
from app.core.config import Settings, get_settings
from app.core.container import Container, build_container
from app.core.errors import register_error_handlers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("celke-treinar-ia-agro")


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        c = app.state.container = container or build_container(settings)
        c.database.create_schema()
        interrupted = c.runs.mark_interrupted() + c.municipalities.mark_interrupted()
        interrupted += c.insights_repository.mark_interrupted()
        if interrupted:
            logger.warning("%d coleta(s) ou geração(ões) interrompidas marcadas como erro", interrupted)
        c.scheduler.start()
        yield
        c.scheduler.stop()
        for executor in c.executors:
            executor.shutdown(wait=False, cancel_futures=True)
        if container is None:  # o container de fora (testes) é fechado por quem o criou
            c.database.close()

    app = FastAPI(
        title="Celke Treinar IA Agro",
        description="API que coleta chuva (Open-Meteo) e produção de soja e milho (IBGE), cruza os dados e conversa "
        "sobre eles com um modelo de IA local (Ollama) que usa ferramentas.",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["Content-Type"],
        )
    register_error_handlers(app)

    api = APIRouter(prefix="/api")
    for module in (status, municipalities, collections, analyses, forecasts, insights, chat, conversations):
        api.include_router(module.router)
    app.include_router(api)
    return app


app = create_app()
