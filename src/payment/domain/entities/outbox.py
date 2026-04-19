from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

@dataclass
class OutboxMessage:
    id: UUID = field(default_factory=uuid4)
    event_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    processed: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
