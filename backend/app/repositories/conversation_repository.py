import uuid

from psycopg.types.json import Jsonb

from app.repositories.database import Database
from app.schemas.analyses import Chart
from app.schemas.chat import ToolCallRecord
from app.schemas.conversations import Conversation, Message, MessageRole, MessageState

_MESSAGE_COLUMNS = "id, role, content, state, error_message, tool_calls, charts, created_at"


class ConversationRepository:
    """Conversas e mensagens do chat no PostgreSQL."""

    def __init__(self, database: Database):
        self._db = database

    def create(self, *, title: str) -> Conversation:
        with self._db.connection() as conn:
            row = conn.execute(
                "INSERT INTO conversations (id, title) VALUES (%s, %s) RETURNING *", (uuid.uuid4().hex, title)
            ).fetchone()
        return Conversation(**row)

    def get(self, conversation_id: str) -> Conversation | None:
        with self._db.connection() as conn:
            row = conn.execute("SELECT * FROM conversations WHERE id = %s", (conversation_id,)).fetchone()
        return Conversation(**row) if row else None

    def list_all(self) -> list[Conversation]:
        with self._db.connection() as conn:
            rows = conn.execute("SELECT * FROM conversations ORDER BY updated_at DESC").fetchall()
        return [Conversation(**r) for r in rows]

    def delete(self, conversation_id: str) -> bool:
        with self._db.connection() as conn:
            return conn.execute("DELETE FROM conversations WHERE id = %s", (conversation_id,)).rowcount > 0

    def messages(self, conversation_id: str) -> list[Message]:
        with self._db.connection() as conn:
            rows = conn.execute(
                f"SELECT {_MESSAGE_COLUMNS} FROM messages WHERE conversation_id = %s ORDER BY seq",
                (conversation_id,),
            ).fetchall()
        return [Message(**r) for r in rows]

    def add_message(
        self,
        conversation_id: str,
        *,
        role: MessageRole,
        content: str,
        state: MessageState = "concluida",
        error_message: str | None = None,
        tool_calls: list[ToolCallRecord] | None = None,
        charts: list[Chart] | None = None,
    ) -> Message:
        with self._db.connection() as conn:
            row = conn.execute(
                "INSERT INTO messages (id, conversation_id, role, content, state, error_message, tool_calls, charts)"
                f" VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING {_MESSAGE_COLUMNS}",
                (
                    uuid.uuid4().hex,
                    conversation_id,
                    role,
                    content,
                    state,
                    error_message,
                    Jsonb([t.model_dump() for t in tool_calls or []]),
                    Jsonb(charts or []),
                ),
            ).fetchone()
            conn.execute("UPDATE conversations SET updated_at = now() WHERE id = %s", (conversation_id,))
        return Message(**row)

    def delete_message(self, message_id: str) -> None:
        with self._db.connection() as conn:
            conn.execute("DELETE FROM messages WHERE id = %s", (message_id,))
