from datetime import date, timedelta

from app.core.domain import CROPS
from app.repositories.crop_repository import CropYear
from app.services.seasons import (
    build_seasons,
    current_dry_spell,
    longest_dry_spell,
    monthly_totals,
    season_rain,
    season_to_date,
    weighted_state_rain,
)
from tests.fakes import synthetic_rain

SOJA = CROPS["soja"]


def days(start: date, values: list[float]):
    return [(start + timedelta(days=i), v) for i, v in enumerate(values)]


def test_monthly_totals_marks_incomplete_months():
    daily = days(date(2024, 1, 1), [1.0] * 31) + days(date(2024, 2, 1), [2.0] * 10)
    monthly = monthly_totals(daily)
    assert monthly[(2024, 1)].total == 31
    assert monthly[(2024, 1)].complete
    assert not monthly[(2024, 2)].complete


def test_soy_season_starts_in_october_of_previous_year():
    assert SOJA.window_months(2024)[0] == (2023, 10)
    assert SOJA.window_months(2024)[-1] == (2024, 3)
    daily = synthetic_rain(1, date(2023, 10, 1), date(2024, 3, 31))
    assert season_rain(monthly_totals(daily), SOJA, 2024) == round(sum(mm for _, mm in daily), 1)
    # faltando março, a safra fica sem chuva (nunca soma parcial)
    partial = [d for d in daily if d[0] < date(2024, 3, 31)]
    assert season_rain(monthly_totals(partial), SOJA, 2024) is None


def test_dry_spells():
    by_day = dict(days(date(2024, 1, 1), [5, 0, 0.5, 0, 3, 0, 0, 0, 0, 2]))
    assert longest_dry_spell(by_day, date(2024, 1, 1), date(2024, 1, 10)) == 4
    assert longest_dry_spell(by_day, date(2024, 1, 1), date(2024, 1, 11)) is None  # falta o dia 11
    assert current_dry_spell(by_day, date(2024, 1, 9), date(2024, 1, 1)) == 4


def test_weighted_state_rain_needs_half_of_the_area():
    assert weighted_state_rain([(100, 3), (200, 1)]) == 125
    assert weighted_state_rain([(100, 1), (None, 3)]) is None


def test_build_seasons_computes_trend_and_anomaly():
    daily = synthetic_rain(1, date(2010, 1, 1), date(2020, 12, 31))
    municipal = [CropYear("municipio", 1, "soja", y, yield_kg_ha=3000 + 50 * (y - 2010)) for y in range(2011, 2021)]
    municipal[4] = CropYear("municipio", 1, "soja", 2015, yield_kg_ha=2500)
    seasons = {s.year: s for s in build_seasons(SOJA, daily, municipal)}
    assert seasons[2015].yield_anomaly_pct < -10
    assert seasons[2016].rain_mm is not None
    assert seasons[2016].dry_spell_days is not None
    assert seasons[2016].month_rain.keys() == {10, 11, 12, 1, 2, 3}
    assert 2010 not in seasons or seasons[2010].rain_mm is None  # sem outubro de 2009


def test_season_to_date_compares_with_same_span_of_past_seasons():
    daily = synthetic_rain(1, date(2000, 1, 1), date(2024, 12, 10))
    # zera a chuva desta safra a partir de novembro: déficit e veranico
    daily = [(d, 0.0 if d >= date(2024, 11, 1) else mm) for d, mm in daily]
    std = season_to_date(SOJA, daily, date(2024, 12, 15))
    assert std is not None
    assert std.season_year == 2025
    assert std.start == date(2024, 10, 1)
    assert std.until == date(2024, 12, 10)
    assert std.deviation_pct < -40
    assert std.dry_spell_days >= 40
    assert len(std.past) >= 20
