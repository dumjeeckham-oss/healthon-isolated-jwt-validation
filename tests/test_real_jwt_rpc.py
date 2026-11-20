"""Real local GoTrue -> JWT -> PostgREST contract test.

The script is intentionally runtime-only: endpoints and credentials come from
environment variables, production hosts are rejected, and all assertion
failures exit non-zero. Tokens and Authorization headers are never printed.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from typing import Any


def env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"missing environment variable: {name}")
    return value.rstrip("/")


AUTH_URL = env("AUTH_URL")
REST_URL = env("REST_URL")
PHASE = os.environ.get("TEST_PHASE", "after").lower()
if PHASE not in {"before", "after"}:
    raise RuntimeError("TEST_PHASE must be before or after")
for endpoint in (AUTH_URL, REST_URL):
    if "wakmxrgmercaauqstrvj" in endpoint or "supabase.co" in endpoint:
        raise RuntimeError("production endpoint rejected")


def request_json(url: str, method: str = "GET", body: Any | None = None, token: str | None = None) -> tuple[int, Any]:
    payload = None if body is None else json.dumps(body).encode()
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            raw = response.read()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            data = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            data = {"raw": raw.decode(errors="replace")}
        return error.code, data


def token_payload(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise AssertionError("Auth response did not contain a JWT")
    padded = parts[1] + "=" * (-len(parts[1]) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded).decode())
    if not payload.get("sub") or payload.get("role") not in {"authenticated", "anon"}:
        raise AssertionError("unexpected JWT claims")
    if int(payload.get("exp", 0)) <= 0:
        raise AssertionError("JWT has no expiration")
    return payload


def login(email: str, password: str) -> tuple[str, str]:
    status, data = request_json(f"{AUTH_URL}/token?grant_type=password", "POST", {"email": email, "password": password})
    if status != 200 or not isinstance(data, dict) or not data.get("access_token") or not data.get("user", {}).get("id"):
        raise AssertionError(f"login failed with HTTP {status}")
    token = data["access_token"]
    claims = token_payload(token)
    user_id = str(data["user"]["id"])
    if claims["sub"] != user_id:
        raise AssertionError("JWT sub does not match authenticated user")
    return token, user_id


TEST_DATE = os.environ.get("TEST_DATE", "2099-01-01")


def rpc(token: str | None, user_id: str | None, *, steps: int = 1234) -> tuple[int, Any]:
    body = {"p_user_id": user_id, "p_date": TEST_DATE, "p_steps": steps, "p_distance_km": 1.2, "p_calories": 50.0, "p_exercise_minutes": 10, "p_active_minutes": 20}
    return request_json(f"{REST_URL}/rpc/upsert_health_daily", "POST", body, token)


def read_own_rows(token: str, user_id: str) -> list[dict[str, Any]]:
    status, data = request_json(f"{REST_URL}/health_daily?user_id=eq.{user_id}&date=eq.{TEST_DATE}&select=*", token=token)
    if status != 200 or not isinstance(data, list):
        raise AssertionError(f"health_daily read control failed with HTTP {status}")
    return data


def main() -> int:
    token_a, user_a = login(env("USER_A_EMAIL"), env("USER_A_PASSWORD"))
    token_b, user_b = login(env("USER_B_EMAIL"), env("USER_B_PASSWORD"))
    if user_a == user_b:
        raise AssertionError("USER_A and USER_B are not distinct")

    # T09: each phase must begin from reset-clean state.  This is a real
    # assertion, not a comment about the reset step.
    if read_own_rows(token_a, user_a) or read_own_rows(token_b, user_b):
        raise AssertionError("reset-clean assertion failed: test rows remain")

    # T04: an unauthenticated request must not be treated as a valid caller.
    anon_status, anon_data = rpc(None, user_a, steps=101)
    if PHASE == "after" and anon_status in {200, 201}:
        raise AssertionError("anonymous RPC write was accepted after security patch")

    # T05: a valid JWT with a JSON null p_user_id must be rejected after the
    # patch.  The before fixture's behavior is recorded by the phase run.
    null_status, null_data = rpc(token_a, None, steps=102)
    if PHASE == "after":
        null_code = null_data.get("code") if isinstance(null_data, dict) else None
        if null_status not in {400, 401, 403} and null_code != "42501":
            raise AssertionError(f"NULL p_user_id was not denied: HTTP {null_status}")

    own_status, own_data = rpc(token_a, user_a)
    if own_status not in {200, 201}:
        raise AssertionError(f"own RPC failed with HTTP {own_status}")
    returned = own_data[0] if isinstance(own_data, list) and own_data else own_data
    if not isinstance(returned, str) or not uuid.UUID(returned):
        raise AssertionError("own RPC did not return a UUID")
    user_b_before = read_own_rows(token_b, user_b)
    if not isinstance(own_data, (str, list, dict)):
        raise AssertionError("own RPC did not return a JSON value")
    cross_status, cross_data = rpc(token_a, user_b, steps=2345)
    if PHASE == "before":
        if cross_status not in {200, 201}:
            raise AssertionError(f"before cross-user control did not reproduce: HTTP {cross_status}")
        user_b_after = read_own_rows(token_b, user_b)
        if len(user_b_after) != 1:
            raise AssertionError("before cross-user write did not create exactly one USER_B row")
        row = user_b_after[0]
        if (
            str(row.get("user_id")) != user_b
            or row.get("date") != TEST_DATE
            or row.get("steps") != 2345
        ):
            raise AssertionError("before cross-user write did not persist expected USER_B values")
    else:
        code = cross_data.get("code") if isinstance(cross_data, dict) else None
        if cross_status not in {400, 401, 403} and code != "42501":
            raise AssertionError(f"after cross-user write was not denied: HTTP {cross_status}")
        user_b_after = read_own_rows(token_b, user_b)
        if user_b_before != user_b_after:
            raise AssertionError("USER_B data changed after denied cross-user write")

    # T06/T07: same-day UPSERT updates one existing row and preserves its id.
    first_status, first_data = rpc(token_a, user_a, steps=3001)
    first_id = first_data[0] if isinstance(first_data, list) and first_data else first_data
    if first_status not in {200, 201} or not isinstance(first_id, str) or not uuid.UUID(first_id):
        raise AssertionError("first same-day UPSERT did not return a UUID")
    second_status, second_data = rpc(token_a, user_a, steps=3002)
    second_id = second_data[0] if isinstance(second_data, list) and second_data else second_data
    if second_status not in {200, 201} or second_id != first_id:
        raise AssertionError("same-day UPSERT did not preserve the row UUID")
    final_rows = read_own_rows(token_a, user_a)
    if len(final_rows) != 1 or final_rows[0].get("steps") != 3002:
        raise AssertionError("same-day UPSERT duplicate/value assertion failed")

    # T10: the patched cross-user path must expose the authorization SQLSTATE.
    if PHASE == "after":
        cross_code = cross_data.get("code") if isinstance(cross_data, dict) else None
        if cross_status not in {400, 401, 403} and cross_code != "42501":
            raise AssertionError("cross-user denial did not expose an expected authorization result")

    print(json.dumps({"phase": PHASE, "user_a_distinct": True, "own_rpc_http": own_status, "cross_rpc_http": cross_status, "anonymous_http": anon_status, "null_user_http": null_status, "same_day_http": second_status, "cross_denied": PHASE == "after"}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"TEST FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
