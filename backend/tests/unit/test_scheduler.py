from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.config import Settings
from app.schemas.collections import CollectionRun
from app.services.scheduler import is_due

TZ = ZoneInfo("America/Sao_Paulo")
SETTINGS = Settings(rain_collect_hour=6, monthly_collect_day=1)


def run(started: datetime, status="concluida", source="chuva"):
    return CollectionRun(id="x", source=source, trigger="agendada", status=status, records=1, started_at=started)


def test_daily_rain_after_the_hour_once_a_day():
    now = datetime(2024, 12, 15, 7, 0, tzinfo=TZ)
    assert not is_due("chuva", now.replace(hour=5), None, None, SETTINGS)
    assert is_due("chuva", now, None, None, SETTINGS)
    yesterday = run(now - timedelta(days=1))
    assert is_due("chuva", now, yesterday, yesterday, SETTINGS)
    today = run(now.replace(hour=6, minute=1))
    assert not is_due("chuva", now, today, today, SETTINGS)


def test_button_today_counts_as_done():
    now = datetime(2024, 12, 15, 9, 0, tzinfo=TZ)
    by_button = run(now.replace(hour=6, minute=30)).model_copy(update={"trigger": "botao"})
    assert not is_due("chuva", now, by_button, by_button, SETTINGS)


def test_monthly_once_a_month():
    now = datetime(2024, 12, 3, 10, 0, tzinfo=TZ)
    last_month = run(datetime(2024, 11, 1, 0, 1, tzinfo=TZ), source="producao")
    assert is_due("producao", now, last_month, last_month, SETTINGS)
    this_month = run(datetime(2024, 12, 1, 0, 1, tzinfo=TZ), source="producao")
    assert not is_due("producao", now, this_month, this_month, SETTINGS)


def test_error_waits_before_retrying():
    now = datetime(2024, 12, 15, 8, 0, tzinfo=TZ)
    failed = run(now - timedelta(minutes=10), status="erro")
    assert not is_due("chuva", now, None, failed, SETTINGS)
    failed = run(now - timedelta(minutes=61), status="erro")
    assert is_due("chuva", now, None, failed, SETTINGS)
    running = run(now - timedelta(minutes=1), status="executando")
    assert not is_due("chuva", now, None, running, SETTINGS)


def test_tick_starts_due_collections(client, registered, container):
    # o relógio dos testes está em 2024; as coletas do cadastro ficam fora do horário agendado
    with container.database.connection() as conn:
        conn.execute("DELETE FROM collection_runs")
    started = container.scheduler.tick()
    assert set(started) == {"chuva", "producao", "estimativa"}
    assert container.scheduler.tick() == []  # já coletadas hoje e neste mês
    triggers = {r["trigger"] for r in client.get("/api/collections").json()["runs"]}
    assert "agendada" in triggers


def test_tick_without_municipalities_does_nothing(container):
    assert container.scheduler.tick() == []
