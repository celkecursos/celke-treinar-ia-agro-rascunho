"""Estatística usada nas análises. Todas as contas ficam aqui, no código; o modelo de IA só interpreta os resultados."""

import math
from dataclasses import dataclass


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


@dataclass(frozen=True)
class LinearFit:
    slope: float
    intercept: float

    def at(self, x: float) -> float:
        return self.intercept + self.slope * x


def linear_fit(xs: list[float], ys: list[float]) -> LinearFit | None:
    """Mínimos quadrados. `None` com menos de 3 pontos ou sem variação em x."""
    n = len(xs)
    if n < 3 or n != len(ys):
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / sxx
    return LinearFit(slope, my - slope * mx)


def _betacf(a: float, b: float, x: float) -> float:
    """Fração contínua da beta incompleta (Numerical Recipes, betacf)."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > tiny else tiny)
        c = 1 + aa / c if abs(1 + aa / c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > tiny else tiny)
        c = 1 + aa / c if abs(1 + aa / c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-12:
            break
    return h


def _betai(a: float, b: float, x: float) -> float:
    """Beta incompleta regularizada I_x(a, b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return front * _betacf(a, b, x) / a
    return 1 - front * _betacf(b, a, 1 - x) / b


def t_test_p_value(t: float, df: int) -> float:
    """p-valor bilateral da distribuição t de Student."""
    return _betai(df / 2, 0.5, df / (df + t * t))


@dataclass(frozen=True)
class CorrelationResult:
    r: float
    p: float
    n: int


def pearson(xs: list[float], ys: list[float]) -> CorrelationResult | None:
    """Correlação de Pearson com o p-valor do teste t. `None` com menos de 4 pares ou sem variação."""
    n = len(xs)
    if n < 4 or n != len(ys):
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    r = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / math.sqrt(sxx * syy)
    r = max(-1.0, min(1.0, r))
    if abs(r) == 1:
        return CorrelationResult(r, 0.0, n)
    t = r * math.sqrt((n - 2) / (1 - r * r))
    return CorrelationResult(r, t_test_p_value(t, n - 2), n)


def benjamini_hochberg(p_values: list[float]) -> list[float]:
    """q-valores (p corrigido para muitos testes): controla a fração de "descobertas" que são acaso."""
    m = len(p_values)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: p_values[i])
    q = [0.0] * m
    running = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        running = min(running, p_values[i] * m / rank)
        q[i] = running
    return q


def percent_change(value: float, reference: float) -> float | None:
    return (value - reference) / reference * 100 if reference else None
