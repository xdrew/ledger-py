"""``ledger-migrate`` — apply the event-store schema to the configured database."""

# asyncpg's connect() surface is partially typed; relax at the driver boundary.
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

import asyncio
import logging

import asyncpg

from ledger.config.settings import get_settings
from ledger.eventstore.schema import SCHEMA_SQL

_log = logging.getLogger(__name__)


async def _apply() -> None:
    settings = get_settings()
    conn: asyncpg.Connection = await asyncpg.connect(settings.database_url)
    try:
        await conn.execute(SCHEMA_SQL)
        _log.info("schema applied")
    finally:
        await conn.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_apply())


if __name__ == "__main__":
    main()
