"""Game state model."""

from dataclasses import dataclass, field, asdict
from typing import List
import time
from config import GAME_DURATION_DAYS, DAY_START_HOUR, DAY_END_HOUR, COOLDOWN_BALL, COOLDOWN_STEALTH


@dataclass
class GameState:
    status: str = "pending"           # "pending" | "active" | "paused" | "completed"
    start_time: float = 0.0
    end_time: float = 0.0
    day_start_hour: int = DAY_START_HOUR
    day_end_hour: int = DAY_END_HOUR
    cooldown_ball_secs: int = COOLDOWN_BALL
    cooldown_stealth_secs: int = COOLDOWN_STEALTH
    group_chat_id: int = 0
    group_topic_id: int = 0             # Forum/topic thread ID (0 = no topic)
    admin_ids: List = field(default_factory=list)
    team_chat_ids: dict = field(default_factory=dict)  # {"1": chat_id, ...} for team GCs

    def is_active(self) -> bool:
        return self.status == "active"

    def start(self):
        self.status = "active"
        self.start_time = time.time()
        self.end_time = self.start_time + (GAME_DURATION_DAYS * 86400)

    def end(self):
        self.status = "completed"
        self.end_time = time.time()

    def pause(self):
        self.status = "paused" if self.status == "active" else "active"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "GameState":
        # Filter to only known fields for backward compatibility
        import dataclasses
        valid_fields = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)
