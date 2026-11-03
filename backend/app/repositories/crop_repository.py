from dataclasses import dataclass

from app.repositories.database import Database


@dataclass(frozen=True)
class CropYear:
    level: str
    territory_code: int
    crop: str
    year: int
    planted_area_ha: float | None = None
    harvested_area_ha: float | None = None
    production_t: float | None = None
    yield_kg_ha: float | None = None


@dataclass(frozen=True)
class CropEstimate:
    level: str
    territory_code: int
    product: str
    period: int
    planted_area_ha: float | None = None
    harvested_area_ha: float | None = None
    production_t: float | None = None
    yield_kg_ha: float | None = None


_VALUES = ("planted_area_ha", "harvested_area_ha", "production_t", "yield_kg_ha")


class CropRepository:
    """Produção anual (PAM) e estimativas mensais da safra (LSPA)."""

    def __init__(self, database: Database):
        self._db = database

    def _save(self, table: str, keys: tuple[str, ...], rows: list) -> int:
        """Grava e devolve quantas linhas entraram ou mudaram de valor."""
        if not rows:
            return 0
        columns = keys + _VALUES
        types = {"level": "text", "crop": "text", "product": "text"}
        arrays = ", ".join(f"%s::{types.get(c, 'int' if c in keys else 'float8')}[]" for c in columns)
        changed = " OR ".join(f"{table}.{c} IS DISTINCT FROM EXCLUDED.{c}" for c in _VALUES)
        with self._db.connection() as conn:
            result = conn.execute(
                f"INSERT INTO {table} ({', '.join(columns)}) SELECT * FROM unnest({arrays})"
                f" ON CONFLICT ({', '.join(keys)}) DO UPDATE SET "
                + ", ".join(f"{c} = EXCLUDED.{c}" for c in _VALUES)
                + f" WHERE {changed} RETURNING 1",
                [[getattr(r, c) for r in rows] for c in columns],
            ).fetchall()
        return len(result)

    def save_yearly(self, rows: list[CropYear]) -> int:
        return self._save("crop_yearly", ("level", "territory_code", "crop", "year"), rows)

    def save_estimates(self, rows: list[CropEstimate]) -> int:
        return self._save("crop_estimates", ("level", "territory_code", "product", "period"), rows)

    def yearly(self, level: str, territory_code: int, crop: str) -> list[CropYear]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT * FROM crop_yearly WHERE level = %s AND territory_code = %s AND crop = %s ORDER BY year",
                (level, territory_code, crop),
            ).fetchall()
        return [CropYear(**r) for r in rows]

    def last_years(self) -> dict[tuple[str, int], int]:
        """Último ano guardado de cada território."""
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT level, territory_code, max(year) AS year FROM crop_yearly GROUP BY level, territory_code"
            ).fetchall()
        return {(r["level"], r["territory_code"]): r["year"] for r in rows}

    def last_year(self) -> int | None:
        with self._db.connection() as conn:
            return conn.execute("SELECT max(year) AS year FROM crop_yearly").fetchone()["year"]

    def last_period(self) -> int | None:
        with self._db.connection() as conn:
            return conn.execute("SELECT max(period) AS period FROM crop_estimates").fetchone()["period"]

    def latest_estimates(self) -> list[CropEstimate]:
        """O levantamento mais recente de cada território e produto."""
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT ON (level, territory_code, product) * FROM crop_estimates"
                " ORDER BY level, territory_code, product, period DESC"
            ).fetchall()
        return [CropEstimate(**r) for r in rows]
