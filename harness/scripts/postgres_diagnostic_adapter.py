"""Injectable, read-only PostgreSQL diagnostic adapter.

This module intentionally does not import a PostgreSQL driver or open a
connection at import time. A future runtime supplies a connection factory;
tests supply fakes. SQL statements are fixed read-only queries.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any


READ_ONLY_ACCESS_SQL = "SELECT 1"
PERMISSION_SQL = {
    "database_connect": "SELECT has_database_privilege(current_user, current_database(), 'CONNECT')",
    "schema_usage": "SELECT has_schema_privilege(current_user, 'auth', 'USAGE')",
    "schema_create": "SELECT has_schema_privilege(current_user, 'auth', 'CREATE')",
}


class PostgresDiagnosticAdapter:
    """Adapter conforming to the existing injected DbAdapter contract."""

    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self._connection_factory = connection_factory
        self._connection: Any | None = None

    def _connection_or_raise(self) -> Any:
        if self._connection is None:
            self._connection = self._connection_factory()
        return self._connection

    def authenticate(self) -> bool:
        """Opening the injected connection is the future driver's auth check."""
        self._connection_or_raise()
        return True

    def access_database(self) -> bool:
        cursor = self._connection_or_raise().cursor()
        try:
            cursor.execute(READ_ONLY_ACCESS_SQL)
            row = cursor.fetchone()
            return row is not None
        finally:
            cursor.close()

    def permission_snapshot(self, requirements: Iterable[str]) -> dict[str, bool | None]:
        connection = self._connection_or_raise()
        snapshot: dict[str, bool | None] = {}
        for requirement in requirements:
            statement = PERMISSION_SQL.get(requirement)
            if statement is None:
                snapshot[requirement] = None
                continue
            cursor = connection.cursor()
            try:
                cursor.execute(statement)
                row = cursor.fetchone()
                snapshot[requirement] = None if row is None else bool(row[0])
            finally:
                cursor.close()
        return snapshot

    def close(self) -> None:
        if self._connection is None:
            return
        try:
            self._connection.close()
        finally:
            self._connection = None
