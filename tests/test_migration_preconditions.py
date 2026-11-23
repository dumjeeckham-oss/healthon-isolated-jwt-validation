import io
import socket
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).parents[1] / "harness" / "scripts"))
import diagnose_migration_preconditions as d


class FakeDb:
    def __init__(self, auth=True, access=True, permissions=None):
        self.auth = auth
        self.access = access
        self.permissions = permissions if permissions is not None else {"connect": True}
        self.closed = False

    def authenticate(self): return self.auth
    def access_database(self): return self.access
    def permission_snapshot(self, requirements): return {r: self.permissions.get(r) for r in requirements}
    def close(self): self.closed = True


class DiagnosticTests(unittest.TestCase):
    def test_dns_outcomes(self):
        self.assertEqual(d.dns_probe("db", lambda _: [object()]).code, "DNS_PASS")
        self.assertEqual(d.dns_probe("db", Mock(side_effect=OSError())).code, "NETWORK_DIAGNOSTIC_UNKNOWN")

    def test_tcp_outcomes_and_cleanup(self):
        sock = Mock()
        self.assertEqual(d.tcp_probe("db", 5432, lambda *_args, **_kw: sock).code, "TCP_PASS")
        sock.close.assert_called_once()
        self.assertEqual(d.tcp_probe("db", 5432, Mock(side_effect=socket.timeout())).code, "TCP_TIMEOUT")
        self.assertEqual(d.tcp_probe("db", 5432, Mock(side_effect=OSError())).code, "TCP_FAIL")

    def test_db_auth_access_and_close(self):
        fake = FakeDb()
        self.assertEqual(d.safe_codes(d.db_probe(fake)), ["DB_AUTH_PASS", "DB_ACCESS_PASS"])
        self.assertTrue(fake.closed)
        self.assertEqual(d.safe_codes(d.db_probe(FakeDb(auth=False))), ["DB_AUTH_FAIL"])

    def test_db_unexpected_error_is_fixed_code(self):
        fake = FakeDb()
        fake.authenticate = Mock(side_effect=RuntimeError("FAKE_DB_PASSWORD_SENTINEL"))
        self.assertEqual(d.safe_codes(d.db_probe(fake)), ["DB_CONNECTION_FAIL"])

    def test_permission_outcomes(self):
        self.assertEqual(d.safe_codes(d.permission_probe(FakeDb(), ["connect"])), ["DB_PERMISSION_PASS"])
        self.assertEqual(d.safe_codes(d.permission_probe(FakeDb(permissions={"connect": False}), ["connect"])), ["DB_PERMISSION_FAIL"])
        self.assertEqual(d.safe_codes(d.permission_probe(FakeDb(permissions={}), ["connect"])), ["DB_PERMISSION_UNKNOWN"])

    def test_permission_exception_is_unknown(self):
        fake = FakeDb()
        fake.permission_snapshot = Mock(side_effect=RuntimeError("FAKE_SECRET_SENTINEL"))
        self.assertEqual(d.safe_codes(d.permission_probe(fake, ["connect"])), ["DB_PERMISSION_UNKNOWN"])

    def test_import_and_cli_do_not_connect(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(d.main([]), 0)
        self.assertNotIn("SENTINEL", output.getvalue())
        self.assertEqual(d.main(["--runtime"]), 2)

    def test_allow_list_rejects_unknown_result(self):
        with self.assertRaises(ValueError):
            d.ProbeResult("RAW_EXCEPTION")


if __name__ == "__main__":
    unittest.main()
