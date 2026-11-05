from typing import Literal

from pydantic import BaseModel, Field

# nao_configurado = sem servidor cadastrado; erro = a última tentativa falhou (a mensagem diz o que fazer)
TunnelState = Literal["nao_configurado", "desconectado", "conectando", "conectado", "erro"]


class GpuServer(BaseModel):
    """Servidor da GPU externa (por exemplo, uma instância de GPU da Hostinger com o app Ollama)."""

    host: str = Field(min_length=1, max_length=253, description="IP ou nome do servidor")
    port: int = Field(default=22, ge=1, le=65535)
    user: str = Field(default="root", min_length=1, max_length=32)


class GpuPassword(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class GpuStatus(BaseModel):
    configured: bool
    host: str | None = None
    port: int = 22
    user: str = "root"
    state: TunnelState
    message: str | None = None
    # chave pública do backend: cadastre no servidor (ou instale com a senha)
    public_key: str
    # chave do servidor aceita na primeira conexão
    host_key_fingerprint: str | None = None
    host_key_mismatch: bool = False
    # porta do túnel dentro da rede do Docker (http://backend:<porta> para o finetune-tools)
    tunnel_port: int
