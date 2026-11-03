import logging
import threading
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import Executor
from datetime import date, datetime, timedelta

from app.core.config import Settings
from app.core.domain import BRAZIL_CODE, MONTH_ABBR, STATES_BY_ACRONYM, STATES_BY_CODE
from app.core.errors import AppError, ConflictError, InvalidDataError, NotFoundError
from app.repositories.collection_repository import CollectionRepository
from app.repositories.crop_repository import CropRepository
from app.repositories.municipality_repository import MunicipalityRepository, StateReference
from app.repositories.weather_repository import WeatherRepository
from app.schemas.collections import CollectionOverview, CollectionRun, CollectionSource, CollectionTrigger, SourceStatus
from app.schemas.municipalities import IbgeMunicipality, Municipality
from app.services.public_data import IbgeSource, RainSource

logger = logging.getLogger(__name__)

RECENT_DAYS = 10
SIDRA_BATCH = 20
SOURCES: dict[CollectionSource, tuple[str, str]] = {
    "chuva": ("Chuva diária", "Open-Meteo (reanálise ERA5)"),
    "producao": ("Produção anual (PAM)", "IBGE · Produção Agrícola Municipal"),
    "estimativa": ("Estimativa da safra (LSPA)", "IBGE · Levantamento Sistemático da Produção Agrícola"),
}
BUSY = {
    "chuva": "Já existe uma coleta de chuva em andamento. Aguarde terminar.",
    "producao": "Já existe uma coleta de produção em andamento. Aguarde terminar.",
    "estimativa": "Já existe uma coleta da estimativa de safra em andamento. Aguarde terminar.",
}


class CollectionService:
    """Coletas dos dados públicos: no cadastro do município, pelo botão e pelo agendador. Uma por vez em cada fonte."""

    def __init__(
        self,
        settings: Settings,
        municipalities: MunicipalityRepository,
        weather: WeatherRepository,
        crops: CropRepository,
        runs: CollectionRepository,
        rain: RainSource,
        ibge: IbgeSource,
        executor: Executor,
        clock: Callable[[], datetime],
        on_new_data: Callable[[CollectionSource], None] | None = None,
    ):
        self._settings = settings
        self._municipalities = municipalities
        self._weather = weather
        self._crops = crops
        self._runs = runs
        self._rain = rain
        self._ibge = ibge
        self._executor = executor
        self._clock = clock
        self._on_new_data = on_new_data
        self._locks: dict[CollectionSource, threading.Lock] = {s: threading.Lock() for s in SOURCES}
        self._state_cache: dict[str, list[IbgeMunicipality]] = {}

    def today(self) -> date:
        return self._clock().date()

    # Municípios

    def state_municipalities(self, acronym: str) -> list[IbgeMunicipality]:
        acronym = acronym.upper()
        if acronym not in STATES_BY_ACRONYM:
            raise NotFoundError(f"UF {acronym} não existe.")
        if acronym not in self._state_cache:
            self._state_cache[acronym] = [
                IbgeMunicipality(code=c, name=n) for c, n in self._ibge.municipalities_of_state(acronym)
            ]
        return self._state_cache[acronym]

    def register(self, code: int) -> Municipality:
        """Cadastra e, em segundo plano, baixa o histórico de chuva e de produção."""
        existing = self._municipalities.get(code)
        if existing and existing.principal:
            raise ConflictError(f"{existing.name} ({existing.state}) já está cadastrado.")
        if existing:
            self._municipalities.upsert(
                code=code,
                name=existing.name,
                state_code=existing.state_code,
                state=existing.state,
                latitude=existing.latitude,
                longitude=existing.longitude,
                principal=True,
            )
        else:
            name, acronym = self._ibge.municipality(code)
            coordinates = self._rain.geocode(name, acronym)
            if coordinates is None:
                raise InvalidDataError(f"Não encontrei as coordenadas de {name} ({acronym}) no Open-Meteo.")
            self._municipalities.upsert(
                code=code,
                name=name,
                state_code=STATES_BY_ACRONYM[acronym].code,
                state=acronym,
                latitude=coordinates[0],
                longitude=coordinates[1],
                principal=True,
            )
        self._municipalities.set_status(code, "coletando", "Na fila para a coleta.")
        self._executor.submit(self._register_job, code)
        return self._municipalities.get(code)  # type: ignore[return-value]

    def remove(self, code: int) -> None:
        if not self._municipalities.remove_principal(code):
            raise NotFoundError("Município não encontrado.")

    def _register_job(self, code: int) -> None:
        m = self._municipalities.get(code)
        if m is None:
            return
        # O cadastro espera a coleta agendada da mesma fonte terminar, se houver.
        with self._locks["chuva"], self._locks["producao"]:
            try:
                self._municipalities.set_status(code, "coletando", "Escolhendo os municípios de referência da UF…")
                self._ensure_references(m.state_code)
                codes = [code] + [r.municipality_code for r in self._municipalities.references(m.state_code)]
                pending = [c for c in dict.fromkeys(codes) if self._weather.last_archive_day(c) is None]
                self._municipalities.set_status(
                    code, "coletando", f"Baixando a chuva diária desde {self._settings.history_start_year}…"
                )
                self._run("chuva", "cadastro", lambda: self._collect_rain(pending or [code]))
                self._municipalities.set_status(code, "coletando", "Baixando a produção de soja e milho do IBGE…")
                self._run("producao", "cadastro", self._collect_production)
            except AppError as exc:
                self._municipalities.set_status(code, "erro", exc.message)
                return
            except Exception:
                logger.exception("Erro no cadastro do município %s", code)
                self._municipalities.set_status(code, "erro", "Erro inesperado na coleta. Tente Coletar chuva.")
                return
        if self._locks["estimativa"].acquire(blocking=False):
            try:
                self._run("estimativa", "cadastro", self._collect_estimates)
            except AppError:
                pass  # a estimativa da safra é complemento: o município fica pronto mesmo assim
            finally:
                self._locks["estimativa"].release()
        self._municipalities.set_status(code, "pronto", None)

    def _ensure_references(self, state_code: int) -> None:
        if self._municipalities.references(state_code):
            return
        state = STATES_BY_CODE[state_code]
        year = self._ibge.pam_last_year()
        top = self._ibge.top_soy_municipalities(state_code, year, self._settings.state_reference_count)
        if not top:  # UF sem soja: tenta o ano anterior, que pode já ter sido divulgado por completo
            year -= 1
            top = self._ibge.top_soy_municipalities(state_code, year, self._settings.state_reference_count)
        references = []
        for code, name, area in top:
            if self._municipalities.get(code) is None:
                coordinates = self._rain.geocode(name, state.acronym)
                if coordinates is None:
                    logger.warning("Sem coordenadas para %s (%s): fica fora da média da UF", name, state.acronym)
                    continue
                self._municipalities.upsert(
                    code=code,
                    name=name,
                    state_code=state_code,
                    state=state.acronym,
                    latitude=coordinates[0],
                    longitude=coordinates[1],
                    principal=False,
                )
            references.append(StateReference(code, area, year))
        self._municipalities.replace_references(state_code, references)

    # Coletas pelo botão e pelo agendador

    def trigger(self, source: CollectionSource, trigger: CollectionTrigger = "botao") -> CollectionRun:
        """Começa a coleta em segundo plano. Recusa se a mesma fonte já estiver coletando."""
        if not self._municipalities.all():
            raise InvalidDataError("Cadastre um município antes de coletar dados.")
        lock = self._locks[source]
        if not lock.acquire(blocking=False):
            raise ConflictError(BUSY[source])
        try:
            run = self._runs.start(source, trigger)
            job = {
                "chuva": self._collect_rain,
                "producao": self._collect_production,
                "estimativa": self._collect_estimates,
            }
            self._executor.submit(self._finish_locked, run, lock, job[source])
        except BaseException:
            lock.release()
            raise
        return run

    def is_running(self, source: CollectionSource) -> bool:
        return self._locks[source].locked()

    def _finish_locked(self, run: CollectionRun, lock: threading.Lock, job: Callable[[], int]) -> None:
        try:
            self._execute(run, job)
        finally:
            lock.release()

    def _run(self, source: CollectionSource, trigger: CollectionTrigger, job: Callable[[], int]) -> int:
        """Coleta com registro, quando quem chama já tem a trava da fonte. Repassa o erro."""
        return self._execute(self._runs.start(source, trigger), job, raise_errors=True)

    def _execute(self, run: CollectionRun, job: Callable[[], int], raise_errors: bool = False) -> int:
        try:
            records = job()
        except AppError as exc:
            self._runs.finish(run.id, "erro", 0, exc.message)
            if raise_errors:
                raise
            return 0
        except Exception:
            logger.exception("Erro inesperado na coleta %s", run.source)
            self._runs.finish(run.id, "erro", 0, "Erro inesperado na coleta. Veja: docker compose logs backend")
            if raise_errors:
                raise
            return 0
        if records:
            self._runs.finish(run.id, "concluida", records, self._done_message(run.source, records))
            if self._on_new_data:
                try:
                    self._on_new_data(run.source)
                except Exception:
                    logger.exception("Erro ao atualizar descobertas e alertas")
        else:
            self._runs.finish(run.id, "sem_novidade", 0, self._no_news_message(run.source))
        return records

    def _done_message(self, source: CollectionSource, records: int) -> str:
        unit = {"chuva": "dias de chuva", "producao": "registros de produção", "estimativa": "registros de estimativa"}
        return f"{records} {unit[source]} novos ou atualizados."

    def _no_news_message(self, source: CollectionSource) -> str:
        if source == "producao":
            return f"Já está atualizado: último ano disponível {self._crops.last_year() or '–'}."
        if source == "estimativa":
            period = self._crops.last_period()
            label = f"{MONTH_ABBR[period % 100 - 1]}/{period // 100}" if period else "–"
            return f"Já está atualizado: último levantamento {label}."
        return "Já está atualizado: nenhum dia novo de chuva."

    def _collect_rain(self, codes: list[int] | None = None) -> int:
        records = 0
        today = self.today()
        for code in codes or self._municipalities.codes():
            m = self._municipalities.get(code)
            if m is None:
                continue
            last = self._weather.last_archive_day(code)
            start = last + timedelta(days=1) if last else date(self._settings.history_start_year, 1, 1)
            end = today - timedelta(days=1)
            if start <= end:
                records += self._weather.save(
                    code, self._rain.archive(m.latitude, m.longitude, start, end), source="arquivo"
                )
            records += self._weather.save(
                code, self._rain.recent(m.latitude, m.longitude, RECENT_DAYS), source="recente"
            )
        return records

    def _collect_production(self) -> int:
        """PAM de todos os municípios (principais e referências), das UFs com cadastro e do Brasil.

        Busca de novo os 2 últimos anos de cada território: o IBGE revisa o ano mais recente. Só conta o que mudou.
        """
        latest = self._ibge.pam_last_year()
        last_years = self._crops.last_years()
        territories = (
            [("municipio", c) for c in self._municipalities.codes()]
            + [("uf", s) for s in self._municipalities.state_codes()]
            + [("brasil", BRAZIL_CODE)]
        )
        groups: dict[tuple[str, int], list[int]] = defaultdict(list)
        for level, code in territories:
            last = last_years.get((level, code))
            start = min(last + 1, latest - 1) if last else self._settings.history_start_year
            groups[(level, start)].append(code)
        records = 0
        for (level, start), codes in groups.items():
            for i in range(0, len(codes), SIDRA_BATCH):
                rows = self._ibge.pam(level, codes[i : i + SIDRA_BATCH], start, latest)
                records += self._crops.save_yearly(rows)
        return records

    def _collect_estimates(self) -> int:
        months = 3 if self._crops.last_period() else 12
        states = self._municipalities.state_codes()
        rows = self._ibge.lspa("brasil", [BRAZIL_CODE], months)
        if states:
            rows += self._ibge.lspa("uf", states, months)
        return self._crops.save_estimates(rows)

    # Status

    def overview(self) -> CollectionOverview:
        rain_last = self._weather.last_day()
        last_year = self._crops.last_year()
        period = self._crops.last_period()
        last_data = {
            "chuva": rain_last.strftime("%d/%m/%Y") if rain_last else None,
            "producao": str(last_year) if last_year else None,
            "estimativa": f"{MONTH_ABBR[period % 100 - 1]}/{period // 100}" if period else None,
        }
        s = self._settings
        schedule = {
            "chuva": f"Todo dia às {s.rain_collect_hour}h",
            "producao": f"Todo dia {s.monthly_collect_day} do mês",
            "estimativa": f"Todo dia {s.monthly_collect_day} do mês",
        }
        if not s.scheduler_enabled:
            schedule = dict.fromkeys(schedule, "Agendamento desligado")
        return CollectionOverview(
            sources=[
                SourceStatus(
                    source=source,
                    name=name,
                    provider=provider,
                    schedule=schedule[source],
                    last_data=last_data[source],
                    running=self.is_running(source),
                    last_run=self._runs.last(source),
                )
                for source, (name, provider) in SOURCES.items()
            ],
            runs=self._runs.recent(),
        )
