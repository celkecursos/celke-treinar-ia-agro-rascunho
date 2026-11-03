"""Clientes das fontes públicas: Open-Meteo (chuva e coordenadas) e IBGE (municípios, PAM e LSPA).

Só estes endereços são acessados, e só saem do computador nomes de municípios, coordenadas, datas e códigos do IBGE.
"""

import logging
import re
import time
from collections import defaultdict
from datetime import date
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx

from app.core.domain import BRAZIL_CODE, CROP_BY_PAM_CODE, CROPS, LSPA_PRODUCTS, STATES_BY_ACRONYM, normalize
from app.core.errors import SourceUnavailableError
from app.repositories.crop_repository import CropEstimate, CropYear
from app.repositories.weather_repository import DailyRain

logger = logging.getLogger(__name__)

OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_GEOCODING = "https://geocoding-api.open-meteo.com/v1/search"
IBGE_LOCALIDADES = "https://servicodados.ibge.gov.br/api/v1/localidades"
IBGE_AGREGADOS = "https://servicodados.ibge.gov.br/api/v3/agregados"
SIDRA = "https://apisidra.ibge.gov.br/values"
ALLOWED_HOSTS = {urlsplit(u).hostname for u in (OPEN_METEO_ARCHIVE, OPEN_METEO_FORECAST, OPEN_METEO_GEOCODING, SIDRA)}
ALLOWED_HOSTS.add(urlsplit(IBGE_LOCALIDADES).hostname)

TIMEZONE = "America/Sao_Paulo"
PAM_TABLE = 5457
LSPA_TABLE = 6588
# Variáveis do IBGE → campo gravado
PAM_VARIABLES = {"8331": "planted_area_ha", "216": "harvested_area_ha", "214": "production_t", "112": "yield_kg_ha"}
LSPA_VARIABLES = {"109": "planted_area_ha", "216": "harvested_area_ha", "35": "production_t", "36": "yield_kg_ha"}
SIDRA_LEVELS = {"municipio": "n6", "uf": "n3", "brasil": "n1"}
USER_AGENT = "CelkeTreinarIAAgro/1.0 (+https://github.com/celkecursos)"


class PublicDataClient:
    """GET de JSON só nos endereços permitidos, com nova tentativa em falha de rede e mensagens em português."""

    def __init__(self, timeout: float, transport: httpx.BaseTransport | None = None, retries: int = 2):
        self._client = httpx.Client(
            timeout=timeout, transport=transport, trust_env=False, headers={"User-Agent": USER_AGENT}
        )
        self._retries = retries

    def get_json(self, url: str, params: dict[str, Any] | None = None, *, source: str) -> Any:
        if urlsplit(url).hostname not in ALLOWED_HOSTS or not url.startswith("https://"):
            raise SourceUnavailableError(f"Endereço não permitido: {url}")
        for attempt in range(self._retries + 1):
            try:
                response = self._client.get(url, params=params)
            except httpx.HTTPError as exc:
                logger.warning("%s: falha de rede (%s)", source, exc)
                if attempt == self._retries:
                    raise SourceUnavailableError(
                        f"Não foi possível acessar {source}. Verifique a conexão com a internet e tente de novo."
                    ) from exc
            else:
                if response.status_code < 500 and response.status_code != 429:
                    break
                logger.warning("%s: HTTP %s", source, response.status_code)
                if attempt == self._retries:
                    detail = "limite de pedidos atingido" if response.status_code == 429 else "serviço com erro"
                    raise SourceUnavailableError(f"{source} não respondeu ({detail}). Tente de novo mais tarde.")
            time.sleep(1.5 * (attempt + 1))
        if response.status_code >= 400:
            raise SourceUnavailableError(f"{source} recusou o pedido: {response.text[:200]}")
        try:
            return response.json()
        except ValueError as exc:
            raise SourceUnavailableError(f"{source} respondeu algo inesperado: {response.text[:200]}") from exc


class RainSource(Protocol):
    def archive(self, latitude: float, longitude: float, start: date, end: date) -> DailyRain: ...

    def recent(self, latitude: float, longitude: float, past_days: int) -> DailyRain: ...

    def geocode(self, name: str, state_acronym: str) -> tuple[float, float] | None: ...


class IbgeSource(Protocol):
    def municipality(self, code: int) -> tuple[str, str]: ...

    def municipalities_of_state(self, state_acronym: str) -> list[tuple[int, str]]: ...

    def pam_last_year(self) -> int: ...

    def pam(self, level: str, codes: list[int], start: int, end: int) -> list[CropYear]: ...

    def top_soy_municipalities(self, state_code: int, year: int, count: int) -> list[tuple[int, str, float]]: ...

    def lspa(self, level: str, codes: list[int], months: int) -> list[CropEstimate]: ...


def _daily(payload: dict) -> DailyRain:
    daily = payload.get("daily") or {}
    return [
        (date.fromisoformat(day), float(mm))
        for day, mm in zip(daily.get("time", []), daily.get("precipitation_sum", []), strict=False)
        if mm is not None
    ]


class OpenMeteo:
    """Chuva diária (reanálise ERA5 no arquivo; previsão para os últimos dias) e coordenadas por nome."""

    def __init__(self, client: PublicDataClient):
        self._client = client

    def archive(self, latitude: float, longitude: float, start: date, end: date) -> DailyRain:
        payload = self._client.get_json(
            OPEN_METEO_ARCHIVE,
            {
                "latitude": latitude,
                "longitude": longitude,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "daily": "precipitation_sum",
                "timezone": TIMEZONE,
            },
            source="o Open-Meteo (arquivo de chuva)",
        )
        return _daily(payload)

    def recent(self, latitude: float, longitude: float, past_days: int) -> DailyRain:
        payload = self._client.get_json(
            OPEN_METEO_FORECAST,
            {
                "latitude": latitude,
                "longitude": longitude,
                "daily": "precipitation_sum",
                "past_days": past_days,
                "forecast_days": 1,
                "timezone": TIMEZONE,
            },
            source="o Open-Meteo (chuva recente)",
        )
        # O dia de hoje ainda não terminou: fica de fora.
        today = date.fromisoformat(payload["daily"]["time"][-1]) if payload.get("daily", {}).get("time") else None
        return [(d, mm) for d, mm in _daily(payload) if d != today]

    def geocode(self, name: str, state_acronym: str) -> tuple[float, float] | None:
        state = STATES_BY_ACRONYM[state_acronym]
        payload = self._client.get_json(
            OPEN_METEO_GEOCODING,
            {"name": name, "count": 20, "language": "pt", "countryCode": "BR"},
            source="o Open-Meteo (coordenadas)",
        )
        wanted = normalize(state.name)
        candidates = [
            r
            for r in payload.get("results") or []
            if r.get("country_code") == "BR"
            and normalize(r.get("admin1", "")) == wanted
            and normalize(r.get("name", "")) == normalize(name)
        ]
        if not candidates:
            return None
        best = max(candidates, key=lambda r: r.get("population") or 0)
        return float(best["latitude"]), float(best["longitude"])


def _strip_state(name: str) -> str:
    """O SIDRA escreve "Rio Verde - GO" ou "Rio Verde (GO)"."""
    return re.sub(r"\s*(\([A-Z]{2}\)| - [A-Z]{2})$", "", name)


def _sidra_value(raw: str) -> float | None:
    """`-` é zero absoluto; `..`, `...` e `X` são dado não aplicável, não disponível ou sigiloso."""
    if raw == "-":
        return 0.0
    try:
        return float(raw)
    except ValueError:
        return None


class Ibge:
    """Municípios (Localidades), Produção Agrícola Municipal (PAM) e estimativa mensal da safra (LSPA)."""

    def __init__(self, client: PublicDataClient):
        self._client = client

    def municipality(self, code: int) -> tuple[str, str]:
        """Nome e sigla da UF."""
        payload = self._client.get_json(f"{IBGE_LOCALIDADES}/municipios/{code}", source="o IBGE (municípios)")
        if not payload or not isinstance(payload, dict) or "nome" not in payload:
            raise SourceUnavailableError(f"O IBGE não tem município com o código {code}.")
        # municípios criados depois da divisão em microrregiões só têm a região imediata
        region = payload.get("microrregiao")
        state = (
            region["mesorregiao"]["UF"]["sigla"]
            if region
            else payload["regiao-imediata"]["regiao-intermediaria"]["UF"]["sigla"]
        )
        return payload["nome"], state

    def municipalities_of_state(self, state_acronym: str) -> list[tuple[int, str]]:
        payload = self._client.get_json(
            f"{IBGE_LOCALIDADES}/estados/{state_acronym}/municipios", {"orderBy": "nome"}, source="o IBGE (municípios)"
        )
        return [(int(m["id"]), m["nome"]) for m in payload]

    def pam_last_year(self) -> int:
        payload = self._client.get_json(f"{IBGE_AGREGADOS}/{PAM_TABLE}/periodos", source="o IBGE (PAM)")
        return max(int(p["id"]) for p in payload)

    def _sidra(self, path: str, source: str) -> list[dict]:
        payload = self._client.get_json(f"{SIDRA}/{path}", source=source)
        if not isinstance(payload, list):
            raise SourceUnavailableError(f"{source} respondeu algo inesperado.")
        return payload[1:]  # a primeira linha é o cabeçalho

    def pam(self, level: str, codes: list[int], start: int, end: int) -> list[CropYear]:
        territories = "all" if level == "brasil" else ",".join(str(c) for c in codes)
        products = ",".join(str(c.pam_code) for c in CROPS.values())
        rows = self._sidra(
            f"t/{PAM_TABLE}/{SIDRA_LEVELS[level]}/{territories}/v/{','.join(PAM_VARIABLES)}"
            f"/p/{start}-{end}/c782/{products}",
            "o IBGE (PAM)",
        )
        grouped: dict[tuple[int, str, int], dict[str, float | None]] = defaultdict(dict)
        for r in rows:
            crop = CROP_BY_PAM_CODE.get(int(r["D4C"]))
            if crop and r["D2C"] in PAM_VARIABLES:
                grouped[(int(r["D1C"]), crop.key, int(r["D3C"]))][PAM_VARIABLES[r["D2C"]]] = _sidra_value(r["V"])
        result = []
        for (territory, crop, year), values in grouped.items():
            if not values.get("production_t"):
                values["yield_kg_ha"] = None  # sem produção, o rendimento não tem sentido
            result.append(CropYear(level=level, territory_code=territory, crop=crop, year=year, **values))
        return result

    def top_soy_municipalities(self, state_code: int, year: int, count: int) -> list[tuple[int, str, float]]:
        """Municípios da UF com maior área plantada de soja no ano: (código, nome, hectares)."""
        rows = self._sidra(
            f"t/{PAM_TABLE}/n6/in%20n3%20{state_code}/v/8331/p/{year}/c782/{CROPS['soja'].pam_code}",
            "o IBGE (PAM)",
        )
        areas = [(int(r["D1C"]), _strip_state(r["D1N"]), _sidra_value(r["V"]) or 0.0) for r in rows]
        return sorted([a for a in areas if a[2] > 0], key=lambda a: -a[2])[:count]

    def lspa(self, level: str, codes: list[int], months: int) -> list[CropEstimate]:
        territories = "all" if level == "brasil" else ",".join(str(c) for c in codes)
        rows = self._sidra(
            f"t/{LSPA_TABLE}/{SIDRA_LEVELS[level]}/{territories}/v/{','.join(LSPA_VARIABLES)}"
            f"/p/last%20{months}/c48/{','.join(str(c) for c in LSPA_PRODUCTS)}",
            "o IBGE (LSPA)",
        )
        grouped: dict[tuple[int, str, int], dict[str, float | None]] = defaultdict(dict)
        for r in rows:
            product = LSPA_PRODUCTS.get(int(r["D4C"]))
            if product and r["D2C"] in LSPA_VARIABLES:
                grouped[(int(r["D1C"]), product, int(r["D3C"]))][LSPA_VARIABLES[r["D2C"]]] = _sidra_value(r["V"])
        return [
            CropEstimate(level=level, territory_code=t if level != "brasil" else BRAZIL_CODE, product=p, period=y, **v)
            for (t, p, y), v in grouped.items()
        ]
