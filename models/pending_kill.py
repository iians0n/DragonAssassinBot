"""Pending kill data model — kills awaiting confirmation or dispute."""

from dataclasses import dataclass, asdict
import time
import uuid

from config import KILL_DISPUTE_WINDOW


@dataclass
class PendingKill:
    id: str
    killer_id: int
    target_id: int
    kill_type: str            # "normal" | "stealth"
    timestamp: float
    expires_at: float
    witness: str = ""
    photo_file_id: str = ""
    status: str = "pending"   # "pending" | "confirmed" | "disputed" | "rejected"
    disputed_reason: str = ""
    resolved_by: int = 0      # admin user_id who resolved (0 = N/A)
    resolution_type: str = "" # e.g. "confirmed by target", "auto-confirmed", "approved by admin", "rejected by admin"

    def is_expired(self) -> bool:
        """Check if the dispute window has passed."""
        return time.time() >= self.expires_at and self.status == "pending"

    def is_active(self) -> bool:
        """Check if this pending kill is still awaiting action."""
        return self.status == "pending"

    def is_unresolved(self) -> bool:
        """Check if this kill is still awaiting resolution (pending OR disputed)."""
        return self.status in ("pending", "disputed")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PendingKill":
        return cls(**data)

    @classmethod
    def create(cls, killer_id: int, target_id: int, kill_type: str,
               witness: str = "", photo_file_id: str = "") -> "PendingKill":
        now = time.time()
        return cls(
            id=str(uuid.uuid4()),
            killer_id=killer_id,
            target_id=target_id,
            kill_type=kill_type,
            timestamp=now,
            expires_at=now + KILL_DISPUTE_WINDOW,
            witness=witness,
            photo_file_id=photo_file_id,
        )
