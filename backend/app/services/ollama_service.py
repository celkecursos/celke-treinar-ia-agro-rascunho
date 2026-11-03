import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

import httpx
import ollama

from app.core.errors import ModelNotInstalledError, OllamaUnavailableError

Messages = list[dict[str, Any]]


@dataclass(frozen=True)
class ChatChunk:
    """Pedaço da resposta: `content` vai para a pessoa; `thinking` é o raciocínio; `tool_call` pede uma ferramenta."""

    kind: Literal["content", "thinking", "tool_call"]
    text: str = ""
    name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)


class LanguageModel(Protocol):
    def chat_stream(self, messages: Messages, tools: list[dict] | None = None) -> Iterator[ChatChunk]: ...

    def chat_json(self, messages: Messages, schema: dict) -> dict: ...


def _same_model(installed: str, wanted: str) -> bool:
    # "qwen3" é instalado como "qwen3:latest"
    if ":" not in wanted:
        wanted = f"{wanted}:latest"
    return installed == wanted


class OllamaService:
    """Acesso ao Ollama: estado, modelos instalados, chat com ferramentas (streaming) e respostas em JSON."""

    def __init__(self, host: str, timeout: float, chat_model: str, num_ctx: int, temperature: float, think: str):
        self._client = ollama.Client(host=host, timeout=timeout)
        self._quick = ollama.Client(host=host, timeout=5)
        self.chat_model = chat_model
        self._options = {"num_ctx": num_ctx, "temperature": temperature}
        self._think = think
        self._capabilities: list[str] | None = None

    def installed_models(self) -> list[str]:
        try:
            response = self._quick.list()
        except (httpx.HTTPError, ConnectionError) as exc:
            raise OllamaUnavailableError(
                "Não foi possível conectar ao Ollama. Verifique se o container está rodando."
            ) from exc
        return [m.model for m in response.models if m.model]

    def is_installed(self, model: str, installed: list[str] | None = None) -> bool:
        names = installed if installed is not None else self.installed_models()
        return any(_same_model(name, model) for name in names)

    def capabilities(self) -> list[str]:
        if self._capabilities is None:
            try:
                self._capabilities = list(self._quick.show(self.chat_model).capabilities or [])
            except Exception as exc:
                raise self._translate(exc) from exc
        return self._capabilities

    def _translate(self, exc: Exception) -> Exception:
        model = self.chat_model
        if isinstance(exc, ollama.ResponseError):
            if exc.status_code == 404:
                return ModelNotInstalledError(
                    f"O modelo {model} não está instalado no Ollama. Aguarde o download inicial "
                    f"(serviço ollama-init) ou execute: docker compose exec ollama ollama pull {model}"
                )
            if "does not support tools" in str(exc.error):
                return ModelNotInstalledError(
                    f"O modelo {model} não aceita ferramentas (tool calling). Use um modelo com a etiqueta "
                    '"tools" no Ollama, como o qwen3, em CHAT_MODEL no .env.'
                )
            if "memory" in str(exc.error).lower():
                return OllamaUnavailableError(
                    f"O Ollama não tem memória suficiente para carregar o modelo {model}. "
                    "Feche outros programas ou configure um modelo menor."
                )
            return OllamaUnavailableError(f"O Ollama retornou um erro: {exc.error}")
        if isinstance(exc, httpx.TimeoutException):
            return OllamaUnavailableError(
                "O Ollama demorou demais para responder. Na primeira pergunta o modelo é carregado na memória; tente de novo."
            )
        if isinstance(exc, (httpx.HTTPError, ConnectionError)):
            return OllamaUnavailableError("Não foi possível conectar ao Ollama. Verifique se o container está rodando.")
        return exc

    def _use_thinking(self) -> bool:
        """`auto` liga o raciocínio separado quando o modelo tem essa capacidade."""
        if self._think in ("true", "false"):
            return self._think == "true"
        return "thinking" in self.capabilities()

    def chat_stream(self, messages: Messages, tools: list[dict] | None = None) -> Iterator[ChatChunk]:
        try:
            stream = self._client.chat(
                model=self.chat_model,
                messages=messages,
                tools=tools,
                stream=True,
                think=self._use_thinking(),
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
            raise self._translate(exc) from exc

    def chat_json(self, messages: Messages, schema: dict) -> dict:
        """Resposta inteira (sem streaming) em JSON que segue o `schema` (saída estruturada do Ollama)."""
        try:
            response = self._client.chat(
                model=self.chat_model, messages=messages, format=schema, think=False, options=self._options
            )
        except Exception as exc:
            raise self._translate(exc) from exc
        try:
            return json.loads(response.message.content or "{}")
        except json.JSONDecodeError as exc:
            raise OllamaUnavailableError(
                "O modelo devolveu uma resposta fora do formato pedido. Tente de novo."
            ) from exc
