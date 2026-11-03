from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Erro de negócio com código HTTP e mensagem para o usuário."""

    status_code = 400
    code = "erro"

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class NotFoundError(AppError):
    status_code = 404
    code = "nao_encontrado"


class ConflictError(AppError):
    status_code = 409
    code = "conflito"


class InvalidDataError(AppError):
    status_code = 422
    code = "dados_invalidos"


class OllamaUnavailableError(AppError):
    status_code = 503
    code = "ollama_indisponivel"


class ModelNotInstalledError(AppError):
    status_code = 503
    code = "modelo_ausente"


class DatabaseUnavailableError(AppError):
    status_code = 503
    code = "banco_de_dados_indisponivel"


class SourceUnavailableError(AppError):
    """Uma fonte de dados públicos (Open-Meteo, IBGE) não respondeu ou respondeu algo inesperado."""

    status_code = 503
    code = "fonte_indisponivel"


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"erro": {"codigo": exc.code, "mensagem": exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        message = f"Dados inválidos em {field}: {first.get('msg', '')}" if field else "Dados inválidos."
        return JSONResponse(
            status_code=422,
            content={"erro": {"codigo": "dados_invalidos", "mensagem": message}},
        )
