from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = Field(
        default=None,
        max_length=64,
        description="Conversa em que a pergunta entra. Vazio = cria uma conversa nova (evento `conversation`).",
    )
    retry: bool = Field(
        default=False,
        description="Gera de novo a última resposta da conversa, que terminou em erro, sem repetir a pergunta.",
    )


class ToolCallRecord(BaseModel):
    """Ferramenta que o modelo chamou: aparece como fonte da resposta."""

    name: str
    arguments: dict[str, Any]
    ok: bool
    summary: str
    source: str | None = None
