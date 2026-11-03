"""Modelo de previsão da safra: treinado de verdade com os dados do banco.

rendimento (kg/ha) = intercepto + b·ano + c₁·variável de chuva₁ + c₂·variável de chuva₂

O ano representa a tendência (a tecnologia sobe o rendimento). As variáveis de chuva vêm de `features.py`. O treino
testa a tendência sozinha e as combinações de até 2 variáveis de chuva, mede cada uma pela validação "deixa uma safra
de fora" (cada safra é prevista por um modelo treinado sem ela) e fica com a de menor erro. Se a chuva não reduzir o
erro em pelo menos `MIN_GAIN`, o modelo fica só com a tendência: melhor dizer isso do que fingir que a chuva prevê.
"""

import math
from dataclasses import dataclass
from itertools import combinations

MIN_GAIN = 0.05  # a chuva precisa reduzir o erro em 5% para entrar no modelo
MAX_RAIN_FEATURES = 2
RIDGE = 1e-3  # regularização mínima, só para a conta não quebrar com variáveis quase iguais


def solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Sistema linear por eliminação de Gauss com pivoteamento parcial."""
    n = len(vector)
    a = [row[:] + [vector[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-12:
            raise ValueError("sistema sem solução única")
        a[col], a[pivot] = a[pivot], a[col]
        for r in range(n):
            if r != col:
                factor = a[r][col] / a[col][col]
                for c in range(col, n + 1):
                    a[r][c] -= factor * a[col][c]
    return [a[i][n] / a[i][i] for i in range(n)]


@dataclass(frozen=True)
class LinearModel:
    """Coeficientes em unidades originais: `intercept + sum(coef * x)`."""

    intercept: float
    coefficients: tuple[float, ...]

    def predict(self, x: list[float]) -> float:
        return self.intercept + sum(c * v for c, v in zip(self.coefficients, x, strict=True))


def fit(rows: list[list[float]], target: list[float]) -> LinearModel:
    """Mínimos quadrados com as variáveis padronizadas (média 0, desvio 1) e volta às unidades originais."""
    k = len(rows[0])
    n = len(rows)
    means = [sum(r[j] for r in rows) / n for j in range(k)]
    stds = [math.sqrt(sum((r[j] - means[j]) ** 2 for r in rows) / n) or 1.0 for j in range(k)]
    z = [[(r[j] - means[j]) / stds[j] for j in range(k)] for r in rows]
    y_mean = sum(target) / n
    yc = [t - y_mean for t in target]
    xtx = [[sum(z[i][a] * z[i][b] for i in range(n)) + (RIDGE if a == b else 0) for b in range(k)] for a in range(k)]
    xty = [sum(z[i][a] * yc[i] for i in range(n)) for a in range(k)]
    beta = solve(xtx, xty)
    coefficients = tuple(beta[j] / stds[j] for j in range(k))
    intercept = y_mean - sum(coefficients[j] * means[j] for j in range(k))
    return LinearModel(intercept, coefficients)


@dataclass(frozen=True)
class Backtest:
    year: int
    actual: float
    predicted: float


def leave_one_out(rows: list[list[float]], target: list[float], years: list[int]) -> list[Backtest]:
    """Cada safra prevista por um modelo treinado com todas as outras."""
    result = []
    for i in range(len(rows)):
        model = fit(rows[:i] + rows[i + 1 :], target[:i] + target[i + 1 :])
        result.append(Backtest(years[i], target[i], model.predict(rows[i])))
    return result


def mae(backtest: list[Backtest]) -> float:
    return sum(abs(b.actual - b.predicted) for b in backtest) / len(backtest)


def mae_pct(backtest: list[Backtest]) -> float:
    return sum(abs(b.actual - b.predicted) / b.actual for b in backtest) / len(backtest) * 100


@dataclass(frozen=True)
class TrainingResult:
    features: tuple[str, ...]  # variáveis de chuva escolhidas (o ano sempre entra)
    model: LinearModel
    backtest: list[Backtest]
    baseline_backtest: list[Backtest]  # só a tendência
    candidates: int
    years: list[int]
    feature_means: tuple[float, ...]  # média de cada variável de chuva nas safras usadas

    def trend(self, year: int) -> float:
        """Rendimento esperado no ano com a chuva na média: a tendência deste modelo."""
        return self.model.predict([float(year), *self.feature_means])

    @property
    def error(self) -> float:
        return mae(self.backtest)

    @property
    def baseline_error(self) -> float:
        return mae(self.baseline_backtest)

    @property
    def error_pct(self) -> float:
        return mae_pct(self.backtest)

    @property
    def baseline_error_pct(self) -> float:
        return mae_pct(self.baseline_backtest)

    @property
    def gain_pct(self) -> float:
        return (1 - self.error / self.baseline_error) * 100 if self.baseline_error else 0.0


def train(samples: list[dict[str, float | None]], candidates: list[str], min_samples: int) -> TrainingResult | None:
    """Escolhe as variáveis e treina. Cada amostra tem `ano`, `rendimento` e os valores das variáveis candidatas.

    Só entram as safras com todas as variáveis da combinação testada; a comparação com a tendência usa as mesmas
    safras, para ser justa.
    """
    complete = [s for s in samples if s.get("rendimento") is not None and s.get("ano") is not None]
    if len(complete) < min_samples:
        return None
    sets: list[tuple[str, ...]] = [()]
    for size in range(1, MAX_RAIN_FEATURES + 1):
        sets += list(combinations(candidates, size))

    def evaluate(names: tuple[str, ...]):
        rows_samples = [s for s in complete if all(s.get(n) is not None for n in names)]
        if len(rows_samples) < min_samples:
            return None
        years = [int(s["ano"]) for s in rows_samples]  # type: ignore[arg-type]
        target = [float(s["rendimento"]) for s in rows_samples]  # type: ignore[arg-type]
        rows = [[float(s["ano"])] + [float(s[n]) for n in names] for s in rows_samples]  # type: ignore[arg-type]
        try:
            backtest = leave_one_out(rows, target, years)
            baseline = leave_one_out([[r[0]] for r in rows], target, years)
            model = fit(rows, target)
        except ValueError:
            return None
        means = tuple(sum(r[j] for r in rows) / len(rows) for j in range(1, len(names) + 1))
        return names, model, backtest, baseline, years, means

    results = [r for r in (evaluate(names) for names in sets) if r is not None]
    if not results:
        return None
    trend_only = next(r for r in results if r[0] == ())
    best = min(results, key=lambda r: mae(r[2]))
    if best[0] and mae(best[2]) > mae(best[3]) * (1 - MIN_GAIN):
        best = trend_only
    names, model, backtest, baseline, years, means = best
    return TrainingResult(names, model, backtest, baseline, len(sets), years, means)
