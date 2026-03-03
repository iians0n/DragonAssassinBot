"""Pending kill service — create, confirm, dispute, and resolve pending kills."""

import logging
from typing import Tuple, Optional, List

from models.pending_kill import PendingKill
from models.player import Player
from services.combat import execute_kill
from services.registration import get_player
from storage.json_store import store

logger = logging.getLogger(__name__)


def create_pending_kill(killer: Player, target: Player, kill_type: str,
                        witness: str = "", photo_file_id: str = "") -> PendingKill:
    """Create a new pending kill and save it."""
    pending = PendingKill.create(
        killer_id=killer.user_id,
        target_id=target.user_id,
        kill_type=kill_type,
        witness=witness,
        photo_file_id=photo_file_id,
    )

    pending_kills = store.load_pending_kills()
    pending_kills.append(pending.to_dict())
    store.save_pending_kills(pending_kills)

    return pending


def get_pending_kill(pending_kill_id: str) -> Optional[PendingKill]:
    """Look up a pending kill by ID."""
    pending_kills = store.load_pending_kills()
    for pk_data in pending_kills:
        if pk_data["id"] == pending_kill_id:
            return PendingKill.from_dict(pk_data)
    return None


def has_pending_kill_against(target_id: int) -> bool:
    """Check if there's already an active pending kill against this target."""
    pending_kills = store.load_pending_kills()
    for pk_data in pending_kills:
        pk = PendingKill.from_dict(pk_data)
        if pk.target_id == target_id and pk.is_active():
            return True
    return False


def confirm_pending_kill(pending_kill_id: str) -> Tuple[Optional[dict], int, list]:
    """
    Confirm a pending kill — execute it and update stats.
    Returns (kill_event_dict, bounty_bonus, new_achievements) or (None, 0, []) if not found/invalid.
    """
    pending_kills = store.load_pending_kills()
    target_data = None

    for pk_data in pending_kills:
        if pk_data["id"] == pending_kill_id:
            target_data = pk_data
            break

    if not target_data or target_data["status"] != "pending":
        return None, 0, []

    pk = PendingKill.from_dict(target_data)

    # Get fresh player data
    killer = get_player(pk.killer_id)
    target = get_player(pk.target_id)

    if not killer or not target:
        logger.warning(f"Pending kill {pk.id}: killer or target not found")
        target_data["status"] = "rejected"
        store.save_pending_kills(pending_kills)
        return None, 0, []

    kill_event, bounty_bonus, new_achievements = execute_kill(
        killer, target, pk.kill_type,
        witness=pk.witness,
        photo_file_id=pk.photo_file_id,
    )

    # Update pending kill status
    target_data["status"] = "confirmed"
    store.save_pending_kills(pending_kills)

    return kill_event.to_dict(), bounty_bonus, new_achievements


def dispute_pending_kill(pending_kill_id: str, reason: str = "") -> Optional[PendingKill]:
    """
    Mark a pending kill as disputed.
    Returns the updated PendingKill or None if not found.
    """
    pending_kills = store.load_pending_kills()

    for pk_data in pending_kills:
        if pk_data["id"] == pending_kill_id:
            if pk_data["status"] != "pending":
                return None
            pk_data["status"] = "disputed"
            pk_data["disputed_reason"] = reason
            store.save_pending_kills(pending_kills)
            return PendingKill.from_dict(pk_data)

    return None


def resolve_disputed_kill(pending_kill_id: str, approved: bool,
                          admin_id: int) -> Tuple[Optional[dict], int, Optional[PendingKill], list]:
    """
    Admin resolves a disputed kill.
    Returns (kill_event_dict, bounty_bonus, pending_kill, new_achievements) — kill_event is None if rejected.
    """
    pending_kills = store.load_pending_kills()

    for pk_data in pending_kills:
        if pk_data["id"] == pending_kill_id:
            if pk_data["status"] != "disputed":
                return None, 0, None, []

            pk_data["resolved_by"] = admin_id

            if approved:
                pk_data["status"] = "confirmed"
                store.save_pending_kills(pending_kills)
                # Now execute the kill
                pk = PendingKill.from_dict(pk_data)
                killer = get_player(pk.killer_id)
                target = get_player(pk.target_id)
                if not killer or not target:
                    return None, 0, pk, []
                kill_event, bounty_bonus, new_achievements = execute_kill(
                    killer, target, pk.kill_type,
                    witness=pk.witness,
                    photo_file_id=pk.photo_file_id,
                )
                return kill_event.to_dict(), bounty_bonus, pk, new_achievements
            else:
                pk_data["status"] = "rejected"
                store.save_pending_kills(pending_kills)
                return None, 0, PendingKill.from_dict(pk_data), []

    return None, 0, None, []


def get_expired_pending_kills() -> List[PendingKill]:
    """Return all pending kills that have passed their dispute window."""
    pending_kills = store.load_pending_kills()
    expired = []
    for pk_data in pending_kills:
        pk = PendingKill.from_dict(pk_data)
        if pk.is_expired():
            expired.append(pk)
    return expired
