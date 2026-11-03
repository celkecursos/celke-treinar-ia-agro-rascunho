from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.deps import ContainerDep
from app.schemas.chat import ChatRequest

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post(
    "",
    summary="Pergunta ao assistente, que consulta os dados com ferramentas (streaming)",
    description=(
        "Resposta em Server-Sent Events. Eventos: `conversation` (`{id, title}`), `thinking` (o modelo está "
        "raciocinando; uma vez), `tool_call` (`{name, arguments}`), `tool_result` (`{name, ok, summary, source}`), "
        "`chart` (especificação do gráfico), `token` (`{text}`), `done` e `error` (`{codigo, mensagem}`). A pergunta "
        "e a resposta ficam gravadas na conversa, com as ferramentas usadas e os gráficos."
    ),
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
def chat(request: ChatRequest, c: ContainerDep) -> StreamingResponse:
    turn = c.chat.start(request)
    return StreamingResponse(
        c.chat.stream_answer(turn),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
