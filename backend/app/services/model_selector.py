"""Qual Ollama e qual modelo de linguagem a aplicação usa, escolhidos na página Modelo de IA (Status e coletas > Configurar).

Os dois Ollama podem estar no ar ao mesmo tempo: o deste computador e o da GPU externa (pelo túnel SSH que o backend
abre, `services/gpu_tunnel.py`). A escolha fica no banco e vale para o chat, as descobertas, os alertas e a explicação
da previsão, sem reiniciar nada.
"""

import logging
import threading
from collections.abc import Iterator
from concurrent.futures import Executor
from typing import Protocol

from app.core.errors import (
    AppError,
    ConflictError,
    DatabaseUnavailableError,
    InvalidDataError,
    OllamaUnavailableError,
)
from app.repositories.setting_repository import SettingRepository
from app.schemas.status import (
    InstalledModelInfo,
    ModelStatus,
    OllamaLocation,
    OllamaServer,
    OllamaStatus,
    PullStatus,
)
from app.services.ollama_service import ChatChunk, Messages, OllamaService, PullProgress, same_model

logger = logging.getLogger(__name__)

LOCATIONS: tuple[OllamaLocation, ...] = ("local", "externo")
LOCATION_LABEL: dict[OllamaLocation, str] = {
    "local": "Neste computador",
    "externo": "GPU externa",
}
NOT_CONFIGURED = 'GPU externa não cadastrada. Cadastre o servidor no card "GPU externa" desta página.'
DISCONNECTED = 'GPU externa desconectada. Conecte no card "GPU externa" desta página.'
LOCATION_KEY = "ollama_location"


class Tunnel(Protocol):
    """O que o seletor usa do túnel da GPU externa."""

    @property
    def configured(self) -> bool: ...

    @property
    def connected(self) -> bool: ...

    @property
    def message(self) -> str | None: ...


def _model_key(location: OllamaLocation) -> str:
    return f"chat_model.{location}"


def _percent(layers: dict[str, tuple[int, int]]) -> float | None:
    total = sum(t for _, t in layers.values())
    if not total:
        return None
    return round(100 * sum(c for c, _ in layers.values()) / total, 1)


class ModelSelector:
    """O modelo de linguagem em uso (implementa `LanguageModel`), a troca pelo painel e o download de modelos."""

    def __init__(
        self,
        servers: dict[OllamaLocation, OllamaService],
        gpu: Tunnel,
        settings: SettingRepository,
        default_model: str,
        executor: Executor,
    ):
        self._servers = servers
        self._gpu = gpu
        self._settings = settings
        self._executor = executor
        self._location: OllamaLocation = "local"
        self._models: dict[OllamaLocation, str] = dict.fromkeys(LOCATIONS, default_model)
        self._loaded = False
        self._lock = threading.Lock()
        self._pulls: dict[OllamaLocation, PullStatus] = {}

    # Escolha

    def _load(self) -> None:
        if self._loaded:
            return
        try:
            saved = self._settings.all()
        except DatabaseUnavailableError:
            return  # tenta de novo na próxima chamada; até lá, os valores do .env
        for location in LOCATIONS:
            if saved.get(_model_key(location)):
                self._models[location] = saved[_model_key(location)]
        if saved.get(LOCATION_KEY) in LOCATIONS:
            self._location = saved[LOCATION_KEY]  # type: ignore[assignment]
        self._loaded = True

    def current(self) -> tuple[OllamaLocation, str]:
        with self._lock:
            self._load()
            # escolhida a GPU externa e depois removido o servidor: volta para o local
            location = self._location if self._configured(self._location) else "local"
            return location, self._models[location]

    @property
    def name(self) -> str:
        return self.current()[1]

    def _configured(self, location: OllamaLocation) -> bool:
        return location == "local" or self._gpu.configured

    def _server(self, location: OllamaLocation) -> OllamaService:
        if not self._configured(location):
            raise InvalidDataError(NOT_CONFIGURED)
        if location == "externo" and not self._gpu.connected:
            raise OllamaUnavailableError(self._gpu.message or DISCONNECTED)
        return self._servers[location]

    def select(self, location: OllamaLocation, model: str) -> OllamaStatus:
        """Troca o Ollama e o modelo em uso. O modelo precisa estar instalado nele e aceitar ferramentas."""
        server = self._server(location)
        if not server.is_installed(model):
            raise InvalidDataError(
                f'O modelo {model} não está instalado em "{LOCATION_LABEL[location]}". Baixe o modelo antes de usar.'
            )
        if "tools" not in server.capabilities(model):
            raise InvalidDataError(
                f"O modelo {model} não aceita ferramentas (tool calling), e o chat precisa delas. Escolha um modelo com "
                'a etiqueta "tools" no Ollama, como o qwen3.'
            )
        with self._lock:
            self._load()
            self._settings.save({LOCATION_KEY: location, _model_key(location): model})
            self._location = location
            self._models[location] = model
        logger.info("Modelo em uso: %s (%s)", model, location)
        return self.status()

    def use_local(self) -> None:
        """Volta para o Ollama deste computador (GPU externa desconectada ou removida pelo painel)."""
        with self._lock:
            self._load()
            if self._location == "local":
                return
            self._settings.save({LOCATION_KEY: "local"})
            self._location = "local"
        logger.info("GPU externa fora de uso: modelo em uso volta para %s (local)", self._models["local"])

    # Download

    def pull(self, location: OllamaLocation, model: str) -> PullStatus:
        """Baixa o modelo no Ollama escolhido, em segundo plano. Um download por vez em cada Ollama."""
        server = self._server(location)
        with self._lock:
            running = self._pulls.get(location)
            if running and running.status == "baixando":
                raise ConflictError(f"Já existe um download em andamento ({running.model}). Aguarde terminar.")
            state = self._pulls[location] = PullStatus(model=model, status="baixando", message="Iniciando o download")
        self._executor.submit(self._run_pull, server, location, model)
        return state

    def _run_pull(self, server: OllamaService, location: OllamaLocation, model: str) -> None:
        layers: dict[str, tuple[int, int]] = {}
        try:
            for step in server.pull(model):
                self._pull_step(location, model, step, layers)
            self._pulls[location] = PullStatus(model=model, status="concluido", message="Modelo baixado", percent=100)
        except AppError as exc:
            self._pulls[location] = PullStatus(
                model=model, status="erro", message=exc.message, percent=_percent(layers)
            )
        except Exception:
            logger.exception("Erro no download do modelo %s (%s)", model, location)
            self._pulls[location] = PullStatus(
                model=model, status="erro", message="Erro inesperado no download. Veja: docker compose logs backend"
            )

    def _pull_step(
        self, location: OllamaLocation, model: str, step: PullProgress, layers: dict[str, tuple[int, int]]
    ) -> None:
        if step.digest and step.total:
            layers[step.digest] = (step.completed or 0, step.total)
        message = "Baixando" if step.status.startswith("pulling ") and step.digest else step.status
        self._pulls[location] = PullStatus(model=model, status="baixando", message=message, percent=_percent(layers))

    # Estado para a página Modelo de IA e a de Status

    def status(self) -> OllamaStatus:
        location, model = self.current()
        servers: list[OllamaServer] = []
        installed: list = []
        error: str | None = NOT_CONFIGURED
        for loc in LOCATIONS:
            entry = OllamaServer(
                location=loc,
                label=LOCATION_LABEL[loc],
                configured=self._configured(loc),
                online=False,
                chat_model=self._models[loc],
                error=NOT_CONFIGURED,
                pull=self._pulls.get(loc),
            )
            if entry.configured:
                try:
                    # com o túnel fechado, nem tenta: a mensagem do túnel diz o que fazer
                    models = self._server(loc).installed_models()
                    entry.online, entry.error = True, None
                    entry.models = [
                        InstalledModelInfo(
                            name=m.name,
                            size_gb=round(m.size_bytes / 1e9, 1) if m.size_bytes else None,
                            parameter_size=m.parameter_size,
                        )
                        for m in sorted(models, key=lambda m: m.name)
                    ]
                except AppError as exc:
                    models, entry.error = [], exc.message
                if loc == location:
                    installed, error = models, entry.error
            servers.append(entry)

        chat_model = ModelStatus(name=model, installed=any(same_model(m.name, model) for m in installed))
        if chat_model.installed:
            try:
                chat_model.tools = "tools" in self._servers[location].capabilities(model)
            except AppError:
                chat_model.tools = None
        return OllamaStatus(
            online=error is None, chat_model=chat_model, location=location, error=error, servers=servers
        )

    # LanguageModel: cada chamada vai para o Ollama e o modelo escolhidos no momento

    def chat_stream(self, messages: Messages, tools: list[dict] | None = None) -> Iterator[ChatChunk]:
        location, model = self.current()
        yield from self._server(location).chat_stream(model, messages, tools)

    def chat_json(self, messages: Messages, schema: dict) -> dict:
        location, model = self.current()
        return self._server(location).chat_json(model, messages, schema)
