"""Variáveis de chuva de uma safra, usadas nas descobertas e no treino da previsão."""

from collections.abc import Callable
from dataclasses import dataclass

from app.core.domain import MONTH_ABBR, MONTH_NAMES, Crop
from app.services.seasons import Season


@dataclass
class Feature:
    key: str
    label: str
    unit: str
    step: float
    value: Callable[[Season], float | None]


def features(crop: Crop) -> list[Feature]:
    items = [
        Feature("chuva_safra", "Chuva da safra", "mm", 100, lambda s: s.rain_mm),
        Feature("veranico", "Maior veranico da safra", "dias", 5, lambda s: s.dry_spell_days),
    ]
    for _, month in crop.window:
        label = f"Chuva de {MONTH_NAMES[month - 1]}"

        def value(s: Season, m: int = month) -> float | None:
            return s.month_rain.get(m) if s.month_rain else None

        items.append(Feature(f"chuva_{MONTH_ABBR[month - 1]}", label, "mm", 50, value))
    return items
