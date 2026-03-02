"""Player data model."""
# hi weibz

from dataclasses import dataclass, field, asdict
import time


@dataclass
class Player:
    user_id: int
    username: str
    name: str
    gender: str               # "M" or "F"
    team: int                 # 1-4
    status: str = "alive"     # "alive" | "cooldown" | "eliminated"
    cooldown_until: float = 0.0
    kills_normal: int = 0
    kills_stealth: int = 0
    deaths: int = 0
    points: int = 0
    bounties_placed: int = 0
    bounties_collected: int = 0
    registered_at: float = field(default_factory=time.time)

    @property
    def kills_total(self) -> int:
        return self.kills_normal + self.kills_stealth

    @property
    def kda(self) -> float:
        return self.kills_total / max(1, self.deaths)

    def is_alive(self) -> bool:
        """Check if player is alive (auto-restores from cooldown if expired)."""
        if self.status == "cooldown" and time.time() >= self.cooldown_until:
            self.status = "alive"
            self.cooldown_until = 0.0
        return self.status == "alive"

    def is_active(self) -> bool:
        """Check if player can perform actions (alive, not in cooldown)."""
        if self.status == "cooldown" and time.time() >= self.cooldown_until:
            self.status = "alive"
            self.cooldown_until = 0.0
        return self.status == "alive"

    def can_be_killed(self) -> bool:
        """Players can be killed if alive OR in cooldown (vulnerable)."""
        if self.status == "cooldown" and time.time() >= self.cooldown_until:
            self.status = "alive"
            self.cooldown_until = 0.0
        return self.status in ("alive", "cooldown")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Player":
        return cls(**data)
