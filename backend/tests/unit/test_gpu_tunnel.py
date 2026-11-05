"""O túnel da GPU externa contra um servidor SSH de verdade (asyncssh), na própria máquina do teste.

O servidor aceita a senha "senha" e as chaves de `authorized`, trata o comando de instalar a chave e encaminha a porta
do túnel até um servidor de eco, no lugar do Ollama.
"""

import asyncio
import re
import socket
import threading
import time

import asyncssh
import pytest

from app.core.errors import InvalidDataError
from app.repositories.setting_repository import SettingRepository
from app.services.gpu_tunnel import GpuTunnel


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FakeSshServer:
    def __init__(self):
        self.authorized: set[str] = set()
        self.commands: list[str] = []
        self.port = free_port()
        self.echo_port = free_port()
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, daemon=True).start()
        self._server = None
        self._run(self._start_echo())
        self.start()

    def _run(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(10)

    async def _start_echo(self):
        async def echo(reader, writer):
            writer.write(await reader.read(100))
            await writer.drain()
            writer.close()

        self._echo = await asyncio.start_server(echo, "127.0.0.1", self.echo_port)

    def start(self) -> None:
        """Sobe (ou sobe de novo) com uma chave de servidor nova: como uma instância recriada no mesmo IP."""
        outer = self

        class Server(asyncssh.SSHServer):
            def begin_auth(self, username):
                return True

            def password_auth_supported(self):
                return True

            def validate_password(self, username, password):
                return username == "root" and password == "senha"

            def public_key_auth_supported(self):
                return True

            def validate_public_key(self, username, key):
                # como no authorized_keys: vale o tipo e a chave, não o comentário
                offered = key.export_public_key().decode().split()[:2]
                return any(k.split()[:2] == offered for k in outer.authorized)

            def connection_requested(self, dest_host, dest_port, orig_host, orig_port):
                return True

        def handle(process):
            outer.commands.append(process.command)
            match = re.search(r"echo '([^']+)' >>", process.command)
            if match:
                outer.authorized.add(match.group(1))
            process.exit(0)

        async def start():
            if self._server:
                self._server.close()
                await self._server.wait_closed()
            self._server = await asyncssh.create_server(
                Server,
                "127.0.0.1",
                self.port,
                server_host_keys=[asyncssh.generate_private_key("ssh-ed25519")],
                process_factory=handle,
            )

        self._run(start())

    def stop(self) -> None:
        async def stop():
            self._server.close()
            self._echo.close()

        self._run(stop())
        self._loop.call_soon_threadsafe(self._loop.stop)


@pytest.fixture
def ssh_server():
    server = FakeSshServer()
    yield server
    server.stop()


@pytest.fixture
def tunnel(database, tmp_path, ssh_server):
    t = GpuTunnel(
        SettingRepository(database),
        tmp_path / "ssh",
        free_port(),
        listen_host="127.0.0.1",
        remote_port=ssh_server.echo_port,
        connect_timeout=5,
    )
    yield t
    t.stop()


def wait_state(tunnel: GpuTunnel, *states: str) -> str:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if tunnel.status().state in states:
            return tunnel.status().state
        time.sleep(0.05)
    raise AssertionError(f"Túnel parado em {tunnel.status().state}: {tunnel.status().message}")


def through_tunnel(tunnel: GpuTunnel) -> bytes:
    with socket.create_connection(("127.0.0.1", tunnel.status().tunnel_port), timeout=5) as s:
        s.sendall(b"ollama")
        return s.recv(100)


def test_key_is_created_once_and_private_key_never_leaves(tunnel, tmp_path):
    key = tunnel.public_key()
    assert key.startswith("ssh-ed25519 ") and key.endswith("celke-treinar-ia-agro")
    assert tunnel.public_key() == key
    assert (tmp_path / "ssh" / "id_ed25519").stat().st_mode & 0o777 == 0o600
    assert "PRIVATE" not in tunnel.status().model_dump_json()


def test_not_configured(tunnel):
    status = tunnel.status()
    assert status.configured is False
    assert status.state == "nao_configurado"
    with pytest.raises(InvalidDataError):
        tunnel.connect()
    with pytest.raises(InvalidDataError):
        tunnel.save("host com espaço", 22, "root")


def test_install_key_with_password_and_open_tunnel(tunnel, ssh_server):
    # sem a chave no servidor: recusa e para de tentar
    tunnel.save("127.0.0.1", ssh_server.port, "root")
    assert wait_state(tunnel, "erro", "conectado") == "erro"
    assert "recusou a chave" in tunnel.status().message

    with pytest.raises(InvalidDataError, match="usuário ou a senha"):
        tunnel.install_key("errada")
    tunnel.install_key("senha")
    assert tunnel.public_key() in ssh_server.authorized
    assert "senha" not in " ".join(ssh_server.commands)

    assert wait_state(tunnel, "conectado", "erro") == "conectado"
    assert through_tunnel(tunnel) == b"ollama"
    status = tunnel.status()
    assert status.host_key_fingerprint.startswith("SHA256:")
    assert tunnel.connected

    tunnel.disconnect()
    assert tunnel.status().state == "desconectado"
    with pytest.raises(OSError):
        through_tunnel(tunnel)

    tunnel.remove()
    assert tunnel.status().state == "nao_configurado"


def test_reconnects_after_restart_and_blocks_changed_host_key(tunnel, ssh_server, database, tmp_path):
    ssh_server.authorized.add(tunnel.public_key())
    tunnel.save("127.0.0.1", ssh_server.port, "root")
    assert wait_state(tunnel, "conectado", "erro") == "conectado"
    first = tunnel.status().host_key_fingerprint

    # backend reiniciado: o túnel volta sozinho, porque estava conectado
    tunnel.stop()
    restarted = GpuTunnel(
        SettingRepository(database),
        tmp_path / "ssh",
        tunnel.status().tunnel_port,
        listen_host="127.0.0.1",
        remote_port=ssh_server.echo_port,
        connect_timeout=5,
    )
    try:
        restarted.start()
        assert wait_state(restarted, "conectado", "erro") == "conectado"
        assert through_tunnel(restarted) == b"ollama"

        # servidor com outra chave no mesmo endereço: não conecta até a pessoa aceitar a chave nova
        restarted.disconnect()
        ssh_server.start()
        restarted.connect()
        assert wait_state(restarted, "erro", "conectado") == "erro"
        assert restarted.status().host_key_mismatch is True
        assert "chave do servidor mudou" in restarted.status().message

        restarted.forget_host_key()
        assert wait_state(restarted, "conectado", "erro") == "conectado"
        assert restarted.status().host_key_fingerprint != first
    finally:
        restarted.stop()


def test_disconnect_and_remove_go_back_to_local(client, selector):
    selector.select("externo", "qwen3:8b")
    client.post("/api/gpu/disconnect")
    assert selector.current() == ("local", "qwen3:8b")
    selector.select("externo", "qwen3:8b")
    client.delete("/api/gpu")
    assert selector.current() == ("local", "qwen3:8b")


def test_gpu_routes(client):
    data = client.get("/api/gpu").json()
    assert data["state"] == "nao_configurado"
    assert data["public_key"].startswith("ssh-ed25519 ")
    assert client.get("/api/status").json()["gpu"]["configured"] is False
    response = client.post("/api/gpu", json={"host": "203.0.113.10; rm -rf /", "port": 22, "user": "root"})
    assert response.status_code == 422
    response = client.post("/api/gpu/connect")
    assert response.status_code == 422
