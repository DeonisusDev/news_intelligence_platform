"""Generates a throwaway .env for the CI compose smoke test - real values for the secrets
docker-compose.yml requires containers to actually start with (Fernet key, API/JWT secrets),
dummy values for external API keys (never called during a startup-only smoke test, since no
DAG run is triggered - see the compose-smoke job in .github/workflows/ci.yml).
"""

from __future__ import annotations

import base64
import os
import re
import secrets

_DUMMY_VALUES = {
    "AIRFLOW_FERNET_KEY": lambda: base64.urlsafe_b64encode(os.urandom(32)).decode(),
    "AIRFLOW_API_SECRET_KEY": lambda: secrets.token_hex(32),
    "AIRFLOW_JWT_SECRET": lambda: secrets.token_hex(32),
    "NEWSAPI_API_KEY": lambda: "ci-dummy-key",
    "GNEWS_API_KEY": lambda: "ci-dummy-key",
    "OPENROUTER_API_KEY": lambda: "ci-dummy-key",
}


def main() -> None:
    with open(".env.example") as f:
        content = f.read()

    for key, generator in _DUMMY_VALUES.items():
        content = re.sub(rf"^{key}=.*$", f"{key}={generator()}", content, flags=re.MULTILINE)

    with open(".env", "w") as f:
        f.write(content)


if __name__ == "__main__":
    main()
