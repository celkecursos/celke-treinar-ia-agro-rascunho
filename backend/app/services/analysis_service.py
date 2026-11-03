from dataclasses import dataclass

from app.core import format as fmt
from app.core.domain import BRAZIL_CODE, CROPS, LSPA_PRODUCT_NAMES, MONTH_ABBR, STATES_BY_CODE, Crop
from app.core.errors import NotFoundError
from app.repositories.crop_repository import CropRepository
from app.repositories.municipality_repository import MunicipalityRepository
from app.repositories.weather_repository import DailyRain, WeatherRepository
from app.schemas.analyses import Analysis, Correlation, Estimate, IndicatorItem, SeasonRow
from app.schemas.municipalities import Municipality
from app.services import charts
from app.services.seasons import (
    Month,
    MonthlyRain,
    Season,
    build_seasons,
    climatology,
    monthly_totals,
    state_season_rain,
)
from app.services.statistics import CorrelationResult, linear_fit, mean, pearson

NOTES = [
    "Chuva: reanálise ERA5 do Open-Meteo para as coordenadas do município (quadrados de cerca de 25 km); não é "
    "pluviômetro. Os últimos dias vêm da previsão e são trocados pelo arquivo quando ele chega.",
    "Produção e rendimento: Produção Agrícola Municipal (PAM) do IBGE, anual. O milho soma a 1ª e a 2ª safra.",
    "Janela da safra: soja de outubro (ano anterior) a março; milho de janeiro a abril (2ª safra). É uma escolha "
    "de método.",
    "Desvio da tendência: o rendimento sobe com a tecnologia; por isso a comparação com a chuva usa a diferença "
    "entre o rendimento do ano e a reta de tendência, não o rendimento bruto.",
    "Chuva da UF: média dos municípios que mais plantam soja na UF, ponderada pela área plantada.",
    "Correlação não é causa. Com poucas safras, o resultado é instável.",
]


def crop_or_error(key: str) -> Crop:
    crop = CROPS.get(key)
    if crop is None:
        raise NotFoundError(f'Cultura "{key}" não existe. Use: {", ".join(CROPS)}.')
    return crop


def window_label(crop: Crop) -> str:
    first, last = crop.window[0][1], crop.window[-1][1]
    return f"{MONTH_ABBR[first - 1]} a {MONTH_ABBR[last - 1]}"


def place(m: Municipality) -> str:
    return f"{m.name} ({m.state})"


@dataclass
class SeasonData:
    municipality: Municipality
    crop: Crop
    seasons: list[Season]
    daily: DailyRain
    monthly: dict[Month, MonthlyRain]


class AnalysisService:
    """Cruza chuva e produção de um município. Todas as contas ficam no código, nunca no modelo de IA."""

    def __init__(self, municipalities: MunicipalityRepository, weather: WeatherRepository, crops: CropRepository):
        self._municipalities = municipalities
        self._weather = weather
        self._crops = crops

    def municipality(self, code: int) -> Municipality:
        m = self._municipalities.get(code)
        if m is None:
            raise NotFoundError("Município não encontrado. Cadastre-o na página Municípios.")
        return m

    def season_data(self, code: int, crop_key: str) -> SeasonData:
        m = self.municipality(code)
        crop = crop_or_error(crop_key)
        daily = self._weather.daily(code)
        municipal = self._crops.yearly("municipio", code, crop.key)
        years = sorted({d.year for d, _ in daily} | {d.year + 1 for d, _ in daily} | {c.year for c in municipal})
        references = [
            (self._weather.daily(r.municipality_code), r.area_ha) for r in self._municipalities.references(m.state_code)
        ]
        seasons = build_seasons(
            crop,
            daily,
            municipal,
            state=self._crops.yearly("uf", m.state_code, crop.key),
            brazil=self._crops.yearly("brasil", BRAZIL_CODE, crop.key),
            state_rain=state_season_rain(crop, references, years) if references else None,
        )
        return SeasonData(m, crop, seasons, daily, monthly_totals(daily))

    @staticmethod
    def correlation(seasons: list[Season], field: str = "rain_mm") -> CorrelationResult | None:
        pairs = [(getattr(s, field), s.yield_anomaly_pct) for s in seasons]
        pairs = [(x, y) for x, y in pairs if x is not None and y is not None]
        return pearson([x for x, _ in pairs], [y for _, y in pairs])

    def analysis(self, code: int, crop_key: str) -> Analysis:
        data = self.season_data(code, crop_key)
        m, crop, seasons = data.municipality, data.crop, data.seasons
        corr = self.correlation(seasons)
        name = place(m)
        state = STATES_BY_CODE[m.state_code].name
        note = (
            f"r = {fmt.number(corr.r, 2)}, p = {fmt.number(corr.p, 3)}, {corr.n} safras. Correlação não é causa."
            if corr
            else "Safras insuficientes para a correlação."
        )
        chart_list = [
            charts.rain_vs_yield(seasons, crop, name),
            charts.scatter(charts.scatter_points(seasons, "rain_mm"), crop, name, "Chuva da safra", "mm", note),
            charts.yield_anomaly(seasons, crop, name),
            charts.yield_comparison(seasons, crop, name, state),
            charts.monthly_rain(data.monthly, climatology(data.monthly), name),
            charts.heatmap(data.monthly, name),
        ]
        refs = self._municipalities.references(m.state_code)
        if refs:
            names = {x.code: x.name for x in self._municipalities.all(principal_only=False)}
            chart_list.append(
                charts.state_references(
                    [(names.get(r.municipality_code, str(r.municipality_code)), r.area_ha) for r in refs],
                    state,
                    refs[0].year,
                )
            )
        return Analysis(
            municipality=m,
            crop=crop.key,
            crop_name=crop.name,
            window=window_label(crop),
            seasons=[SeasonRow(**{k: v for k, v in vars(s).items() if k != "month_rain"}) for s in seasons],
            correlation=Correlation(r=round(corr.r, 3), p=round(corr.p, 4), n=corr.n) if corr else None,
            indicators=self._indicators(seasons, corr),
            charts=chart_list,
            notes=NOTES,
        )

    @staticmethod
    def _indicators(seasons: list[Season], corr: CorrelationResult | None) -> list[IndicatorItem]:
        with_rain = [s for s in seasons if s.rain_mm is not None]
        with_yield = [s for s in seasons if s.yield_kg_ha]
        items: list[IndicatorItem] = []
        if with_rain:
            last = with_rain[-1]
            average = mean([s.rain_mm for s in with_rain])  # type: ignore[misc]
            items.append(
                IndicatorItem(
                    rotulo=f"Chuva da safra {last.year}",
                    valor=f"{fmt.number(last.rain_mm)} mm",
                    descricao=f"Média das safras: {fmt.number(average)} mm",
                    variacao=last.rain_anomaly_pct,
                    tendencia=[s.rain_mm for s in with_rain[-12:]],  # type: ignore[misc]
                )
            )
            items.append(
                IndicatorItem(
                    rotulo=f"Maior veranico da safra {last.year}",
                    valor=f"{last.dry_spell_days} dias" if last.dry_spell_days is not None else "–",
                    descricao="Dias seguidos com menos de 1 mm",
                )
            )
        if with_yield:
            last = with_yield[-1]
            items.append(
                IndicatorItem(
                    rotulo=f"Rendimento {last.year}",
                    valor=f"{fmt.number(last.yield_kg_ha)} kg/ha",
                    descricao="Variação em relação à tendência",
                    variacao=last.yield_anomaly_pct,
                    tendencia=[s.yield_kg_ha for s in with_yield[-12:]],  # type: ignore[misc]
                )
            )
        items.append(
            IndicatorItem(
                rotulo="Chuva × rendimento",
                valor=f"r = {fmt.number(corr.r, 2)}" if corr else "–",
                descricao=f"p = {fmt.number(corr.p, 3)} · {corr.n} safras" if corr else "Safras insuficientes",
            )
        )
        return items

    def estimates(self) -> list[Estimate]:
        """Último levantamento da safra (LSPA) de cada UF com município cadastrado e do Brasil."""
        result = []
        for e in self._crops.latest_estimates():
            territory = "Brasil" if e.level == "brasil" else STATES_BY_CODE[e.territory_code].name
            crop_key = "soja" if e.product == "soja" else None
            expected = None
            if crop_key:
                history = self._crops.yearly("brasil" if e.level == "brasil" else "uf", e.territory_code, crop_key)
                points = [(c.year, c.yield_kg_ha) for c in history if c.yield_kg_ha]
                fit = linear_fit([y for y, _ in points], [v for _, v in points])  # type: ignore[misc]
                expected = round(fit.at(e.period // 100), 0) if fit else None
            year, month = divmod(e.period, 100)
            result.append(
                Estimate(
                    product=e.product,
                    product_name=LSPA_PRODUCT_NAMES[e.product],
                    level=e.level,
                    territory_code=e.territory_code,
                    territory_name=territory,
                    period=e.period,
                    period_label=f"{MONTH_ABBR[month - 1]}/{year}",
                    production_t=e.production_t,
                    yield_kg_ha=e.yield_kg_ha,
                    planted_area_ha=e.planted_area_ha,
                    harvested_area_ha=e.harvested_area_ha,
                    expected_yield_kg_ha=expected,
                )
            )
        return sorted(result, key=lambda e: (e.level != "brasil", e.territory_name, e.product))
