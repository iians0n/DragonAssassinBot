"""Bounty data model."""

from dataclasses import dataclass, asdict
from typing import Optional
import time
import uuid


@dataclass
class Bounty:
    id: str
    creator_id: int
    target_id: int
    points: int
    created_at: float
    expires_at: float
    claimed: bool = False
    claimed_by: int = 0  # 0 means not claimed

    def is_expired(self) -> bool:
        return time.time() >= self.expires_at and not self.claimed

    def is_active(self) -> bool:
        return not self.claimed and not self.is_expired()

    def claim(self, killer_id: int):
        self.claimed = True
        self.claimed_by = killer_id

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Bounty":
        return cls(**data)

    @classmethod
    def create(cls, creator_id: int, target_id: int, points: int, duration: int = 86400) -> "Bounty":
        now = time.time()
        return cls(
            id=str(uuid.uuid4()),
            creator_id=creator_id,
            target_id=target_id,
            points=points,
            created_at=now,
            expires_at=now + duration,
        )
