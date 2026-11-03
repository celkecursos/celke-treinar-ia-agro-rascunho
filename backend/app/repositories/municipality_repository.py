from dataclasses import dataclass

from app.repositories.database import Database
from app.schemas.municipalities import Municipality, MunicipalityStatus

_SELECT = """
SELECT m.*, w.first_day AS rain_first_day, w.last_day AS rain_last_day, COALESCE(w.days, 0) AS rain_days,
       c.last_year AS production_last_year
FROM municipalities m
LEFT JOIN LATERAL (
    SELECT min(day) AS first_day, max(day) AS last_day, count(*) AS days
    FROM weather_daily WHERE municipality_code = m.code
) w ON true
LEFT JOIN LATERAL (
    SELECT max(year) AS last_year FROM crop_yearly WHERE level = 'municipio' AND territory_code = m.code
) c ON true
"""


@dataclass(frozen=True)
class StateReference:
    municipality_code: int
    area_ha: float
    year: int


class MunicipalityRepository:
    """Municípios (cadastrados e de referência da UF) e as referências da chuva média de cada UF."""

    def __init__(self, database: Database):
        self._db = database

    def upsert(
        self, *, code: int, name: str, state_code: int, state: str, latitude: float, longitude: float, principal: bool
    ) -> None:
        """Um município que já existe como referência vira principal; o contrário nunca acontece aqui."""
        with self._db.connection() as conn:
            conn.execute(
                "INSERT INTO municipalities (code, name, state_code, state, latitude, longitude, principal)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s)"
                " ON CONFLICT (code) DO UPDATE SET principal = municipalities.principal OR EXCLUDED.principal",
                (code, name, state_code, state, latitude, longitude, principal),
            )

    def get(self, code: int) -> Municipality | None:
        with self._db.connection() as conn:
            row = conn.execute(_SELECT + " WHERE m.code = %s", (code,)).fetchone()
        return Municipality(**row) if row else None

    def all(self, *, principal_only: bool = True) -> list[Municipality]:
        where = " WHERE m.principal" if principal_only else ""
        with self._db.connection() as conn:
            rows = conn.execute(_SELECT + where + " ORDER BY m.state, m.name").fetchall()
        return [Municipality(**r) for r in rows]

    def codes(self) -> list[int]:
        """Todos os municípios com chuva coletada: principais e referências."""
        with self._db.connection() as conn:
            return [r["code"] for r in conn.execute("SELECT code FROM municipalities ORDER BY code").fetchall()]

    def set_status(self, code: int, status: MunicipalityStatus, message: str | None = None) -> None:
        with self._db.connection() as conn:
            conn.execute(
                "UPDATE municipalities SET status = %s, status_message = %s WHERE code = %s", (status, message, code)
            )

    def mark_interrupted(self) -> int:
        with self._db.connection() as conn:
            return conn.execute(
                "UPDATE municipalities SET status = 'erro',"
                " status_message = 'Coleta interrompida (o backend reiniciou). Clique em Coletar chuva.'"
                " WHERE status = 'coletando'"
            ).rowcount

    def remove_principal(self, code: int) -> bool:
        """Tira o município dos cadastrados e apaga o que não for mais usado por nenhum outro."""
        with self._db.connection() as conn:
            row = conn.execute(
                "UPDATE municipalities SET principal = false WHERE code = %s AND principal RETURNING state_code",
                (code,),
            ).fetchone()
            if row is None:
                return False
            # sem cadastrados na UF, as referências dela não servem mais
            conn.execute(
                "DELETE FROM state_references WHERE state_code = %s AND NOT EXISTS"
                " (SELECT 1 FROM municipalities WHERE principal AND state_code = %s)",
                (row["state_code"], row["state_code"]),
            )
            # a chuva sai junto (ON DELETE CASCADE); a produção municipal não tem chave estrangeira
            conn.execute(
                "DELETE FROM municipalities m WHERE NOT m.principal"
                " AND NOT EXISTS (SELECT 1 FROM state_references r WHERE r.municipality_code = m.code)"
            )
            conn.execute(
                "DELETE FROM crop_yearly c WHERE c.level = 'municipio'"
                " AND NOT EXISTS (SELECT 1 FROM municipalities m WHERE m.code = c.territory_code)"
            )
        return True

    def state_codes(self) -> list[int]:
        """UFs com ao menos um município cadastrado."""
        with self._db.connection() as conn:
            rows = conn.execute("SELECT DISTINCT state_code FROM municipalities WHERE principal ORDER BY 1").fetchall()
        return [r["state_code"] for r in rows]

    def references(self, state_code: int) -> list[StateReference]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "SELECT municipality_code, area_ha, year FROM state_references WHERE state_code = %s"
                " ORDER BY area_ha DESC",
                (state_code,),
            ).fetchall()
        return [StateReference(**r) for r in rows]

    def replace_references(self, state_code: int, references: list[StateReference]) -> None:
        with self._db.connection() as conn:
            conn.execute("DELETE FROM state_references WHERE state_code = %s", (state_code,))
            for ref in references:
                conn.execute(
                    "INSERT INTO state_references (state_code, municipality_code, area_ha, year) VALUES (%s, %s, %s, %s)",
                    (state_code, ref.municipality_code, ref.area_ha, ref.year),
                )
