"""Database schema for the event store and its support tables.

Kept as idempotent ``CREATE ... IF NOT EXISTS`` so it can be applied at startup
or via the ``ledger-migrate`` command. The ``UNIQUE(stream_type, stream_id,
version)`` constraint is the optimistic-concurrency guard.
"""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS events (
    global_position BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id        UUID        NOT NULL,
    stream_type     TEXT        NOT NULL,
    stream_id       UUID        NOT NULL,
    version         INTEGER     NOT NULL,
    event_type      TEXT        NOT NULL,
    schema_version  INTEGER     NOT NULL,
    payload         JSONB       NOT NULL,
    metadata        JSONB       NOT NULL DEFAULT '{}'::jsonb,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (stream_type, stream_id, version)
);

CREATE INDEX IF NOT EXISTS events_stream_idx
    ON events (stream_type, stream_id, version);

CREATE TABLE IF NOT EXISTS projection_checkpoints (
    name     TEXT   PRIMARY KEY,
    position BIGINT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS relay_checkpoints (
    name     TEXT   PRIMARY KEY,
    position BIGINT NOT NULL DEFAULT 0
);
"""
