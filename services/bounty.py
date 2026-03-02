"""Bounty lifecycle service."""

from typing import Optional, Tuple, List

from models.bounty import Bounty
from storage.json_store import store
from services.registration import get_player, save_player
from config import MIN_BOUNTY, BOUNTY_DURATION


def place_bounty(creator_id: int, target_id: int, points: int) -> Tuple[bool, str, Optional[Bounty]]:
    """
    Place a bounty on a target player.
    Returns (success, message, bounty_or_none).
    """
    if points < MIN_BOUNTY:
        return False, f"❌ Minimum bounty is {MIN_BOUNTY} point(s).", None

    creator = get_player(creator_id)
    if not creator:
        return False, "❌ You're not registered.", None

    if creator.points < points:
        return False, f"❌ Not enough points! You have {creator.points} pts.", None

    target = get_player(target_id)
    if not target:
        return False, "❌ Target is not registered.", None

    if creator_id == target_id:
        return False, "❌ You can't put a bounty on yourself!", None

    # Check for duplicate active bounty
    bounties = store.load_bounties()
    for b_data in bounties:
        b = Bounty.from_dict(b_data)
        if b.creator_id == creator_id and b.target_id == target_id and b.is_active():
            return False, "❌ You already have an active bounty on this player.", None

    # Deduct points from creator
    creator.points -= points
    creator.bounties_placed += points
    save_player(creator)

    # Create bounty
    bounty = Bounty.create(creator_id, target_id, points, BOUNTY_DURATION)
    bounties.append(bounty.to_dict())
    store.save_bounties(bounties)

    return True, "", bounty


def get_active_bounties() -> List[Bounty]:
    """Get all active (not claimed, not expired) bounties."""
    bounties = store.load_bounties()
    return [Bounty.from_dict(b) for b in bounties if Bounty.from_dict(b).is_active()]


def expire_bounties() -> List[Tuple[Bounty, int]]:
    """
    Expire all overdue bounties and refund points to creators.
    Returns list of (expired_bounty, refunded_points).
    """
    bounties = store.load_bounties()
    expired_list = []
    changed = False

    for b_data in bounties:
        b = Bounty.from_dict(b_data)
        if not b.claimed and b.is_expired():
            # Refund points to creator
            creator = get_player(b.creator_id)
            if creator:
                creator.points += b.points
                creator.bounties_placed -= b.points
                save_player(creator)
                expired_list.append((b, b.points))

            # Mark as claimed (so it won't be processed again)
            b_data["claimed"] = True
            b_data["claimed_by"] = 0  # 0 = expired, not claimed by anyone
            changed = True

    if changed:
        store.save_bounties(bounties)

    return expired_list
