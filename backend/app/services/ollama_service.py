import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

import httpx
import ollama

from app.core.errors import ModelNotInstalledError, OllamaUnavailableError

Messages = list[dict[str, Any]]
# local = Ollama deste computador; externo = GPU externa pelo túnel SSH (services/gpu_tunnel.py)
Location = Literal["local", "externo"]


@dataclass(frozen=True)
class ChatChunk:
    """Pedaço da resposta: `content` vai para a pessoa; `thinking` é o raciocínio; `tool_call` pede uma ferramenta."""

    kind: Literal["content", "thinking", "tool_call"]
    text: str = ""
    name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InstalledModel:
    name: str
    size_bytes: int | None = None
    # tamanho do modelo informado pelo Ollama, como "8.2B"
    parameter_size: str | None = None


@dataclass(frozen=True)
class PullProgress:
    """Um passo do download: `completed` e `total` (bytes) vêm por camada, identificada pelo `digest`."""

    status: str
    digest: str | None = None
    completed: int | None = None
    total: int | None = None


class LanguageModel(Protocol):
    @property
    def name(self) -> str: ...

    def chat_stream(self, messages: Messages, tools: list[dict] | None = None) -> Iterator[ChatChunk]: ...

    def chat_json(self, messages: Messages, schema: dict) -> dict: ...


def same_model(installed: str, wanted: str) -> bool:
    # "qwen3" é instalado como "qwen3:latest"
    if ":" not in wanted:
        wanted = f"{wanted}:latest"
    return installed == wanted


class OllamaService:
    """Um servidor Ollama (local ou GPU externa): modelos instalados, download, chat com ferramentas e JSON.

    O modelo vem em cada chamada: quem escolhe qual servidor e qual modelo usar é o `ModelSelector`.
    """

    def __init__(self, location: Location, host: str, timeout: float, num_ctx: int, temperature: float, think: str):
        self.location: Location = location
        self._client = ollama.Client(host=host, timeout=timeout)
        self._quick = ollama.Client(host=host, timeout=5)
        # o download de um modelo grande leva minutos: sem tempo limite de leitura
        self._pulling = ollama.Client(host=host, timeout=httpx.Timeout(10, read=None))
        self._options = {"num_ctx": num_ctx, "temperature": temperature}
        self._think = think
        self._capabilities: dict[str, list[str]] = {}

    def _unavailable_message(self) -> str:
        if self.location == "externo":
            return (
                "O túnel está aberto, mas o Ollama da GPU externa não respondeu. Confira no servidor se o Ollama está "
                "rodando (systemctl status ollama) na porta 11434 e se o SSH permite encaminhar portas "
                "(AllowTcpForwarding yes em /etc/ssh/sshd_config)."
            )
        return "Não foi possível conectar ao Ollama. Verifique se o container está rodando."

    def _pull_hint(self, model: str) -> str:
        where = "no servidor da GPU" if self.location == "externo" else "com docker compose exec ollama"
        return f"Baixe na página Modelo de IA (Status e coletas > Configurar) ou {where}: ollama pull {model}"

    def installed_models(self) -> list[InstalledModel]:
        try:
            response = self._quick.list()
        except (httpx.HTTPError, ConnectionError) as exc:
            raise OllamaUnavailableError(self._unavailable_message()) from exc
        return [
            InstalledModel(m.model, m.size, m.details.parameter_size if m.details else None)
            for m in response.models
            if m.model
        ]

    def is_installed(self, model: str, installed: list[InstalledModel] | None = None) -> bool:
        models = installed if installed is not None else self.installed_models()
        return any(same_model(m.name, model) for m in models)

    def capabilities(self, model: str) -> list[str]:
        if model not in self._capabilities:
            try:
                self._capabilities[model] = list(self._quick.show(model).capabilities or [])
            except Exception as exc:
                raise self._translate(exc, model) from exc
        return self._capabilities[model]

    def pull(self, model: str) -> Iterator[PullProgress]:
        """Baixa o modelo neste servidor, devolvendo o andamento. O Ollama retoma um download interrompido."""
        self._capabilities.pop(model, None)
        try:
            for part in self._pulling.pull(model, stream=True):
                yield PullProgress(part.status or "", part.digest, part.completed, part.total)
        except Exception as exc:
            if isinstance(exc, ollama.ResponseError) and "file does not exist" in str(exc.error):
                raise ModelNotInstalledError(
                    f"O modelo {model} não existe na biblioteca do Ollama. Confira o nome em https://ollama.com/library"
                ) from exc
            raise self._translate(exc, model) from exc

    def _translate(self, exc: Exception, model: str) -> Exception:
        if isinstance(exc, ollama.ResponseError):
            if exc.status_code == 404:
                return ModelNotInstalledError(
                    f"O modelo {model} não está instalado neste Ollama. {self._pull_hint(model)}"
                )
            if "does not support tools" in str(exc.error):
                return ModelNotInstalledError(
                    f"O modelo {model} não aceita ferramentas (tool calling). Escolha na página Modelo de IA (Status e coletas > Configurar) um modelo "
                    'com a etiqueta "tools" no Ollama, como o qwen3.'
                )
            if "memory" in str(exc.error).lower():
                return OllamaUnavailableError(
                    f"O Ollama não tem memória suficiente para carregar o modelo {model}. "
                    "Feche outros programas ou escolha um modelo menor na página Modelo de IA (Status e coletas > Configurar)."
                )
            return OllamaUnavailableError(f"O Ollama retornou um erro: {exc.error}")
        if isinstance(exc, httpx.TimeoutException):
            return OllamaUnavailableError(
                "O Ollama demorou demais para responder. Na primeira pergunta o modelo é carregado na memória; tente de novo."
            )
        if isinstance(exc, (httpx.HTTPError, ConnectionError)):
            return OllamaUnavailableError(self._unavailable_message())
        return exc

    def _use_thinking(self, model: str) -> bool:
        """`auto` liga o raciocínio separado quando o modelo tem essa capacidade."""
        if self._think in ("true", "false"):
            return self._think == "true"
        return "thinking" in self.capabilities(model)

    def chat_stream(self, model: str, messages: Messages, tools: list[dict] | None = None) -> Iterator[ChatChunk]:
        try:
            stream = self._client.chat(
                model=model,
                messages=messages,
                tools=tools,
                stream=True,
                think=self._use_thinking(model),
                options=self._options,
            )
            for part in stream:
                if part.message.thinking:
                    yield ChatChunk("thinking", part.message.thinking)
                if part.message.content:
                    yield ChatChunk("content", part.message.content)
                for call in part.message.tool_calls or []:
                    yield ChatChunk("tool_call", name=call.function.name, arguments=dict(call.function.arguments or {}))
        except Exception as exc:
            raise self._translate(exc, model) from exc

    def chat_json(self, model: str, messages: Messages, schema: dict) -> dict:
        """Resposta inteira (sem streaming) em JSON que segue o `schema` (saída estruturada do Ollama)."""
        try:
            response = self._client.chat(
                model=model, messages=messages, format=schema, think=False, options=self._options
            )
        except Exception as exc:
            raise self._translate(exc, model) from exc
        try:
            return json.loads(response.message.content or "{}")
        except json.JSONDecodeError as exc:
            raise OllamaUnavailableError(
                "O modelo devolveu uma resposta fora do formato pedido. Tente de novo."
            ) from exc
