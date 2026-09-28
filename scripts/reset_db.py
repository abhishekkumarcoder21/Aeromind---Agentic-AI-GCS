#!/usr/bin/env python3
"""Reset database — Drops all tables and recreates them.

Usage:
    python -m scripts.reset_db
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main() -> None:
    from apps.backend.database import engine, Base
    from apps.backend import models  # noqa: F401 — registers models

    print("AeroMind — Database Reset")
    print("=" * 40)

    async with engine.begin() as conn:
        print("Dropping all tables...")
        await conn.run_sync(Base.metadata.drop_all)
        print("Creating all tables...")
        await conn.run_sync(Base.metadata.create_all)

    print("Database reset complete ✓")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
