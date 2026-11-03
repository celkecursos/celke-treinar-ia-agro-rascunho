from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.analyses import Chart
from app.schemas.chat import ToolCallRecord

MessageRole = Literal["user", "assistant"]
MessageState = Literal["concluida", "erro"]


class Message(BaseModel):
    id: str
    role: MessageRole
    content: str
    state: MessageState
    error_message: str | None = None
    tool_calls: list[ToolCallRecord] = []
    charts: list[Chart] = []
    created_at: datetime


class Conversation(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationDetail(Conversation):
    messages: list[Message]


class ConversationList(BaseModel):
    items: list[Conversation]
