"""Base type for domain events.

Events are immutable pydantic models — which gives free, schema-checked JSON
(de)serialization shared by the event store *and* the Temporal data converter.
Concrete events live in each bounded context and simply subclass this.
"""

from pydantic import BaseModel, ConfigDict


class DomainEvent(BaseModel):
    """Immutable fact that has already happened. Named in past tense."""

    model_config = ConfigDict(frozen=True)
