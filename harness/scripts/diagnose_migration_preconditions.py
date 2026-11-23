"""Side-effect-free precondition diagnostics.

The probe functions accept injected collaborators. Importing this module and
running it without the explicit (future) runtime hook never opens a socket or
database connection. Only fixed allow-list codes are suitable for external
output; exception text is intentionally discarded.
"""

from __future__ import annotations

import argparse
import socket
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Protocol


ALLOWED_CODES = frozenset(
    {
        "DNS_PASS", "DNS_FAIL", "TCP_PASS", "TCP_FAIL", "TCP_TIMEOUT",
        "NETWORK_DIAGNOSTIC_UNKNOWN", "DB_AUTH_PASS", "DB_AUTH_FAIL",
        "DB_ACCESS_PASS", "DB_ACCESS_FAIL", "DB_CONNECTION_FAIL",
        "DB_PERMISSION_PASS", "DB_PERMISSION_FAIL", "DB_PERMISSION_UNKNOWN",
        "DB_DIAGNOSTIC_UNKNOWN", "DIAGNOSTIC_START", "DIAGNOSTIC_COMPLETE",
    }
)


class DbAdapter(Protocol):
    def authenticate(self) -> bool: ...
    def access_database(self) -> bool: ...
    def permission_snapshot(self, requirements: Iterable[str]) -> dict[str, bool | None]: ...
    def close(self) -> None: ...


@dataclass(frozen=True)
class ProbeResult:
    code: str

    def __post_init__(self) -> None:
        if self.code not in ALLOWED_CODES:
            raise ValueError("diagnostic code is not allow-listed")


def dns_probe(host: str, resolver: Callable[[str], Any] = socket.getaddrinfo) -> ProbeResult:
    try:
        resolver(host)
        return ProbeResult("DNS_PASS")
    except socket.timeout:
        return ProbeResult("DNS_FAIL")
    except Exception:
        return ProbeResult("NETWORK_DIAGNOSTIC_UNKNOWN")


def tcp_probe(
    host: str,
    port: int,
    connector: Callable[..., Any] = socket.create_connection,
    timeout: float = 3.0,
) -> ProbeResult:
    sock = None
    try:
        sock = connector((host, port), timeout=timeout)
        return ProbeResult("TCP_PASS")
    except socket.timeout:
        return ProbeResult("TCP_TIMEOUT")
    except OSError:
        return ProbeResult("TCP_FAIL")
    except Exception:
        return ProbeResult("NETWORK_DIAGNOSTIC_UNKNOWN")
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass


def db_probe(adapter: DbAdapter) -> list[ProbeResult]:
    results: list[ProbeResult] = []
    try:
        try:
            authenticated = bool(adapter.authenticate())
        except Exception:
            results.append(ProbeResult("DB_CONNECTION_FAIL"))
            return results
        results.append(ProbeResult("DB_AUTH_PASS" if authenticated else "DB_AUTH_FAIL"))
        if not authenticated:
            return results
        try:
            accessible = bool(adapter.access_database())
        except Exception:
            results.append(ProbeResult("DB_CONNECTION_FAIL"))
            return results
        results.append(ProbeResult("DB_ACCESS_PASS" if accessible else "DB_ACCESS_FAIL"))
    finally:
        try:
            adapter.close()
        except Exception:
            pass
    return results


def permission_probe(
    adapter: DbAdapter, requirements: Iterable[str]
) -> list[ProbeResult]:
    try:
        snapshot = adapter.permission_snapshot(tuple(requirements))
        values = list(snapshot.values())
        if not values or any(value is None for value in values):
            return [ProbeResult("DB_PERMISSION_UNKNOWN")]
        return [ProbeResult("DB_PERMISSION_PASS" if all(values) else "DB_PERMISSION_FAIL")]
    except Exception:
        return [ProbeResult("DB_PERMISSION_UNKNOWN")]


def safe_codes(results: Iterable[ProbeResult]) -> list[str]:
    """Return only allow-listed code strings, never exception details."""
    return [result.code for result in results if result.code in ALLOWED_CODES]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Precondition diagnostic library (runtime disabled by default).")
    parser.add_argument("--runtime", action="store_true", help="reserved; runtime is not enabled in FIX1")
    args = parser.parse_args(argv)
    if args.runtime:
        print("DB_DIAGNOSTIC_UNKNOWN")
        return 2
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
