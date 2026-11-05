from fastapi import APIRouter

from app.api.deps import ContainerDep
from app.schemas.gpu import GpuPassword, GpuServer, GpuStatus

router = APIRouter(prefix="/gpu", tags=["GPU externa"])


@router.get("", response_model=GpuStatus, summary="Servidor da GPU externa, situação do túnel e chave pública")
def gpu_status(c: ContainerDep) -> GpuStatus:
    return c.gpu.status()


@router.post("", response_model=GpuStatus, summary="Cadastra (ou troca) o servidor e conecta")
def save_gpu(body: GpuServer, c: ContainerDep) -> GpuStatus:
    return c.gpu.save(body.host.strip(), body.port, body.user.strip())


@router.post("/connect", response_model=GpuStatus, summary="Abre o túnel SSH")
def connect_gpu(c: ContainerDep) -> GpuStatus:
    return c.gpu.connect()


@router.post("/disconnect", response_model=GpuStatus, summary="Fecha o túnel SSH (o modelo volta para o local)")
def disconnect_gpu(c: ContainerDep) -> GpuStatus:
    c.ollama.use_local()
    return c.gpu.disconnect()


@router.post("/install-key", response_model=GpuStatus, summary="Instala a chave pública no servidor com a senha")
def install_key(body: GpuPassword, c: ContainerDep) -> GpuStatus:
    return c.gpu.install_key(body.password)


@router.post("/accept-host-key", response_model=GpuStatus, summary="Aceita a chave nova do servidor")
def accept_host_key(c: ContainerDep) -> GpuStatus:
    return c.gpu.forget_host_key()


@router.delete("", response_model=GpuStatus, summary="Remove o servidor cadastrado (o modelo volta para o local)")
def remove_gpu(c: ContainerDep) -> GpuStatus:
    c.ollama.use_local()
    return c.gpu.remove()
