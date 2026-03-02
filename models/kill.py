"""Kill event data model."""

from dataclasses import dataclass, asdict
import time
import uuid


@dataclass
class KillEvent:
    id: str
    killer_id: int
    target_id: int
    kill_type: str            # "normal" | "stealth"
    timestamp: float
    witness: str = ""
    photo_file_id: str = ""
    points_awarded: int = 0
    bounty_claimed: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "KillEvent":
        return cls(**data)

    @classmethod
    def create(cls, killer_id: int, target_id: int, kill_type: str,
               witness: str = "", photo_file_id: str = "",
               points_awarded: int = 0, bounty_claimed: int = 0) -> "KillEvent":
        return cls(
            id=str(uuid.uuid4()),
            killer_id=killer_id,
            target_id=target_id,
            kill_type=kill_type,
            timestamp=time.time(),
            witness=witness,
            photo_file_id=photo_file_id,
            points_awarded=points_awarded,
            bounty_claimed=bounty_claimed,
        )
