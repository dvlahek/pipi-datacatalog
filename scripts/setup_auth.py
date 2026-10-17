from __future__ import annotations

import getpass
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.security.auth import password_hash


def main() -> int:
    username = input("Admin username: ").strip()
    if not username:
        print("Username must not be empty.")
        return 2

    password = getpass.getpass("Admin password: ")
    confirmation = getpass.getpass("Repeat password: ")
    if password != confirmation:
        print("Passwords do not match.")
        return 2
    if len(password) < 12:
        print("Use a password with at least 12 characters.")
        return 2

    print("\nAdd these lines to your local .env. Do not commit them:\n")
    print("AUTH_ENABLED=true")
    print(f"AUTH_USERNAME={username}")
    print(f"AUTH_PASSWORD_HASH={password_hash(password)}")
    print(f"AUTH_JWT_SECRET={secrets.token_urlsafe(48)}")
    print("AUTH_TOKEN_TTL_MINUTES=480")
    print("AUTH_RATE_LIMIT_ATTEMPTS=5")
    print("AUTH_RATE_LIMIT_WINDOW_SECONDS=900")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
