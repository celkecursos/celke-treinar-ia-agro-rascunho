from app.repositories.database import Database


class SettingRepository:
    """Escolhas feitas no painel, guardadas como pares chave e valor."""

    def __init__(self, database: Database):
        self._db = database

    def all(self) -> dict[str, str]:
        with self._db.connection() as conn:
            rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
        return {r["key"]: r["value"] for r in rows}

    def save(self, values: dict[str, str]) -> None:
        with self._db.connection() as conn:
            for key, value in values.items():
                conn.execute(
                    "INSERT INTO app_settings (key, value) VALUES (%s, %s)"
                    " ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()",
                    (key, value),
                )

    def delete(self, keys: list[str]) -> None:
        with self._db.connection() as conn:
            conn.execute("DELETE FROM app_settings WHERE key = ANY(%s)", (keys,))
