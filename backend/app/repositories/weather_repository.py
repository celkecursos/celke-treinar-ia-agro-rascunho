from datetime import date

from app.repositories.database import Database

DailyRain = list[tuple[date, float]]


class WeatherRepository:
    """Chuva diária por município."""

    def __init__(self, database: Database):
        self._db = database

    def last_archive_day(self, code: int) -> date | None:
        with self._db.connection() as conn:
            row = conn.execute(
                "SELECT max(day) AS day FROM weather_daily WHERE municipality_code = %s AND source = 'arquivo'",
                (code,),
            ).fetchone()
        return row["day"]

    def save(self, code: int, days: DailyRain, *, source: str) -> int:
        """Grava os dias e devolve quantos entraram ou mudaram. O dado `recente` nunca substitui o do arquivo."""
        if not days:
            return 0
        guard = "" if source == "arquivo" else " AND weather_daily.source <> 'arquivo'"
        with self._db.connection() as conn:
            rows = conn.execute(
                "INSERT INTO weather_daily (municipality_code, day, precipitation_mm, source)"
                " SELECT %s, d, mm, %s FROM unnest(%s::date[], %s::float8[]) AS t(d, mm)"
                " ON CONFLICT (municipality_code, day) DO UPDATE"
                " SET precipitation_mm = EXCLUDED.precipitation_mm, source = EXCLUDED.source"
                " WHERE (weather_daily.precipitation_mm, weather_daily.source)"
                " IS DISTINCT FROM (EXCLUDED.precipitation_mm, EXCLUDED.source)" + guard + " RETURNING 1",
                (code, source, [d for d, _ in days], [mm for _, mm in days]),
            ).fetchall()
        return len(rows)

    def daily(self, code: int, start: date | None = None, end: date | None = None) -> DailyRain:
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT day, precipitation_mm FROM weather_daily WHERE municipality_code = %s"
                " AND (%s::date IS NULL OR day >= %s) AND (%s::date IS NULL OR day <= %s) ORDER BY day",
                (code, start, start, end, end),
            ).fetchall()
        return [(r["day"], r["precipitation_mm"]) for r in rows]

    def last_day(self) -> date | None:
        with self._db.connection() as conn:
            return conn.execute("SELECT max(day) AS day FROM weather_daily").fetchone()["day"]
