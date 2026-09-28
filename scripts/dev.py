#!/usr/bin/env python3
"""Dev startup script — Runs backend locally without Docker.

Usage:
    python -m scripts.dev

Requires:
    - PostgreSQL running on localhost:5432
    - Redis running on localhost:6379
    - Python dependencies installed
"""

import os
import subprocess
import sys


def main() -> None:
    print("AeroMind — Local Dev Server")
    print("=" * 40)

    # Set default env vars
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://aeromind:aeromind@localhost:5432/aeromind")
    os.environ.setdefault("DATABASE_URL_SYNC", "postgresql://aeromind:aeromind@localhost:5432/aeromind")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
    os.environ.setdefault("LOG_LEVEL", "INFO")
    os.environ.setdefault("INITIAL_UAV_COUNT", "8")

    print("Starting uvicorn with hot-reload...")
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "apps.backend.main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload",
        "--reload-dir", "apps",
        "--reload-dir", "packages",
        "--reload-dir", "services",
    ])


if __name__ == "__main__":
    main()
