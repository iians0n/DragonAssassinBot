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
    target_was_president: bool = False  # Track if target was president at time of kill

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "KillEvent":
        # Filter to only known fields for backward compatibility
        import dataclasses
        valid_fields = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    @classmethod
    def create(cls, killer_id: int, target_id: int, kill_type: str,
               witness: str = "", photo_file_id: str = "",
               points_awarded: int = 0, bounty_claimed: int = 0,
               timestamp: float = 0.0,
               target_was_president: bool = False) -> "KillEvent":
        return cls(
            id=str(uuid.uuid4()),
            killer_id=killer_id,
            target_id=target_id,
            kill_type=kill_type,
            timestamp=timestamp or time.time(),
            witness=witness,
            photo_file_id=photo_file_id,
            points_awarded=points_awarded,
            bounty_claimed=bounty_claimed,
            target_was_president=target_was_president,
        )
