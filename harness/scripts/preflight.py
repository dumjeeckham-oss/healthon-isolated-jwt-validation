from pathlib import Path
import os

root = Path(__file__).resolve().parents[2]
required = [root / "harness" / "docker-compose.yml", root / "fixtures" / "bootstrap.sql", root / "fixtures" / "before.sql", root / "fixtures" / "after.sql", root / "fixtures" / "reset.sql", root / "tests" / "test_real_jwt_rpc.py"]
missing = [str(p) for p in required if not p.is_file()]
if missing:
    raise SystemExit("missing required files: " + ", ".join(missing))
for key in ("AUTH_URL", "REST_URL", "SUPABASE_URL"):
    value = os.getenv(key, "")
    if "wakmxrgmercaauqstrvj" in value or "supabase.co" in value:
        raise SystemExit("production endpoint rejected")
print("preflight passed")
