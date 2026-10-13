
import os
from pathlib import Path

# Project root: Expense_Tracker_FullStack/
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


def load_project_env(path: Path) -> None:
    """Load project environment variables without overwriting existing ones."""
    if not path.is_file():
        return

    try:
        from dotenv import load_dotenv
        load_dotenv(path, override=False)
        return
    except ImportError:
        pass

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]

        if key:
            os.environ.setdefault(key, value)


load_project_env(ENV_FILE)

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 30

SECRET_KEY = os.getenv("SECRET_KEY", "")
REFRESH_SECRET_KEY = os.getenv("REFRESH_SECRET_KEY", "")

if not SECRET_KEY or not REFRESH_SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY and REFRESH_SECRET_KEY must be configured in the project .env file."
    )
