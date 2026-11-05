"""Túnel SSH até a GPU externa, aberto pelo próprio backend e configurado na página Modelo de IA (Status e coletas > Configurar).

O backend gera uma chave SSH própria (a privada fica no volume `backend-ssh` e nunca sai pela API; a pública aparece
no painel para ser cadastrada no servidor). Conectado, o Ollama do servidor fica em `0.0.0.0:<GPU_TUNNEL_PORT>` dentro
do container do backend: só a rede do Docker o alcança, e a porta do Ollama do servidor não precisa abrir na internet.
A chave do servidor é aceita na primeira conexão e conferida nas seguintes; se mudar, o túnel não abre até a pessoa
aceitar a nova no painel.
"""

import asyncio
import contextlib
import logging
import re
import shlex
import threading
from collections.abc import Coroutine
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import asyncssh

from app.core.errors import AppError, ConflictError, InvalidDataError, OllamaUnavailableError
from app.repositories.setting_repository import SettingRepository
from app.schemas.gpu import GpuStatus, TunnelState

logger = logging.getLogger(__name__)

HOST_PATTERN = r"^([A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?|[0-9A-Fa-f:]{2,39})$"
USER_PATTERN = r"^[A-Za-z_][A-Za-z0-9_.-]{0,31}$"
KEYS = ("gpu.host", "gpu.port", "gpu.user", "gpu.enabled", "gpu.host_key")
KEY_COMMENT = "celke-treinar-ia-agro"
FIRST_RETRY_SECONDS = 5
MAX_RETRY_SECONDS = 60


@dataclass(frozen=True)
class GpuConfig:
    host: str
    port: int
    user: str

    @property
    def target(self) -> str:
        return f"{self.user}@{self.host}" + (f":{self.port}" if self.port != 22 else "")

    @property
    def known_hosts_pattern(self) -> str:
        return self.host if self.port == 22 else f"[{self.host}]:{self.port}"


class GpuTunnel:
    def __init__(
        self,
        settings: SettingRepository,
        key_dir: Path,
        listen_port: int,
        *,
        listen_host: str = "0.0.0.0",
        remote_port: int = 11434,
        connect_timeout: float = 15,
    ):
        self._settings = settings
        self._key_path = key_dir / "id_ed25519"
        self._listen = (listen_host, listen_port)
        self._remote_port = remote_port
        self._timeout = connect_timeout
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task | None = None
        self._lock = threading.RLock()
        self._state: TunnelState = "desconectado"
        self._message: str | None = None
        self._host_key_mismatch = False

    # Laço de eventos próprio, numa thread: as rotas são síncronas

    def start(self) -> None:
        with self._lock:
            if self._loop is None:
                self._loop = asyncio.new_event_loop()
                threading.Thread(target=self._loop.run_forever, name="tunel-gpu", daemon=True).start()
        try:
            values = self._settings.all()
        except AppError:
            return
        if self._config(values) and values.get("gpu.enabled") == "true":
            self._start_supervisor()

    def stop(self) -> None:
        if self._loop is None:
            return
        self._run(self._cancel())
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._loop = None

    def _run(self, coro: Coroutine[Any, Any, Any], timeout: float | None = None) -> Any:
        if self._loop is None:
            self.start()
        assert self._loop is not None
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout or self._timeout + 15)

    # Configuração

    @staticmethod
    def _config(values: dict[str, str]) -> GpuConfig | None:
        if not values.get("gpu.host"):
            return None
        return GpuConfig(values["gpu.host"], int(values.get("gpu.port") or 22), values.get("gpu.user") or "root")

    def config(self) -> GpuConfig | None:
        return self._config(self._settings.all())

    @property
    def configured(self) -> bool:
        try:
            return self.config() is not None
        except AppError:
            return False

    @property
    def connected(self) -> bool:
        return self._state == "conectado"

    @property
    def message(self) -> str | None:
        return self._message

    def public_key(self) -> str:
        """A chave pública do backend, criada na primeira vez. É ela que o servidor precisa aceitar."""
        with self._lock:
            if not self._key_path.exists():
                self._key_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                key = asyncssh.generate_private_key("ssh-ed25519", comment=KEY_COMMENT)
                key.write_private_key(str(self._key_path))
                self._key_path.chmod(0o600)
                logger.info("Chave SSH da GPU externa criada em %s", self._key_path)
            key = asyncssh.read_private_key(str(self._key_path))
            return key.export_public_key().decode().strip()

    def save(self, host: str, port: int, user: str) -> GpuStatus:
        """Cadastra (ou troca) o servidor e conecta. Trocar o endereço esquece a chave do servidor anterior."""
        if not re.fullmatch(HOST_PATTERN, host) or not re.fullmatch(USER_PATTERN, user) or not 0 < port < 65536:
            raise InvalidDataError("Endereço, porta ou usuário inválido.")
        old = self.config()
        values = {"gpu.host": host, "gpu.port": str(port), "gpu.user": user, "gpu.enabled": "true"}
        if old is None or (old.host, old.port) != (host, port):
            values["gpu.host_key"] = ""
        self._run(self._cancel())
        self._settings.save(values)
        self._start_supervisor()
        return self.status()

    def connect(self) -> GpuStatus:
        if self.config() is None:
            raise InvalidDataError("Cadastre o servidor da GPU externa antes de conectar.")
        self._settings.save({"gpu.enabled": "true"})
        self._run(self._cancel())
        self._start_supervisor()
        return self.status()

    def disconnect(self) -> GpuStatus:
        self._settings.save({"gpu.enabled": "false"})
        self._run(self._cancel())
        self._set(
            "desconectado", "Desconectado. Desligue também a instância no painel do provedor para parar a cobrança."
        )
        return self.status()

    def remove(self) -> GpuStatus:
        self._run(self._cancel())
        self._settings.delete(list(KEYS))
        self._set("desconectado", None)
        return self.status()

    def forget_host_key(self) -> GpuStatus:
        """Aceita a chave nova do servidor (por exemplo, a instância foi recriada com o mesmo IP)."""
        self._settings.save({"gpu.host_key": ""})
        self._host_key_mismatch = False
        return self.connect()

    def install_key(self, password: str) -> GpuStatus:
        """Entra uma vez com a senha e acrescenta a chave pública ao `authorized_keys`. A senha não é guardada."""
        config = self.config()
        if config is None:
            raise InvalidDataError("Cadastre o servidor da GPU externa antes de instalar a chave.")
        public_key = self.public_key()
        self._run(self._install_key(config, password, public_key))
        return self.connect()

    # Estado para a página Modelo de IA

    def _set(self, state: TunnelState, message: str | None) -> None:
        self._state, self._message = state, message

    def status(self) -> GpuStatus:
        try:
            values = self._settings.all()
        except AppError:
            values = {}  # banco fora do ar: a página de Status mostra o banco vermelho
        config = self._config(values)
        fingerprint = None
        if values.get("gpu.host_key"):
            fingerprint = asyncssh.import_public_key(values["gpu.host_key"]).get_fingerprint()
        return GpuStatus(
            configured=config is not None,
            host=config.host if config else None,
            port=config.port if config else 22,
            user=config.user if config else "root",
            state=self._state if config else "nao_configurado",
            message=self._message if config else None,
            public_key=self.public_key(),
            host_key_fingerprint=fingerprint,
            host_key_mismatch=self._host_key_mismatch,
            tunnel_port=self._listen[1],
        )

    # SSH

    def _start_supervisor(self) -> None:
        async def start() -> None:
            self._task = asyncio.get_running_loop().create_task(self._supervise())

        self._set("conectando", "Conectando…")
        self._run(start())

    async def _cancel(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        self._task = None

    async def _open(self, config: GpuConfig, **auth: Any) -> asyncssh.SSHClientConnection:
        trusted = self._settings.all().get("gpu.host_key")
        known_hosts = asyncssh.import_known_hosts(f"{config.known_hosts_pattern} {trusted}\n") if trusted else None
        conn = await asyncio.wait_for(
            asyncssh.connect(
                config.host,
                config.port,
                username=config.user,
                known_hosts=known_hosts,
                agent_path=None,
                keepalive_interval=30,
                keepalive_count_max=3,
                **auth,
            ),
            self._timeout,
        )
        if not trusted:  # primeira conexão: guarda a chave do servidor para conferir nas próximas
            host_key = conn.get_server_host_key()
            if host_key is not None:
                self._settings.save({"gpu.host_key": host_key.export_public_key().decode().strip()})
        self._host_key_mismatch = False
        return conn

    def _key_auth(self) -> dict[str, Any]:
        self.public_key()  # cria a chave, se faltar
        return {"client_keys": [str(self._key_path)], "password": None, "preferred_auth": "publickey"}

    async def _supervise(self) -> None:
        """Abre o túnel e o mantém aberto: se a conexão cair, tenta de novo com espera crescente."""
        delay = FIRST_RETRY_SECONDS
        while True:
            config = self.config()
            if config is None:
                return
            self._set("conectando", f"Conectando a {config.target}…")
            try:
                conn = await self._open(config, **self._key_auth())
            except asyncssh.HostKeyNotVerifiable:
                self._host_key_mismatch = True
                self._set(
                    "erro",
                    "A chave do servidor mudou desde a primeira conexão. Se a instância foi recriada, aceite a chave "
                    'nova ("Aceitar a chave nova"); se não, não conecte: pode ser outro servidor no mesmo endereço.',
                )
                return
            except asyncssh.PermissionDenied:
                self._set(
                    "erro",
                    "O servidor recusou a chave. Instale a chave com a senha do servidor ou cadastre a chave pública "
                    "no painel do provedor e clique em Conectar.",
                )
                return
            except (OSError, TimeoutError, asyncssh.Error) as exc:
                reason = str(exc) or type(exc).__name__
                self._set(
                    "erro",
                    f"Sem conexão com {config.target} ({reason}). A instância está ligada? Nova tentativa em {delay} s.",
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, MAX_RETRY_SECONDS)
                continue
            try:
                await conn.forward_local_port(self._listen[0], self._listen[1], "127.0.0.1", self._remote_port)
                self._set("conectado", f"Túnel aberto até {config.target}.")
                logger.info("Túnel da GPU externa aberto até %s", config.target)
                delay = FIRST_RETRY_SECONDS
                await conn.wait_closed()
                self._set("erro", f"A conexão com {config.target} caiu. Tentando de novo…")
            except OSError as exc:
                self._set("erro", f"Não foi possível abrir a porta do túnel: {exc}")
                await asyncio.sleep(delay)
            finally:
                conn.close()

    async def _install_key(self, config: GpuConfig, password: str, public_key: str) -> None:
        try:
            conn = await self._open(
                config, password=password, client_keys=None, preferred_auth="password,keyboard-interactive"
            )
        except asyncssh.HostKeyNotVerifiable as exc:
            self._host_key_mismatch = True
            raise ConflictError(
                "A chave do servidor mudou desde a primeira conexão. Aceite a chave nova antes."
            ) from exc
        except asyncssh.PermissionDenied as exc:
            raise InvalidDataError("O servidor recusou o usuário ou a senha.") from exc
        except (OSError, TimeoutError, asyncssh.Error) as exc:
            raise OllamaUnavailableError(
                f"Sem conexão com {config.target} ({exc or type(exc).__name__}). Confira o endereço e se a instância "
                "está ligada."
            ) from exc
        quoted = shlex.quote(public_key)
        command = (
            "umask 077 && mkdir -p ~/.ssh && touch ~/.ssh/authorized_keys && "
            f"(grep -qxF {quoted} ~/.ssh/authorized_keys || echo {quoted} >> ~/.ssh/authorized_keys)"
        )
        async with conn:
            result = await conn.run(command, check=False)
        if result.exit_status != 0:
            raise InvalidDataError(f"O servidor não aceitou a instalação da chave: {str(result.stderr or '').strip()}")
        logger.info("Chave SSH instalada em %s", config.target)
