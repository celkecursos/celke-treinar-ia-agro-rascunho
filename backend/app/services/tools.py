"""Ferramentas que o modelo pode chamar no chat. Lista fechada: o modelo escolhe a ferramenta e os argumentos, o
código valida, consulta o banco e faz as contas. Nada de SQL escrito pelo modelo."""

import json
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from app.core import format as fmt
from app.core.domain import BRAZIL_CODE, CROPS, MONTH_NAMES, STATES_BY_ACRONYM, normalize
from app.core.errors import AppError
from app.repositories.crop_repository import CropRepository
from app.repositories.insight_repository import InsightRepository
from app.repositories.municipality_repository import MunicipalityRepository
from app.repositories.weather_repository import WeatherRepository
from app.schemas.municipalities import Municipality
from app.services.analysis_service import AnalysisService, place
from app.services.forecast_service import ForecastService
from app.services.seasons import Season, climatology, monthly_totals
from app.services.statistics import linear_fit, mean, pearson, percent_change

RAIN_SOURCE = "Open-Meteo (reanálise ERA5)"
PAM_SOURCE = "IBGE · Produção Agrícola Municipal"
LSPA_SOURCE = "IBGE · Levantamento Sistemático da Produção Agrícola"
MAX_DAILY_DAYS = 62

CropKey = Literal["soja", "milho"]


class ToolInputError(AppError):
    """Argumento inválido ou dado ausente: volta ao modelo como resultado, para ele corrigir ou explicar."""


@dataclass
class ToolResult:
    ok: bool
    content: dict[str, Any]
    summary: str
    source: str | None = None
    chart: dict | None = None

    def for_model(self) -> str:
        return json.dumps(self.content, ensure_ascii=False, default=str)


class Place(BaseModel):
    municipio: str = Field(min_length=2, max_length=80)
    uf: str | None = Field(default=None, max_length=2)


class RainArgs(Place):
    inicio: date
    fim: date
    agrupamento: Literal["total", "mes", "ano", "dia"] = "total"


class SeasonRainArgs(Place):
    cultura: CropKey
    ano_inicio: int | None = None
    ano_fim: int | None = None


class ProductionArgs(BaseModel):
    cultura: CropKey
    nivel: Literal["municipio", "uf", "brasil"]
    municipio: str | None = None
    uf: str | None = Field(default=None, max_length=2)
    ano_inicio: int | None = None
    ano_fim: int | None = None


class CorrelationArgs(Place):
    cultura: CropKey
    variavel: Literal["chuva_safra", "veranico", "chuva_plantio", "chuva_do_mes"] = "chuva_safra"
    mes: int | None = Field(default=None, ge=1, le=12)


class EstimateArgs(BaseModel):
    cultura: CropKey
    uf: str | None = Field(default=None, max_length=2)


class OptionalPlace(BaseModel):
    municipio: str | None = None
    uf: str | None = Field(default=None, max_length=2)


class NoArgs(BaseModel):
    pass


class ForecastArgs(Place):
    cultura: CropKey


class ChartArgs(Place):
    tipo: Literal[
        "chuva_x_rendimento", "dispersao", "desvio_rendimento", "rendimento_comparado", "chuva_mensal", "mapa_de_calor"
    ]
    cultura: CropKey = "soja"


def _schema(description: str, properties: dict, required: list[str]) -> dict:
    return {
        "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required},
    }


MUNICIPIO = {"type": "string", "description": "Nome do município cadastrado, ex.: Rio Verde"}
UF = {"type": "string", "description": "Sigla da UF, ex.: GO. Use quando houver municípios com o mesmo nome."}
CULTURA = {"type": "string", "enum": list(CROPS)}
ANO = {"type": "integer"}

TOOL_SPECS: dict[str, dict] = {
    "listar_municipios": _schema("Municípios cadastrados e o período dos dados de cada um.", {}, []),
    "consultar_chuva": _schema(
        "Chuva de um município entre duas datas: total, por mês, por ano ou por dia (até 62 dias).",
        {
            "municipio": MUNICIPIO,
            "uf": UF,
            "inicio": {"type": "string", "description": "AAAA-MM-DD"},
            "fim": {"type": "string", "description": "AAAA-MM-DD"},
            "agrupamento": {"type": "string", "enum": ["total", "mes", "ano", "dia"]},
        },
        ["municipio", "inicio", "fim"],
    ),
    "chuva_da_safra": _schema(
        "Chuva da janela de cada safra (soja: out a mar; milho: jan a abr) no município e na média da UF, com o "
        "desvio em relação à média e o maior veranico.",
        {"municipio": MUNICIPIO, "uf": UF, "cultura": CULTURA, "ano_inicio": ANO, "ano_fim": ANO},
        ["municipio", "cultura"],
    ),
    "consultar_producao": _schema(
        "Produção (t), rendimento (kg/ha) e área plantada (ha) por ano, no município, na UF ou no Brasil (PAM/IBGE).",
        {
            "cultura": CULTURA,
            "nivel": {"type": "string", "enum": ["municipio", "uf", "brasil"]},
            "municipio": MUNICIPIO,
            "uf": UF,
            "ano_inicio": ANO,
            "ano_fim": ANO,
        },
        ["cultura", "nivel"],
    ),
    "correlacao_chuva_rendimento": _schema(
        "Correlação entre uma variável de chuva da safra e o desvio do rendimento em relação à tendência, com r, "
        "p-valor e as safras mais abaixo da tendência. Para um mês específico, use variavel chuva_do_mes e mes "
        "(1 a 12, dentro da janela: soja de outubro a março; milho de janeiro a abril).",
        {
            "municipio": MUNICIPIO,
            "uf": UF,
            "cultura": CULTURA,
            "variavel": {"type": "string", "enum": ["chuva_safra", "veranico", "chuva_plantio", "chuva_do_mes"]},
            "mes": {"type": "integer", "description": "Mês de 1 a 12, só com chuva_do_mes"},
        },
        ["municipio", "cultura"],
    ),
    "estimativa_safra": _schema(
        "Estimativa mais recente da safra do ano em andamento (LSPA/IBGE), no Brasil ou numa UF com município "
        "cadastrado, comparada ao rendimento esperado pela tendência.",
        {"cultura": CULTURA, "uf": UF},
        ["cultura"],
    ),
    "ver_descobertas": _schema(
        "Descobertas do relatório mais recente: relações entre chuva e rendimento que passaram no filtro estatístico.",
        {"municipio": MUNICIPIO, "uf": UF},
        [],
    ),
    "ver_alertas": _schema("Alertas ativos da safra em andamento (chuva abaixo da média, veranico).", {}, []),
    "previsao_safra": _schema(
        "Previsão do rendimento da próxima safra feita pelo modelo treinado com os dados do município: variáveis "
        "usadas, erro medido na validação, previsão com faixa, cenários e comparação com a estimativa do IBGE.",
        {"municipio": MUNICIPIO, "uf": UF, "cultura": CULTURA},
        ["municipio", "cultura"],
    ),
    "mostrar_grafico": _schema(
        "Mostra um gráfico na resposta. Use quando ajudar a pessoa a ver o dado.",
        {
            "tipo": {
                "type": "string",
                "enum": [
                    "chuva_x_rendimento",
                    "dispersao",
                    "desvio_rendimento",
                    "rendimento_comparado",
                    "chuva_mensal",
                    "mapa_de_calor",
                ],
            },
            "municipio": MUNICIPIO,
            "uf": UF,
            "cultura": CULTURA,
        },
        ["tipo", "municipio"],
    ),
}

TOOLS = [{"type": "function", "function": {"name": name, **spec}} for name, spec in TOOL_SPECS.items()]


def correlation_words(r: float, p: float) -> str:
    strength = next(
        label
        for limit, label in [
            (0.2, "muito fraca"),
            (0.4, "fraca"),
            (0.6, "moderada"),
            (0.8, "forte"),
            (1.01, "muito forte"),
        ]
        if abs(r) < limit
    )
    direction = "positiva" if r > 0 else "negativa"
    significance = "estatisticamente significativa (p < 0,05)" if p < 0.05 else "não significativa (p ≥ 0,05)"
    return f"correlação {strength} e {direction}, {significance}"


class ToolExecutor:
    def __init__(
        self,
        municipalities: MunicipalityRepository,
        weather: WeatherRepository,
        crops: CropRepository,
        insights: InsightRepository,
        analyses: AnalysisService,
        forecasts: ForecastService | None = None,
    ):
        self._municipalities = municipalities
        self._weather = weather
        self._crops = crops
        self._insights = insights
        self._analyses = analyses
        self._forecasts = forecasts
        self._handlers: dict[str, tuple[type[BaseModel], Callable[[Any], ToolResult]]] = {
            "listar_municipios": (NoArgs, self._list),
            "consultar_chuva": (RainArgs, self._rain),
            "chuva_da_safra": (SeasonRainArgs, self._season_rain),
            "consultar_producao": (ProductionArgs, self._production),
            "correlacao_chuva_rendimento": (CorrelationArgs, self._correlation),
            "estimativa_safra": (EstimateArgs, self._estimate),
            "ver_descobertas": (OptionalPlace, self._discoveries),
            "ver_alertas": (NoArgs, self._alerts),
            "previsao_safra": (ForecastArgs, self._forecast),
            "mostrar_grafico": (ChartArgs, self._chart),
        }

    def run(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        handler = self._handlers.get(name)
        if handler is None:
            return ToolResult(False, {"erro": f"Ferramenta {name} não existe."}, f"Ferramenta desconhecida: {name}")
        model, fn = handler
        # alguns modelos mandam `null` ou "" nos campos opcionais
        clean = {k: v for k, v in (arguments or {}).items() if v not in (None, "")}
        try:
            return fn(model(**clean))
        except ValidationError as exc:
            first = exc.errors()[0]
            message = f"Argumento inválido em {'.'.join(str(p) for p in first['loc'])}: {first['msg']}"
            return ToolResult(False, {"erro": message}, message)
        except AppError as exc:
            return ToolResult(False, {"erro": exc.message}, exc.message)

    # Municípios

    def _find(self, name: str, uf: str | None) -> Municipality:
        wanted = normalize(name)
        options = self._municipalities.all(principal_only=False)
        found = [m for m in options if normalize(m.name) == wanted and (not uf or m.state == uf.upper())]
        registered = ", ".join(place(m) for m in options if m.principal) or "nenhum"
        if not found:
            raise ToolInputError(
                f"O município {name} não está cadastrado. Cadastrados: {registered}. "
                "Para incluir outro, cadastre-o na página Municípios."
            )
        if len(found) > 1:
            raise ToolInputError(f"Há mais de um {name}: {', '.join(place(m) for m in found)}. Informe a UF.")
        return found[0]

    def _list(self, _: NoArgs) -> ToolResult:
        items = [
            {
                "municipio": m.name,
                "uf": m.state,
                "chuva_desde": m.rain_first_day,
                "chuva_ate": m.rain_last_day,
                "producao_ate": m.production_last_year,
                "situacao": m.status,
            }
            for m in self._municipalities.all()
        ]
        return ToolResult(True, {"municipios": items}, f"{len(items)} municípios cadastrados")

    # Chuva

    def _rain(self, args: RainArgs) -> ToolResult:
        if args.fim < args.inicio:
            raise ToolInputError("A data final é anterior à inicial.")
        if args.agrupamento == "dia" and (args.fim - args.inicio).days >= MAX_DAILY_DAYS:
            raise ToolInputError(f"Por dia, o período máximo é de {MAX_DAILY_DAYS} dias. Use agrupamento mes ou ano.")
        m = self._find(args.municipio, args.uf)
        daily = self._weather.daily(m.code, args.inicio, args.fim)
        expected = (args.fim - args.inicio).days + 1
        content: dict[str, Any] = {
            "municipio": place(m),
            "periodo": f"{args.inicio.isoformat()} a {args.fim.isoformat()}",
            "dias_com_dado": len(daily),
            "dias_no_periodo": expected,
            "total_mm": round(sum(mm for _, mm in daily), 1),
            "fonte": RAIN_SOURCE,
        }
        if args.agrupamento in ("mes", "ano"):
            groups: dict[str, float] = defaultdict(float)
            for day, mm in daily:
                groups[day.strftime("%Y-%m") if args.agrupamento == "mes" else str(day.year)] += mm
            content["por_" + args.agrupamento] = {k: round(v, 1) for k, v in sorted(groups.items())}
            if args.agrupamento == "mes":
                normals = climatology(monthly_totals(self._weather.daily(m.code)))
                content["media_historica_do_mes_mm"] = {f"{k:02d}": v for k, v in sorted(normals.items())}
        elif args.agrupamento == "dia":
            content["por_dia"] = {d.isoformat(): mm for d, mm in daily}
        if len(daily) < expected:
            content["aviso"] = "Faltam dias no período: o total considera só os dias com dado."
        summary = f"Chuva em {place(m)}: {fmt.number(content['total_mm'], 1)} mm ({content['periodo']})"
        return ToolResult(True, content, summary, RAIN_SOURCE)

    def _season_rain(self, args: SeasonRainArgs) -> ToolResult:
        m = self._find(args.municipio, args.uf)
        data = self._analyses.season_data(m.code, args.cultura)
        rows = [
            {
                "safra": s.year,
                "chuva_mm": s.rain_mm,
                "desvio_da_media_historica_do_municipio_pct": s.rain_anomaly_pct,
                "chuva_media_da_uf_na_mesma_safra_mm": s.rain_state_mm,
                "diferenca_para_a_uf_pct": round(percent_change(s.rain_mm, s.rain_state_mm) or 0, 1)
                if s.rain_state_mm
                else None,
                "maior_veranico_dias": s.dry_spell_days,
            }
            for s in data.seasons
            if s.rain_mm is not None
            and (args.ano_inicio is None or s.year >= args.ano_inicio)
            and (args.ano_fim is None or s.year <= args.ano_fim)
        ]
        if not rows:
            raise ToolInputError("Não há safras com chuva completa nesse período.")
        average = mean([s.rain_mm for s in data.seasons if s.rain_mm is not None])  # type: ignore[misc]
        content = {
            "municipio": place(m),
            "cultura": data.crop.name,
            "janela": "outubro a março" if data.crop.key == "soja" else "janeiro a abril",
            "media_historica_das_safras_no_municipio_mm": round(average or 0, 1),
            "safras": rows,
            "fonte": RAIN_SOURCE,
        }
        return ToolResult(
            True, content, f"Chuva de {len(rows)} safras de {data.crop.name.lower()} em {place(m)}", RAIN_SOURCE
        )

    # Produção

    def _production(self, args: ProductionArgs) -> ToolResult:
        if args.nivel == "municipio":
            if not args.municipio:
                raise ToolInputError("Informe o município.")
            m = self._find(args.municipio, args.uf)
            data = self._analyses.season_data(m.code, args.cultura)
            territory = place(m)
            history = self._crops.yearly("municipio", m.code, args.cultura)
            anomaly = {s.year: (s.trend_kg_ha, s.yield_anomaly_pct) for s in data.seasons}
        elif args.nivel == "uf":
            state = STATES_BY_ACRONYM.get((args.uf or "").upper())
            if state is None:
                raise ToolInputError("Informe a sigla da UF.")
            territory = state.name
            history = self._crops.yearly("uf", state.code, args.cultura)
            anomaly = {}
        else:
            territory = "Brasil"
            history = self._crops.yearly("brasil", BRAZIL_CODE, args.cultura)
            anomaly = {}
        if not anomaly:
            points = [(c.year, c.yield_kg_ha) for c in history if c.yield_kg_ha]
            fit = linear_fit([y for y, _ in points], [v for _, v in points])  # type: ignore[misc]
            if fit:
                anomaly = {y: (round(fit.at(y), 1), round(percent_change(v, fit.at(y)) or 0, 1)) for y, v in points}
        rows = [
            {
                "ano": c.year,
                "producao_t": c.production_t,
                "rendimento_kg_ha": c.yield_kg_ha,
                "area_plantada_ha": c.planted_area_ha,
                "tendencia_kg_ha": anomaly.get(c.year, (None, None))[0],
                "desvio_da_tendencia_pct": anomaly.get(c.year, (None, None))[1],
            }
            for c in history
            if (args.ano_inicio is None or c.year >= args.ano_inicio)
            and (args.ano_fim is None or c.year <= args.ano_fim)
        ]
        if not rows:
            raise ToolInputError(f"Não há produção de {args.cultura} guardada para {territory} nesse período.")
        content = {"territorio": territory, "cultura": CROPS[args.cultura].name, "anos": rows, "fonte": PAM_SOURCE}
        return ToolResult(True, content, f"Produção de {args.cultura} em {territory}: {len(rows)} anos", PAM_SOURCE)

    def _correlation(self, args: CorrelationArgs) -> ToolResult:
        m = self._find(args.municipio, args.uf)
        data = self._analyses.season_data(m.code, args.cultura)
        if args.variavel == "chuva_do_mes":
            window = [month for _, month in data.crop.window]
            if args.mes not in window:
                names = ", ".join(MONTH_NAMES[x - 1] for x in window)
                raise ToolInputError(f"Informe mes dentro da janela {data.crop.of}: {names}.")
            month = args.mes

            def value(s: Season) -> float | None:
                return s.month_rain.get(month) if s.month_rain else None

            label = f"chuva de {MONTH_NAMES[month - 1]}"
        else:
            field = {"chuva_safra": "rain_mm", "veranico": "dry_spell_days", "chuva_plantio": "planting_rain_mm"}[
                args.variavel
            ]

            def value(s: Season) -> float | None:
                return getattr(s, field)

            label = args.variavel.replace("_", " ")
        pairs = [(value(s), s.yield_anomaly_pct) for s in data.seasons]
        pairs = [(x, y) for x, y in pairs if x is not None and y is not None]
        corr = pearson([x for x, _ in pairs], [y for _, y in pairs])
        if corr is None:
            raise ToolInputError("Safras insuficientes (com chuva e produção) para calcular a correlação.")
        worst = sorted([s for s in data.seasons if s.yield_anomaly_pct is not None], key=lambda s: s.yield_anomaly_pct)[
            :3
        ]
        content = {
            "municipio": place(m),
            "cultura": data.crop.name,
            "variavel": label,
            "r": round(corr.r, 3),
            "p_valor": round(corr.p, 4),
            "safras": corr.n,
            "leitura": correlation_words(corr.r, corr.p),
            "safras_mais_abaixo_da_tendencia": [
                {"safra": s.year, "desvio_pct": s.yield_anomaly_pct, "valor_da_variavel": value(s)} for s in worst
            ],
            "cuidado": "Correlação não é causa; o rendimento também depende de manejo, pragas, preço e tecnologia.",
            "fonte": f"{RAIN_SOURCE} e {PAM_SOURCE}",
        }
        summary = f"Correlação {label} × rendimento em {place(m)}: r = {fmt.number(corr.r, 2)}"
        return ToolResult(True, content, summary, f"{RAIN_SOURCE} e {PAM_SOURCE}")

    def _estimate(self, args: EstimateArgs) -> ToolResult:
        products = {"soja": {"soja"}, "milho": {"milho_1", "milho_2"}}[args.cultura]
        state = STATES_BY_ACRONYM.get(args.uf.upper()) if args.uf else None
        if args.uf and state is None:
            raise ToolInputError(f"UF {args.uf} não existe.")
        items = [
            e
            for e in self._analyses.estimates()
            if e.product in products
            and (e.territory_code == state.code and e.level == "uf" if state else e.level == "brasil")
        ]
        if not items:
            raise ToolInputError(
                "Não há estimativa guardada para esse território. A estimativa só existe por UF com município "
                "cadastrado e para o Brasil; colete a estimativa na página Status."
            )
        content = {"estimativas": [e.model_dump() for e in items], "fonte": LSPA_SOURCE}
        return ToolResult(
            True, content, f"Estimativa da safra de {args.cultura}: {items[0].territory_name}", LSPA_SOURCE
        )

    # Descobertas, alertas e gráficos

    def _discoveries(self, args: OptionalPlace) -> ToolResult:
        report = self._insights.report()
        if report is None or not report.discoveries:
            raise ToolInputError("Ainda não há descobertas. Elas são geradas depois das coletas.")
        code = self._find(args.municipio, args.uf).code if args.municipio else None
        items = [
            {"municipio": d.municipality_name, "cultura": d.crop, "fato": d.fact, "estatistica": d.stats}
            for d in report.discoveries
            if code is None or d.municipality_code == code
        ]
        content = {"gerado_em": report.created_at, "testes_feitos": report.tests, "descobertas": items}
        return ToolResult(True, content, f"{len(items)} descobertas do relatório mais recente")

    def _alerts(self, _: NoArgs) -> ToolResult:
        items = [
            {
                "municipio": a.municipality_name,
                "cultura": a.crop,
                "titulo": a.title,
                "mensagem": a.message,
                "fatos": a.facts,
            }
            for a in self._insights.alerts()
        ]
        return ToolResult(True, {"alertas": items}, f"{len(items)} alertas ativos")

    def _forecast(self, args: ForecastArgs) -> ToolResult:
        m = self._find(args.municipio, args.uf)
        record = self._forecasts.view(m.code, args.cultura).latest if self._forecasts else None
        if record is None:
            raise ToolInputError(
                "Ainda não há modelo treinado para esse município e cultura. O treino roda depois das coletas e pelo "
                "botão Treinar de novo, na página Previsão."
            )
        r = record.result
        content = {
            "municipio": r.municipality_name,
            "cultura": r.crop_name,
            "treinado_em": record.trained_at,
            "safras_usadas": f"{r.seasons_used} ({r.first_year} a {r.last_year})",
            "equacao": r.equation,
            "variaveis_de_chuva": [f.label for f in r.features] or "nenhuma (a chuva não melhorou a previsão)",
            "erro_medio_do_modelo_pct": r.error_pct,
            "erro_medio_so_tendencia_pct": r.baseline_error_pct,
            "melhora_sobre_a_tendencia_pct": r.gain_pct,
            "previsoes": [f.model_dump(mode="json") for f in r.forecasts],
            "como_foi_medido": "Cada safra foi prevista por um modelo treinado sem ela (validação deixa uma de fora).",
            "fonte": f"{RAIN_SOURCE} e {PAM_SOURCE}; modelo treinado pelo sistema",
        }
        summary = (
            f"Previsão {CROPS[args.cultura].of} em {r.municipality_name} (erro médio {fmt.number(r.error_pct, 1)}%)"
        )
        return ToolResult(True, content, summary, "Modelo de previsão treinado")

    def _chart(self, args: ChartArgs) -> ToolResult:
        m = self._find(args.municipio, args.uf)
        analysis = self._analyses.analysis(m.code, args.cultura)
        index = {
            "chuva_x_rendimento": 0,
            "dispersao": 1,
            "desvio_rendimento": 2,
            "rendimento_comparado": 3,
            "chuva_mensal": 4,
            "mapa_de_calor": 5,
        }[args.tipo]
        chart = analysis.charts[index]
        return ToolResult(
            True,
            {"grafico": chart["titulo"], "aviso": "O gráfico já aparece para a pessoa; não descreva cada valor."},
            f"Gráfico: {chart['titulo']}",
            chart=chart,
        )
