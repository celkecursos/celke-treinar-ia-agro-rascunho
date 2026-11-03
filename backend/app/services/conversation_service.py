from app.core.errors import NotFoundError
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.conversations import Conversation, ConversationDetail


class ConversationService:
    def __init__(self, repository: ConversationRepository):
        self._repo = repository

    def list_all(self) -> list[Conversation]:
        return self._repo.list_all()

    def get(self, conversation_id: str) -> ConversationDetail:
        conversation = self._repo.get(conversation_id)
        if conversation is None:
            raise NotFoundError("Conversa não encontrada.")
        return ConversationDetail(**conversation.model_dump(), messages=self._repo.messages(conversation_id))

    def delete(self, conversation_id: str) -> None:
        if not self._repo.delete(conversation_id):
            raise NotFoundError("Conversa não encontrada.")
