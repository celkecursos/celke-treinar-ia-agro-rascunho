import uuid

from psycopg.types.json import Jsonb

from app.repositories.database import Database
from app.schemas.forecasts import ForecastHistoryItem, ForecastRecord, TrainedForecast

KEEP_PER_MODEL = 20


class ForecastRepository:
    """Histórico dos treinos do modelo de previsão (um registro por treino, por município e cultura)."""

    def __init__(self, database: Database):
        self._db = database

    def save(self, result: TrainedForecast, *, trigger: str, model: str) -> str:
        forecast_id = uuid.uuid4().hex
        with self._db.connection() as conn:
            conn.execute(
                "INSERT INTO forecast_models (id, municipality_code, crop, trigger, model, result)"
                " VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    forecast_id,
                    result.municipality_code,
                    result.crop,
                    trigger,
                    model,
                    Jsonb(result.model_dump(mode="json")),
                ),
            )
            conn.execute(
                "DELETE FROM forecast_models WHERE municipality_code = %s AND crop = %s AND id NOT IN"
                " (SELECT id FROM forecast_models WHERE municipality_code = %s AND crop = %s"
                " ORDER BY trained_at DESC LIMIT %s)",
                (result.municipality_code, result.crop, result.municipality_code, result.crop, KEEP_PER_MODEL),
            )
        return forecast_id

    def set_explanation(self, forecast_id: str, explanation: str) -> None:
        with self._db.connection() as conn:
            conn.execute("UPDATE forecast_models SET explanation = %s WHERE id = %s", (explanation, forecast_id))

    def latest(self, code: int, crop: str) -> ForecastRecord | None:
        with self._db.connection() as conn:
            row = conn.execute(
                "SELECT * FROM forecast_models WHERE municipality_code = %s AND crop = %s"
                " ORDER BY trained_at DESC LIMIT 1",
                (code, crop),
            ).fetchone()
        return ForecastRecord(**row) if row else None

    def history(self, code: int, crop: str, limit: int = 10) -> list[ForecastHistoryItem]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT id, trigger, trained_at, result FROM forecast_models WHERE municipality_code = %s"
                " AND crop = %s ORDER BY trained_at DESC LIMIT %s",
                (code, crop, limit),
            ).fetchall()
        return [
            ForecastHistoryItem(
                id=r["id"],
                trigger=r["trigger"],
                trained_at=r["trained_at"],
                seasons_used=r["result"]["seasons_used"],
                features=[f["label"] for f in r["result"]["features"]],
                error_pct=r["result"]["error_pct"],
                baseline_error_pct=r["result"]["baseline_error_pct"],
            )
            for r in rows
        ]
