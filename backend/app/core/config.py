from functools import lru_cache
from typing import Literal

from psycopg.conninfo import make_conninfo
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração lida das variáveis de ambiente (ver `.env.example`)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Ollama deste computador. O da GPU externa é cadastrado na página Modelo de IA, assim como qual dos dois usar e o
    # modelo de cada um.
    ollama_url: str = "http://ollama:11434"
    # GPU externa: chave SSH gerada pelo backend (volume backend-ssh) e porta do túnel dentro da rede do Docker
    ssh_key_dir: str = "/data/ssh"
    gpu_tunnel_port: int = 11435
    ollama_timeout_seconds: float = 300.0
    # Modelo usado enquanto nenhum for escolhido na página Modelo de IA
    chat_model: str = "qwen3:8b"
    # Janela de contexto do modelo. O padrão do Ollama corta os resultados das ferramentas sem avisar.
    chat_num_ctx: int = 8192
    chat_temperature: float = 0.2
    # false = mais rápido e escolhe as ferramentas igual; auto = usa o raciocínio se o modelo tiver.
    chat_think: Literal["auto", "true", "false"] = "false"
    history_max_messages: int = 6
    max_tool_rounds: int = 5

    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "celke_agro"
    postgres_user: str = "celke"
    postgres_password: str = ""

    # Coleta de dados públicos
    history_start_year: int = 2000
    state_reference_count: int = 5
    http_timeout_seconds: float = 60.0

    # Agendamento: chuva todo dia; produção e estimativa de safra uma vez por mês.
    scheduler_enabled: bool = True
    scheduler_timezone: str = "America/Sao_Paulo"
    rain_collect_hour: int = 6
    monthly_collect_day: int = 1

    # Descobertas: filtro estatístico das relações testadas
    discovery_max_q: float = 0.10
    discovery_min_abs_r: float = 0.4
    discovery_min_years: int = 8

    # Alertas da safra em andamento
    alert_rain_deficit_pct: float = 25.0
    alert_dry_spell_days: int = 10

    # Vazio = sem CORS (o navegador acessa a API pelo proxy do frontend, na mesma origem).
    cors_origins: str = ""

    @property
    def database_conninfo(self) -> str:
        return make_conninfo(
            host=self.postgres_host,
            port=self.postgres_port,
            dbname=self.postgres_db,
            user=self.postgres_user,
            password=self.postgres_password,
            application_name="celke-treinar-ia-agro",
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
