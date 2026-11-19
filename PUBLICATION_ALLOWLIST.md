# Publication allowlist

| Path | Required | Secret risk | Production impact |
|---|---:|---|---|
| `.github/workflows/isolated-jwt-validation.yml` | yes | runtime secret references only | none |
| `harness/docker-compose.yml` | yes | local placeholders | none |
| `harness/scripts/preflight.py` | yes | none | none |
| `harness/scripts/bootstrap_users.py` | yes | runtime passwords only | none |
| `harness/requirements.txt` | yes | none | none |
| `fixtures/bootstrap.sql` | yes | none | none |
| `fixtures/before.sql` | yes | none | none |
| `fixtures/after.sql` | yes | none | none |
| `fixtures/reset.sql` | yes | none | none |
| `tests/test_real_jwt_rpc.py` | yes | runtime credentials only | none |
| `README.md`, `.gitignore`, `docs/*` | yes | none | none |

SHA-256 values are recorded in the Phase 3.3F-2B-1B report in the source repository.
