"""Agendador: chuva todo dia; produção (PAM) e estimativa de safra (LSPA) uma vez por mês.

Roda numa thread do backend e confere a cada minuto, pelo registro das coletas no banco, se alguma está atrasada.
Reiniciar o backend não repete coleta já feita. Se a coleta falhar, tenta de novo depois de `RETRY_MINUTES`.
"""

import logging
import threading
from collections.abc import Callable
from datetime import datetime, timedelta

from app.core.config import Settings
from app.core.errors import AppError
from app.repositories.collection_repository import CollectionRepository
from app.schemas.collections import CollectionRun, CollectionSource
from app.services.collection_service import CollectionService

logger = logging.getLogger(__name__)

RETRY_MINUTES = 60
TICK_SECONDS = 60


def is_due(
    source: CollectionSource,
    now: datetime,
    last_success: CollectionRun | None,
    last_attempt: CollectionRun | None,
    settings: Settings,
) -> bool:
    """A coleta está atrasada? Diária a partir da hora configurada; mensal a partir do dia configurado."""
    if source == "chuva":
        if now.hour < settings.rain_collect_hour:
            return False
        slot_start = now.replace(hour=settings.rain_collect_hour, minute=0, second=0, microsecond=0)
    else:
        if now.day < settings.monthly_collect_day:
            return False
        slot_start = now.replace(day=settings.monthly_collect_day, hour=0, minute=0, second=0, microsecond=0)
    if last_success and last_success.started_at.astimezone(now.tzinfo) >= slot_start:
        return False
    if last_attempt and last_attempt.status == "executando":
        return False
    return not (
        last_attempt
        and last_attempt.status == "erro"
        and now - last_attempt.started_at.astimezone(now.tzinfo) < timedelta(minutes=RETRY_MINUTES)
    )


class Scheduler:
    def __init__(
        self,
        settings: Settings,
        collections: CollectionService,
        runs: CollectionRepository,
        clock: Callable[[], datetime],
    ):
        self._settings = settings
        self._collections = collections
        self._runs = runs
        self._clock = clock
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def tick(self) -> list[CollectionSource]:
        """Dispara as coletas atrasadas e devolve quais começaram."""
        started: list[CollectionSource] = []
        now = self._clock()
        for source in ("chuva", "producao", "estimativa"):
            if self._collections.is_running(source):
                continue
            if not is_due(
                source, now, self._runs.last(source, successful=True), self._runs.last(source), self._settings
            ):
                continue
            try:
                self._collections.trigger(source, "agendada")
                started.append(source)
            except AppError as exc:
                # sem município cadastrado ou coleta do cadastro em andamento: tenta no próximo minuto
                logger.debug("Coleta agendada de %s adiada: %s", source, exc.message)
        return started

    def _loop(self) -> None:
        while not self._stop.wait(TICK_SECONDS):
            try:
                self.tick()
            except Exception:
                logger.exception("Erro no agendador")

    def start(self) -> None:
        if not self._settings.scheduler_enabled or self._thread:
            return
        self._thread = threading.Thread(target=self._loop, name="agendador", daemon=True)
        self._thread.start()
        logger.info(
            "Agendador ligado: chuva às %sh, produção e estimativa no dia %s (%s)",
            self._settings.rain_collect_hour,
            self._settings.monthly_collect_day,
            self._settings.scheduler_timezone,
        )

    def stop(self) -> None:
        self._stop.set()
