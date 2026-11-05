import logging
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, PoolTimeout

from app.core.errors import DatabaseUnavailableError

logger = logging.getLogger(__name__)

UNAVAILABLE_MESSAGE = "O banco de dados (PostgreSQL) não está respondendo. Verifique: docker compose logs postgres"

# Idempotente: roda a cada inicialização do backend.
SCHEMA = """
CREATE TABLE IF NOT EXISTS municipalities (
    code INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    state_code INTEGER NOT NULL,
    state TEXT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    -- principal = cadastrado pela pessoa; os demais são só referência da chuva média da UF
    principal BOOLEAN NOT NULL DEFAULT false,
    status TEXT NOT NULL DEFAULT 'pronto' CHECK (status IN ('coletando', 'pronto', 'erro')),
    status_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Municípios que mais plantam soja na UF: a chuva média da UF é a média deles, ponderada pela área.
CREATE TABLE IF NOT EXISTS state_references (
    state_code INTEGER NOT NULL,
    municipality_code INTEGER NOT NULL REFERENCES municipalities (code) ON DELETE CASCADE,
    area_ha DOUBLE PRECISION NOT NULL,
    year INTEGER NOT NULL,
    PRIMARY KEY (state_code, municipality_code)
);

CREATE TABLE IF NOT EXISTS weather_daily (
    municipality_code INTEGER NOT NULL REFERENCES municipalities (code) ON DELETE CASCADE,
    day DATE NOT NULL,
    precipitation_mm DOUBLE PRECISION NOT NULL,
    -- arquivo = reanálise ERA5 (definitivo); recente = previsão dos últimos dias, trocada pelo arquivo depois
    source TEXT NOT NULL CHECK (source IN ('arquivo', 'recente')),
    PRIMARY KEY (municipality_code, day)
);

-- Produção Agrícola Municipal (PAM/IBGE), anual. level: municipio, uf ou brasil.
CREATE TABLE IF NOT EXISTS crop_yearly (
    level TEXT NOT NULL CHECK (level IN ('municipio', 'uf', 'brasil')),
    territory_code INTEGER NOT NULL,
    crop TEXT NOT NULL,
    year INTEGER NOT NULL,
    planted_area_ha DOUBLE PRECISION,
    harvested_area_ha DOUBLE PRECISION,
    production_t DOUBLE PRECISION,
    yield_kg_ha DOUBLE PRECISION,
    PRIMARY KEY (level, territory_code, crop, year)
);

-- Levantamento Sistemático da Produção Agrícola (LSPA/IBGE): estimativa mensal da safra do ano.
CREATE TABLE IF NOT EXISTS crop_estimates (
    level TEXT NOT NULL CHECK (level IN ('uf', 'brasil')),
    territory_code INTEGER NOT NULL,
    product TEXT NOT NULL,
    period INTEGER NOT NULL,
    planted_area_ha DOUBLE PRECISION,
    harvested_area_ha DOUBLE PRECISION,
    production_t DOUBLE PRECISION,
    yield_kg_ha DOUBLE PRECISION,
    PRIMARY KEY (level, territory_code, product, period)
);

CREATE TABLE IF NOT EXISTS collection_runs (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL CHECK (source IN ('chuva', 'producao', 'estimativa')),
    trigger TEXT NOT NULL CHECK (trigger IN ('agendada', 'botao', 'cadastro')),
    status TEXT NOT NULL CHECK (status IN ('executando', 'concluida', 'sem_novidade', 'erro')),
    records INTEGER NOT NULL DEFAULT 0,
    message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS collection_runs_started_idx ON collection_runs (started_at DESC);

CREATE TABLE IF NOT EXISTS discovery_reports (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('gerando', 'pronto', 'erro')),
    model TEXT NOT NULL,
    tests INTEGER NOT NULL DEFAULT 0,
    summary TEXT,
    next_questions JSONB NOT NULL DEFAULT '[]',
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS discoveries (
    id TEXT PRIMARY KEY,
    report_id TEXT NOT NULL REFERENCES discovery_reports (id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    municipality_code INTEGER NOT NULL,
    crop TEXT NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    fact TEXT NOT NULL,
    stats JSONB NOT NULL DEFAULT '{}',
    chart JSONB,
    interpretation TEXT,
    hypothesis TEXT
);

CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    municipality_code INTEGER NOT NULL REFERENCES municipalities (code) ON DELETE CASCADE,
    crop TEXT NOT NULL,
    kind TEXT NOT NULL,
    season_year INTEGER NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('warn', 'err')),
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    facts JSONB NOT NULL DEFAULT '{}',
    chart JSONB,
    explanation TEXT,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (municipality_code, crop, kind, season_year)
);

-- Cada treino do modelo de previsão da safra: variáveis escolhidas, coeficientes, erro da validação e previsões.
CREATE TABLE IF NOT EXISTS forecast_models (
    id TEXT PRIMARY KEY,
    municipality_code INTEGER NOT NULL REFERENCES municipalities (code) ON DELETE CASCADE,
    crop TEXT NOT NULL,
    trigger TEXT NOT NULL CHECK (trigger IN ('coleta', 'botao')),
    model TEXT NOT NULL,
    -- tudo o que o treino produziu (TrainedForecast em schemas/forecasts.py)
    result JSONB NOT NULL,
    explanation TEXT,
    trained_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS forecast_models_idx ON forecast_models (municipality_code, crop, trained_at DESC);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS conversations_updated_at_idx ON conversations (updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    -- ordem das mensagens na conversa
    seq BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id TEXT NOT NULL UNIQUE,
    conversation_id TEXT NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('concluida', 'erro')),
    error_message TEXT,
    -- ferramentas chamadas para a resposta (nome, argumentos, resumo) e gráficos mostrados
    tool_calls JSONB NOT NULL DEFAULT '[]',
    charts JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS messages_conversation_idx ON messages (conversation_id, seq);

-- Escolhas feitas no painel (Ollama em uso e modelo de cada Ollama). Valem até a próxima troca, mesmo reiniciando.
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

TABLES = (
    "municipalities, state_references, weather_daily, crop_yearly, crop_estimates, collection_runs, "
    "discovery_reports, discoveries, alerts, forecast_models, conversations, messages, app_settings"
)


class Database:
    """Pool de conexões com o PostgreSQL, compartilhado pelos repositórios."""

    def __init__(self, conninfo: str, *, max_size: int = 10, connect_timeout: float = 30):
        # Abre já esperando a primeira conexão: sem banco, o backend nem sobe.
        self._pool = ConnectionPool(
            conninfo,
            min_size=1,
            max_size=max_size,
            kwargs={"row_factory": dict_row},
            timeout=connect_timeout,
            open=False,
            name="celke-treinar-ia-agro",
        )
        try:
            self._pool.open(wait=True, timeout=connect_timeout)
        except PoolTimeout as exc:
            self._pool.close()
            raise DatabaseUnavailableError(UNAVAILABLE_MESSAGE) from exc

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection]:
        """Uma transação: commit no fim do bloco, rollback se der erro."""
        try:
            with self._pool.connection() as conn:
                yield conn
        except (PoolTimeout, psycopg.OperationalError) as exc:
            logger.warning("Falha de conexão com o PostgreSQL: %s", exc)
            raise DatabaseUnavailableError(UNAVAILABLE_MESSAGE) from exc

    def create_schema(self) -> None:
        with self.connection() as conn:
            conn.execute(SCHEMA)

    def ping(self) -> None:
        with self.connection() as conn:
            conn.execute("SELECT 1")

    def close(self) -> None:
        self._pool.close()
