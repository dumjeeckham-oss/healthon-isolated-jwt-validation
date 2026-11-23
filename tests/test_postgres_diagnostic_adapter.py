import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parents[1] / "harness" / "scripts"))
from postgres_diagnostic_adapter import (
    PERMISSION_SQL,
    READ_ONLY_ACCESS_SQL,
    PostgresDiagnosticAdapter,
)


class FakeCursor:
    def __init__(self, rows=()):
        self.rows = iter(rows)
        self.executed = []
        self.closed = False

    def execute(self, statement):
        self.executed.append(statement)

    def fetchone(self):
        return next(self.rows, None)

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursors=()):
        self.cursors = iter(cursors)
        self.closed = False

    def cursor(self):
        return next(self.cursors)

    def close(self):
        self.closed = True


class PostgresDiagnosticAdapterTests(unittest.TestCase):
    def test_import_creates_no_connection(self):
        factory = Mock()
        PostgresDiagnosticAdapter(factory)
        factory.assert_not_called()

    def test_authentication_is_connection_factory_only(self):
        connection = FakeConnection()
        factory = Mock(return_value=connection)
        adapter = PostgresDiagnosticAdapter(factory)
        self.assertTrue(adapter.authenticate())
        factory.assert_called_once_with()

    def test_access_uses_fixed_read_only_query_and_closes_cursor(self):
        cursor = FakeCursor(rows=[(1,)])
        adapter = PostgresDiagnosticAdapter(Mock(return_value=FakeConnection([cursor])))
        self.assertTrue(adapter.access_database())
        self.assertEqual(cursor.executed, [READ_ONLY_ACCESS_SQL])
        self.assertTrue(cursor.closed)

    def test_access_failure_and_timeout_propagate_without_output(self):
        factory = Mock(side_effect=TimeoutError("FAKE_DB_PASSWORD_SENTINEL"))
        adapter = PostgresDiagnosticAdapter(factory)
        with self.assertRaises(TimeoutError):
            adapter.authenticate()
        factory.assert_called_once_with()

    def test_permissions_use_fixed_read_only_queries(self):
        cursors = [FakeCursor(rows=[(True,)]), FakeCursor(rows=[(False,)])]
        adapter = PostgresDiagnosticAdapter(Mock(return_value=FakeConnection(cursors)))
        result = adapter.permission_snapshot(["database_connect", "schema_usage", "unknown"])
        self.assertEqual(result, {"database_connect": True, "schema_usage": False, "unknown": None})
        self.assertEqual(cursors[0].executed, [PERMISSION_SQL["database_connect"]])
        self.assertEqual(cursors[1].executed, [PERMISSION_SQL["schema_usage"]])

    def test_permissions_propagate_query_exception_and_close_cursor(self):
        cursor = FakeCursor()
        cursor.execute = Mock(side_effect=RuntimeError("FAKE_AUTH_TOKEN_SENTINEL"))
        adapter = PostgresDiagnosticAdapter(Mock(return_value=FakeConnection([cursor])))
        with self.assertRaises(RuntimeError):
            adapter.permission_snapshot(["database_connect"])
        self.assertTrue(cursor.closed)

    def test_close_is_idempotent_and_releases_connection(self):
        connection = FakeConnection()
        adapter = PostgresDiagnosticAdapter(Mock(return_value=connection))
        adapter.authenticate()
        adapter.close()
        adapter.close()
        self.assertTrue(connection.closed)

    def test_statements_are_read_only(self):
        for statement in [READ_ONLY_ACCESS_SQL, *PERMISSION_SQL.values()]:
            self.assertEqual(statement.lstrip().split(maxsplit=1)[0].upper(), "SELECT")


if __name__ == "__main__":
    unittest.main()
