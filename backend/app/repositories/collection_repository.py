import uuid

from app.repositories.database import Database
from app.schemas.collections import CollectionRun, CollectionSource, CollectionTrigger, RunStatus


class CollectionRepository:
    """Registro de cada coleta: quando rodou, quem disparou, quantos registros trouxe e se deu erro."""

    def __init__(self, database: Database):
        self._db = database

    def start(self, source: CollectionSource, trigger: CollectionTrigger) -> CollectionRun:
        with self._db.connection() as conn:
            row = conn.execute(
                "INSERT INTO collection_runs (id, source, trigger, status) VALUES (%s, %s, %s, 'executando')"
                " RETURNING *",
                (uuid.uuid4().hex, source, trigger),
            ).fetchone()
        return CollectionRun(**row)

    def finish(self, run_id: str, status: RunStatus, records: int = 0, message: str | None = None) -> None:
        with self._db.connection() as conn:
            conn.execute(
                "UPDATE collection_runs SET status = %s, records = %s, message = %s, finished_at = now() WHERE id = %s",
                (status, records, message, run_id),
            )

    def recent(self, limit: int = 50) -> list[CollectionRun]:
        with self._db.connection() as conn:
            rows = conn.execute("SELECT * FROM collection_runs ORDER BY started_at DESC LIMIT %s", (limit,)).fetchall()
        return [CollectionRun(**r) for r in rows]

    def last(self, source: CollectionSource, *, successful: bool = False) -> CollectionRun | None:
        """A última coleta da fonte; com `successful`, só as que terminaram bem (com ou sem novidade)."""
        status = " AND status IN ('concluida', 'sem_novidade')" if successful else ""
        with self._db.connection() as conn:
            row = conn.execute(
                f"SELECT * FROM collection_runs WHERE source = %s{status} ORDER BY started_at DESC LIMIT 1", (source,)
            ).fetchone()
        return CollectionRun(**row) if row else None

    def mark_interrupted(self) -> int:
        with self._db.connection() as conn:
            return conn.execute(
                "UPDATE collection_runs SET status = 'erro', finished_at = now(),"
                " message = 'Coleta interrompida (o backend reiniciou).' WHERE status = 'executando'"
            ).rowcount
