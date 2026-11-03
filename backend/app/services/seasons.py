"""Contas da safra a partir da chuva diária e da produção anual. Funções puras, sem banco: fáceis de testar."""

import calendar
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from app.core.domain import DRY_DAY_MM, Crop
from app.repositories.crop_repository import CropYear
from app.repositories.weather_repository import DailyRain
from app.services.statistics import linear_fit, mean, percent_change

Month = tuple[int, int]


@dataclass(frozen=True)
class MonthlyRain:
    total: float
    days: int
    complete: bool


def monthly_totals(daily: DailyRain) -> dict[Month, MonthlyRain]:
    """Soma por mês; o mês só é completo se tiver todos os dias."""
    sums: dict[Month, float] = defaultdict(float)
    counts: dict[Month, int] = defaultdict(int)
    for day, mm in daily:
        sums[(day.year, day.month)] += mm
        counts[(day.year, day.month)] += 1
    return {m: MonthlyRain(round(sums[m], 1), counts[m], counts[m] == calendar.monthrange(*m)[1]) for m in sorted(sums)}


def season_rain(monthly: dict[Month, MonthlyRain], crop: Crop, year: int) -> float | None:
    """Chuva da janela da safra `year`. `None` se faltar algum dia."""
    months = [monthly.get(m) for m in crop.window_months(year)]
    if any(m is None or not m.complete for m in months):
        return None
    return round(sum(m.total for m in months), 1)  # type: ignore[union-attr]


def window_days(crop: Crop, year: int) -> tuple[date, date]:
    (first_y, first_m), (last_y, last_m) = crop.window_months(year)[0], crop.window_months(year)[-1]
    return date(first_y, first_m, 1), date(last_y, last_m, calendar.monthrange(last_y, last_m)[1])


def longest_dry_spell(by_day: dict[date, float], start: date, end: date) -> int | None:
    """Maior sequência de dias com menos de 1 mm entre `start` e `end`. `None` se faltar algum dia."""
    longest = current = 0
    day = start
    while day <= end:
        mm = by_day.get(day)
        if mm is None:
            return None
        current = current + 1 if mm < DRY_DAY_MM else 0
        longest = max(longest, current)
        day += timedelta(days=1)
    return longest


def current_dry_spell(by_day: dict[date, float], until: date, start: date) -> int:
    """Dias seguidos sem chuva terminando em `until`, sem passar de `start`."""
    count = 0
    day = until
    while day >= start and by_day.get(day) is not None and by_day[day] < DRY_DAY_MM:
        count += 1
        day -= timedelta(days=1)
    return count


def weighted_state_rain(values: list[tuple[float | None, float]]) -> float | None:
    """Média ponderada pela área; exige dado de referências que somem ao menos metade da área."""
    total_weight = sum(w for _, w in values)
    available = [(v, w) for v, w in values if v is not None]
    weight = sum(w for _, w in available)
    if not available or total_weight == 0 or weight < total_weight / 2:
        return None
    return round(sum(v * w for v, w in available) / weight, 1)  # type: ignore[operator]


@dataclass
class Season:
    year: int
    rain_mm: float | None = None
    rain_state_mm: float | None = None
    rain_anomaly_pct: float | None = None
    dry_spell_days: int | None = None
    planting_rain_mm: float | None = None
    month_rain: dict[int, float] | None = None
    production_t: float | None = None
    yield_kg_ha: float | None = None
    yield_state_kg_ha: float | None = None
    yield_brazil_kg_ha: float | None = None
    trend_kg_ha: float | None = None
    yield_anomaly_pct: float | None = None


def build_seasons(
    crop: Crop,
    daily: DailyRain,
    municipal: list[CropYear],
    *,
    state: list[CropYear] | None = None,
    brazil: list[CropYear] | None = None,
    state_rain: dict[int, float | None] | None = None,
) -> list[Season]:
    """Uma linha por safra com chuva da janela, veranico, rendimento, tendência e desvio da tendência."""
    monthly = monthly_totals(daily)
    by_day = dict(daily)
    yields = {c.year: c for c in municipal if c.yield_kg_ha}
    years = sorted(set(yields) | {y for y in {m[0] for m in monthly} | {m[0] + 1 for m in monthly}})
    state_y = {c.year: c.yield_kg_ha for c in state or [] if c.yield_kg_ha}
    brazil_y = {c.year: c.yield_kg_ha for c in brazil or [] if c.yield_kg_ha}

    seasons: list[Season] = []
    for year in years:
        rain = season_rain(monthly, crop, year)
        crop_year = yields.get(year)
        if rain is None and crop_year is None:
            continue
        start, end = window_days(crop, year)
        planting = monthly.get((year + crop.planting_month[0], crop.planting_month[1]))
        seasons.append(
            Season(
                year=year,
                rain_mm=rain,
                rain_state_mm=(state_rain or {}).get(year),
                dry_spell_days=longest_dry_spell(by_day, start, end) if rain is not None else None,
                planting_rain_mm=planting.total if planting and planting.complete else None,
                month_rain={m: monthly[(y, m)].total for y, m in crop.window_months(year)}
                if rain is not None
                else None,
                production_t=crop_year.production_t if crop_year else None,
                yield_kg_ha=crop_year.yield_kg_ha if crop_year else None,
                yield_state_kg_ha=state_y.get(year),
                yield_brazil_kg_ha=brazil_y.get(year),
            )
        )

    rains = [s.rain_mm for s in seasons if s.rain_mm is not None]
    average_rain = mean(rains)
    fit = linear_fit([s.year for s in seasons if s.yield_kg_ha], [s.yield_kg_ha for s in seasons if s.yield_kg_ha])
    for s in seasons:
        if s.rain_mm is not None and average_rain:
            s.rain_anomaly_pct = round(percent_change(s.rain_mm, average_rain) or 0, 1)
        if fit and s.yield_kg_ha:
            s.trend_kg_ha = round(fit.at(s.year), 1)
            s.yield_anomaly_pct = round(percent_change(s.yield_kg_ha, s.trend_kg_ha) or 0, 1)
    return seasons


def state_season_rain(
    crop: Crop, references: list[tuple[DailyRain, float]], years: list[int]
) -> dict[int, float | None]:
    """Chuva média da UF em cada safra: referências ponderadas pela área de soja."""
    monthly = [(monthly_totals(daily), area) for daily, area in references]
    return {y: weighted_state_rain([(season_rain(m, crop, y), area) for m, area in monthly]) for y in years}


def climatology(monthly: dict[Month, MonthlyRain]) -> dict[int, float]:
    """Média de cada mês do ano, só com meses completos."""
    by_month: dict[int, list[float]] = defaultdict(list)
    for (_, m), value in monthly.items():
        if value.complete:
            by_month[m].append(value.total)
    return {m: round(sum(v) / len(v), 1) for m, v in by_month.items()}


@dataclass(frozen=True)
class SeasonToDate:
    season_year: int
    start: date
    until: date
    rain_mm: float
    normal_mm: float
    deviation_pct: float
    dry_spell_days: int
    # chuva média das safras passadas nos mesmos dias do veranico atual: perto de zero = trecho seco todo ano
    dry_spell_normal_mm: float
    past: dict[int, float]  # desvio (%) de cada safra passada no mesmo trecho da janela


def season_to_date(crop: Crop, daily: DailyRain, today: date) -> SeasonToDate | None:
    """Safra em andamento: chuva da janela até o último dia com dado, comparada ao mesmo trecho das safras passadas."""
    by_day = dict(daily)
    if not by_day:
        return None
    last = max(d for d in by_day if d <= today) if any(d <= today for d in by_day) else None
    if last is None:
        return None
    for year in (last.year, last.year + 1):
        start, end = window_days(crop, year)
        if start <= last <= end:
            break
    else:
        return None
    span = (last - start).days
    if span < 14:  # pouco tempo de janela: comparação instável
        return None

    def total(first: date) -> float | None:
        values = [by_day.get(first + timedelta(days=i)) for i in range(span + 1)]
        return None if any(v is None for v in values) else sum(values)  # type: ignore[arg-type]

    current = total(start)
    if current is None:
        return None
    past: dict[int, float] = {}
    for past_year in range(year - 40, year):
        past_start = window_days(crop, past_year)[0]
        value = total(past_start)
        if value is not None:
            past[past_year] = value
    if len(past) < 5:
        return None
    normal = sum(past.values()) / len(past)
    if normal <= 0:
        return None
    dry = current_dry_spell(by_day, last, start)
    dry_normal = []
    for past_year in past:
        offset = window_days(crop, past_year)[0] - start
        values = [by_day.get(last + offset - timedelta(days=i)) for i in range(dry)]
        if values and all(v is not None for v in values):
            dry_normal.append(sum(values))  # type: ignore[arg-type]
    return SeasonToDate(
        season_year=year,
        start=start,
        until=last,
        rain_mm=round(current, 1),
        normal_mm=round(normal, 1),
        deviation_pct=round((current - normal) / normal * 100, 1),
        dry_spell_days=dry,
        dry_spell_normal_mm=round(sum(dry_normal) / len(dry_normal), 1) if dry_normal else 0.0,
        past={y: round((v - normal) / normal * 100, 1) for y, v in past.items()},
    )
