from fastapi import APIRouter, Response, status

from app.api.deps import ContainerDep
from app.schemas.conversations import ConversationDetail, ConversationList

router = APIRouter(prefix="/conversations", tags=["Conversas"])


@router.get("", response_model=ConversationList, summary="Lista as conversas, da mais recente para a mais antiga")
def list_conversations(c: ContainerDep) -> ConversationList:
    return ConversationList(items=c.conversations.list_all())


@router.get("/{conversation_id}", response_model=ConversationDetail, summary="Abre uma conversa com as mensagens")
def get_conversation(conversation_id: str, c: ContainerDep) -> ConversationDetail:
    return c.conversations.get(conversation_id)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Exclui a conversa")
def delete_conversation(conversation_id: str, c: ContainerDep) -> Response:
    c.conversations.delete(conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
