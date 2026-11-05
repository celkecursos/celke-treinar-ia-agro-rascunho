import uuid
from dataclasses import dataclass, field
from typing import Any

from psycopg.types.json import Jsonb

from app.repositories.database import Database
from app.schemas.insights import Alert, Discovery, DiscoveryReport

KEEP_REPORTS = 10


@dataclass
class NewDiscovery:
    municipality_code: int
    crop: str
    kind: str
    title: str
    fact: str
    stats: dict[str, Any]
    chart: dict[str, Any] | None = None


@dataclass
class NewAlert:
    municipality_code: int
    crop: str
    kind: str
    season_year: int
    severity: str
    title: str
    message: str
    facts: dict[str, Any] = field(default_factory=dict)
    chart: dict[str, Any] | None = None


_DISCOVERY = """
SELECT d.*, m.name || ' (' || m.state || ')' AS municipality_name
FROM discoveries d JOIN municipalities m ON m.code = d.municipality_code
"""
_ALERT = """
SELECT a.*, m.name || ' (' || m.state || ')' AS municipality_name
FROM alerts a JOIN municipalities m ON m.code = a.municipality_code
"""


class InsightRepository:
    """Relatórios de descobertas e alertas da safra em andamento."""

    def __init__(self, database: Database):
        self._db = database

    # Descobertas

    def create_report(self, *, model: str) -> str:
        """Relatório novo, já como `gerando`: a tela mostra o andamento desde a varredura."""
        report_id = uuid.uuid4().hex
        with self._db.connection() as conn:
            conn.execute(
                "INSERT INTO discovery_reports (id, status, model) VALUES (%s, 'gerando', %s)", (report_id, model)
            )
            # só os relatórios mais recentes ficam guardados
            conn.execute(
                "DELETE FROM discovery_reports WHERE id NOT IN"
                " (SELECT id FROM discovery_reports ORDER BY created_at DESC LIMIT %s)",
                (KEEP_REPORTS,),
            )
        return report_id

    def add_discoveries(self, report_id: str, *, tests: int, discoveries: list[NewDiscovery]) -> None:
        with self._db.connection() as conn:
            conn.execute("UPDATE discovery_reports SET tests = %s WHERE id = %s", (tests, report_id))
            for position, d in enumerate(discoveries):
                conn.execute(
                    "INSERT INTO discoveries"
                    " (id, report_id, position, municipality_code, crop, kind, title, fact, stats, chart)"
                    " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        uuid.uuid4().hex,
                        report_id,
                        position,
                        d.municipality_code,
                        d.crop,
                        d.kind,
                        d.title,
                        d.fact,
                        Jsonb(d.stats),
                        Jsonb(d.chart) if d.chart else None,
                    ),
                )

    def save_interpretations(self, report_id: str, interpretations: dict[str, tuple[str | None, str | None]]) -> None:
        with self._db.connection() as conn:
            for discovery_id, (interpretation, hypothesis) in interpretations.items():
                conn.execute(
                    "UPDATE discoveries SET interpretation = %s, hypothesis = %s WHERE id = %s AND report_id = %s",
                    (interpretation, hypothesis, discovery_id, report_id),
                )

    def finish_report(
        self,
        report_id: str,
        *,
        summary: str | None,
        next_questions: list[str],
        interpretations: dict[str, tuple[str | None, str | None]],
        error_message: str | None = None,
    ) -> None:
        with self._db.connection() as conn:
            for discovery_id, (interpretation, hypothesis) in interpretations.items():
                conn.execute(
                    "UPDATE discoveries SET interpretation = %s, hypothesis = %s WHERE id = %s AND report_id = %s",
                    (interpretation, hypothesis, discovery_id, report_id),
                )
            conn.execute(
                "UPDATE discovery_reports SET status = %s, summary = %s, next_questions = %s, error_message = %s,"
                " finished_at = now() WHERE id = %s",
                ("erro" if error_message else "pronto", summary, Jsonb(next_questions), error_message, report_id),
            )

    def mark_interrupted(self) -> int:
        with self._db.connection() as conn:
            return conn.execute(
                "UPDATE discovery_reports SET status = 'erro', finished_at = now(),"
                " error_message = 'Geração interrompida (o backend reiniciou).' WHERE status = 'gerando'"
            ).rowcount

    def report(self, report_id: str | None = None) -> DiscoveryReport | None:
        """O relatório pedido ou, sem id, o mais recente."""
        with self._db.connection() as conn:
            if report_id:
                row = conn.execute("SELECT * FROM discovery_reports WHERE id = %s", (report_id,)).fetchone()
            else:
                row = conn.execute("SELECT * FROM discovery_reports ORDER BY created_at DESC LIMIT 1").fetchone()
            if row is None:
                return None
            items = conn.execute(_DISCOVERY + " WHERE d.report_id = %s ORDER BY d.position", (row["id"],)).fetchall()
        return DiscoveryReport(**row, discoveries=[Discovery(**d) for d in items])

    # Alertas

    def sync_alerts(self, alerts: list[NewAlert]) -> list[str]:
        """Grava os alertas de agora e desativa os que deixaram de valer. Devolve os ids dos alertas novos."""
        created: list[str] = []
        with self._db.connection() as conn:
            keep: list[str] = []
            for a in alerts:
                row = conn.execute(
                    "INSERT INTO alerts"
                    " (id, municipality_code, crop, kind, season_year, severity, title, message, facts, chart)"
                    " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                    " ON CONFLICT (municipality_code, crop, kind, season_year) DO UPDATE SET"
                    " severity = EXCLUDED.severity, title = EXCLUDED.title, message = EXCLUDED.message,"
                    " facts = EXCLUDED.facts, chart = EXCLUDED.chart, active = true, updated_at = now()"
                    " RETURNING id, (xmax = 0) AS inserted",
                    (
                        uuid.uuid4().hex,
                        a.municipality_code,
                        a.crop,
                        a.kind,
                        a.season_year,
                        a.severity,
                        a.title,
                        a.message,
                        Jsonb(a.facts),
                        Jsonb(a.chart) if a.chart else None,
                    ),
                ).fetchone()
                keep.append(row["id"])
                if row["inserted"]:
                    created.append(row["id"])
            conn.execute(
                "UPDATE alerts SET active = false, updated_at = now() WHERE active AND NOT (id = ANY(%s))", (keep,)
            )
        return created

    def alerts(self, *, active_only: bool = True) -> list[Alert]:
        where = " WHERE a.active" if active_only else ""
        with self._db.connection() as conn:
            rows = conn.execute(_ALERT + where + " ORDER BY a.active DESC, a.updated_at DESC LIMIT 100").fetchall()
        return [Alert(**r) for r in rows]

    def alert(self, alert_id: str) -> Alert | None:
        with self._db.connection() as conn:
            row = conn.execute(_ALERT + " WHERE a.id = %s", (alert_id,)).fetchone()
        return Alert(**row) if row else None

    def set_explanation(self, alert_id: str, explanation: str) -> None:
        with self._db.connection() as conn:
            conn.execute("UPDATE alerts SET explanation = %s WHERE id = %s", (explanation, alert_id))
