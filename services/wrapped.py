"""Assassins Wrapped — Spotify-Wrapped-style end-of-game cards.

Generates personalised image cards for every player with their stats
and a unique superlative award.
"""

import io
import os
import random
from typing import Dict, List, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter

from models.player import Player
from services.registration import get_all_players, get_team_players
from utils.formatting import TEAM_NAMES, TEAM_EMOJIS

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FONT_DIR = os.path.join(_BASE_DIR, "assets", "fonts")
_FONT_BOLD = os.path.join(_FONT_DIR, "Inter-Bold.ttf")
_FONT_REGULAR = os.path.join(_FONT_DIR, "Inter-Regular.ttf")

# ---------------------------------------------------------------------------
# Card dimensions & colours
# ---------------------------------------------------------------------------
CARD_W, CARD_H = 800, 1200
BG_TOP = (15, 5, 30)          # deep purple-black
BG_BOTTOM = (5, 5, 20)        # near-black
ACCENT_CYAN = (0, 230, 255)
ACCENT_RED = (255, 50, 80)
ACCENT_GOLD = (255, 210, 50)
TEXT_WHITE = (255, 255, 255)
TEXT_DIM = (180, 180, 200)
BORDER_GLOW = (0, 200, 240, 60)

# Team accent colours used for the card's side glow
TEAM_ACCENTS = {
    0: (180, 180, 180),
    1: (255, 60, 60),
    2: (60, 120, 255),
    3: (50, 210, 80),
    4: (255, 220, 40),
}


# ===================================================================
# SUPERLATIVE CALCULATION
# ===================================================================

# (emoji, title, description template)
_TIER1 = [
    ("mvp",         "🏆", "MVP",             "Dominated the battlefield."),
    ("sharpshooter","🎯", "Sharpshooter",    "Deadly precision, rarely missed."),
    ("shadow",      "🥷", "Shadow Blade",     "You never saw them coming."),
    ("rampage",     "🔥", "Rampage King",     "An unstoppable kill streak."),
    ("bounty",      "💰", "Bounty Hunter",    "Claimed the most bounties."),
]

_TIER2 = [
    ("tank",        "🛡️", "The Tank",         "Took one for the team. Repeatedly."),
    ("immortal",    "💚", "Immortal",          "Barely scratched the whole week."),
    ("phantom",     "👻", "The Phantom",       "Legends say they're still hiding."),
    ("sacrifice",   "⚰️", "The Sacrifice",    "Fell so others could rise."),
    ("og",          "🏛️", "OG Assassin",      "First in. Set the tone."),
    ("late",        "⏰", "Fashionably Late",  "Better late than never."),
    ("social",      "📢", "The Social One",    "Hired the most hitmen."),
    ("badges",      "🏅", "Badge Collector",   "Caught 'em all."),
    ("carry",       "💪", "Team Carry",        "Put the team on their back."),
    ("ballonly",    "🏀", "Ball Only",         "Old-school assassin, no stealth."),
]

# Funny quotes / flavour text based on the award
_QUOTES = {
    "MVP":              "With great power comes... a lot of people trying to kill you.",
    "Sharpshooter":     "They say 100% of shots not taken are missed. You took 'em all.",
    "Shadow Blade":      "Like a ninja, but with more Telegram notifications.",
    "Rampage King":      "Can't stop, won't stop. Seriously, someone stop them.",
    "Bounty Hunter":    "It's not about the money. Wait, yes it is.",
    "The Tank":          "Built different. Mostly out of scar tissue.",
    "Immortal":          "Health bar? Never heard of her.",
    "The Phantom":       "Are we sure they even joined the group chat?",
    "The Sacrifice":     "Your contribution to the kill stats was... noted.",
    "OG Assassin":       "They were here before it was cool. And before it was deadly.",
    "Fashionably Late":  "Arrived just in time to see the leaderboard from the bottom.",
    "The Social One":    "Managed to die while typing a message. Probably.",
    "Badge Collector":   "Achievements > Actually winning.",
    "Team Carry":        "My back hurts from carrying this entire team.",
    "Ball Only":         "Who needs stealth when you have a 100% success rate of being seen?",
    "Wild": [
        "Intelligence Agent? More like Professional Lurker.",
        "Slow and steady wins the... oh wait, everyone else is dead.",
        "Legend says if you stay still long enough, you become part of the background.",
        "The Pacifist: Because weapons are too heavy anyway.",
        "The Tea Sipper: ☕ This is fine.",
    ]
}


_WILD_CARDS = [
    ("🕵️", "Intelligence Agent", "Gathered intel. Never struck."),
    ("🐢", "The Turtle",         "Survived by hiding."),
    ("😴", "The Sleeper Agent",  "Activated... never."),
    ("🧊", "Ice Cold",           "Coolest player. Literally did nothing."),
    ("🦎", "The Chameleon",      "Blended in so well, nobody noticed."),
    ("🫖", "The Tea Sipper",     "Watched the chaos from safety."),
    ("🌿", "The Pacifist",       "Believed in non-violence."),
    ("🎭", "The Understudy",     "Supporting cast, but essential."),
]


def calculate_superlatives(players: List[Player]) -> Dict[int, Tuple[str, str, str, str]]:
    """
    Assign exactly one superlative to every player.

    Returns {player.user_id: (emoji, title, description, funny_quote)}.
    """
    if not players:
        return {}

    awarded: Dict[int, Tuple[str, str, str, str]] = {}
    remaining = {p.user_id for p in players}

    def _award(uid: int, emoji: str, title: str, desc: str):
        if uid in remaining:
            quote = _QUOTES.get(title, "GG, see you next season!")
            awarded[uid] = (emoji, title, desc, quote)
            remaining.discard(uid)

    # ── Tier 1 ────────────────────────────────────────────────
    # MVP — highest points
    best = max(players, key=lambda p: p.points)
    if best.points > 0:
        _award(best.user_id, "🏆", "MVP", "Dominated the battlefield.")

    # Sharpshooter — best KD (min 3 kills)
    eligible = [p for p in players if p.kills_total >= 3 and p.user_id in remaining]
    if eligible:
        best = max(eligible, key=lambda p: p.kda)
        _award(best.user_id, "🎯", "Sharpshooter", "Deadly precision, rarely missed.")

    # Shadow Blade — most stealth kills
    eligible = [p for p in players if p.kills_stealth > 0 and p.user_id in remaining]
    if eligible:
        best = max(eligible, key=lambda p: p.kills_stealth)
        _award(best.user_id, "🥷", "Shadow Blade", "You never saw them coming.")

    # Rampage King — highest streak
    eligible = [p for p in players if p.best_streak >= 3 and p.user_id in remaining]
    if eligible:
        best = max(eligible, key=lambda p: p.best_streak)
        _award(best.user_id, "🔥", "Rampage King", "An unstoppable kill streak.")

    # Bounty Hunter — most bounties collected
    eligible = [p for p in players if p.bounties_collected > 0 and p.user_id in remaining]
    if eligible:
        best = max(eligible, key=lambda p: p.bounties_collected)
        _award(best.user_id, "💰", "Bounty Hunter", "Claimed the most bounties.")

    # ── Tier 2 ────────────────────────────────────────────────
    # Tank — most deaths but still had kills
    eligible = [p for p in players if p.deaths > 0 and p.kills_total > 0 and p.user_id in remaining]
    if eligible:
        best = max(eligible, key=lambda p: p.deaths)
        _award(best.user_id, "🛡️", "The Tank", "Took one for the team. Repeatedly.")

    # Immortal — fewest deaths (min 1 kill)
    eligible = [p for p in players if p.kills_total >= 1 and p.user_id in remaining]
    if eligible:
        best = min(eligible, key=lambda p: p.deaths)
        _award(best.user_id, "💚", "Immortal", "Barely scratched the whole week.")

    # Phantom — 0 kills AND 0 deaths
    for p in players:
        if p.user_id in remaining and p.kills_total == 0 and p.deaths == 0:
            _award(p.user_id, "👻", "The Phantom", "Legends say they're still hiding.")
            break  # only award one

    # Sacrifice — most deaths with 0 kills
    eligible = [p for p in players if p.deaths > 0 and p.kills_total == 0 and p.user_id in remaining]
    if eligible:
        best = max(eligible, key=lambda p: p.deaths)
        _award(best.user_id, "⚰️", "The Sacrifice", "Fell so others could rise.")

    # OG — first registered
    eligible = [p for p in players if p.user_id in remaining]
    if eligible:
        best = min(eligible, key=lambda p: p.registered_at)
        _award(best.user_id, "🏛️", "OG Assassin", "First in. Set the tone.")

    # Fashionably Late — last registered
    eligible = [p for p in players if p.user_id in remaining]
    if eligible:
        best = max(eligible, key=lambda p: p.registered_at)
        _award(best.user_id, "⏰", "Fashionably Late", "Better late than never.")

    # Social One — most bounties placed
    eligible = [p for p in players if p.bounties_placed > 0 and p.user_id in remaining]
    if eligible:
        best = max(eligible, key=lambda p: p.bounties_placed)
        _award(best.user_id, "📢", "The Social One", "Hired the most hitmen.")

    # Badge Collector — most achievements
    eligible = [p for p in players if len(p.achievements) > 0 and p.user_id in remaining]
    if eligible:
        best = max(eligible, key=lambda p: len(p.achievements))
        _award(best.user_id, "🏅", "Badge Collector", "Caught 'em all.")

    # Team Carry — highest % of team points
    eligible = [p for p in players if p.team != 0 and p.points > 0 and p.user_id in remaining]
    if eligible:
        def _carry_pct(p):
            team_pts = sum(t.points for t in players if t.team == p.team)
            return p.points / max(1, team_pts)
        best = max(eligible, key=_carry_pct)
        _award(best.user_id, "💪", "Team Carry", "Put the team on their back.")

    # Ball Only — kills but zero stealth
    for p in players:
        if p.user_id in remaining and p.kills_normal > 0 and p.kills_stealth == 0:
            _award(p.user_id, "🏀", "Ball Only", "Old-school assassin, no stealth needed.")
            break

    # ── Tier 3: Wild Cards for everyone else ──────────────────
    wild_pool = list(_WILD_CARDS)
    random.shuffle(wild_pool)
    for uid in list(remaining):
        if not wild_pool:
            wild_pool = list(_WILD_CARDS)
            random.shuffle(wild_pool)
        emoji, title, desc = wild_pool.pop()
        quote = random.choice(_QUOTES["Wild"])
        awarded[uid] = (emoji, title, desc, quote)

    return awarded


# ---------------------------------------------------------------------------
# Card dimensions & colours (for Dragon Assassins background)
# ---------------------------------------------------------------------------
CARD_BG_PATH = os.path.join(_BASE_DIR, "assets", "wrapped_bg.png")

# Box area where text should live (shifted left to avoid the profile badge)
BOX_X1, BOX_Y1 = 150, 310
BOX_X2, BOX_Y2 = 930, 1150
BOX_W = BOX_X2 - BOX_X1
BOX_CENTER_X = 480  # Shifted left for the badge on the right
BOX_H = BOX_Y2 - BOX_Y1

# Ink-on-parchment style
TEXT_INK = (20, 10, 5)        # Solid mahogany black
TEXT_ACCENT = (140, 40, 5)    # Burnt sienna
LABEL_DIM = (80, 70, 60)      # Faded brown
ACCENT_GOLD_INKEY = (160, 110, 10)


# ===================================================================
# IMAGE CARD GENERATION (Pillow)
# ===================================================================

def _load_font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    """Load Inter font, fall back to built-in if missing."""
    path = _FONT_BOLD if bold else _FONT_REGULAR
    try:
        return ImageFont.truetype(path, size)
    except (IOError, OSError):
        try:
            return ImageFont.truetype("Arial", size)
        except (IOError, OSError):
            return ImageFont.load_default()


def _draw_rich_text(img: Image.Image, text: str, x: int, y: int, font: ImageFont.FreeTypeFont, 
                   fill: tuple = (255, 255, 255), shadow: tuple = (0, 0, 0, 180)):
    """Draw text with a deep burnt-oak border and drop shadow for a 'fiery' feel."""
    draw = ImageDraw.Draw(img)
    # Deep mahogany border
    border_col = (40, 15, 5, 220)
    for dx, dy in [(-2, -2), (2, -2), (-2, 2), (2, 2), (0, -3), (0, 3), (-3, 0), (3, 0)]:
        draw.text((x + dx, y + dy), text, font=font, fill=border_col)
    
    # Subtle drop shadow
    draw.text((x + 5, y + 5), text, font=font, fill=(0, 0, 0, 100))

    # Main text
    draw.text((x, y), text, font=font, fill=fill)


def generate_wrapped_card(player: Player, superlative: Tuple[str, str, str, str]) -> bytes:
    """
    Render a single Assassins Wrapped card for *player* using the custom image.

    Returns PNG image bytes.
    """
    emoji, title, description, quote = superlative

    # — Load base image ───────────────────────────────────────
    try:
        img = Image.open(CARD_BG_PATH).convert("RGBA")
    except Exception:
        img = Image.new("RGBA", (1080, 1350), (40, 30, 20))
    
    draw = ImageDraw.Draw(img)
    card_w, card_h = img.size

    # — Fonts ─────────────────────────────────────────────────
    font_name = _load_font(True, 85)
    font_stat_value = _load_font(True, 64)
    font_stat_label = _load_font(False, 32)
    font_award_title = _load_font(True, 58)
    font_award_desc = _load_font(False, 32)
    font_footer = _load_font(False, 24)
    font_team = _load_font(True, 32)
    font_quote = _load_font(False, 28)

    y = BOX_Y1 + 10  # Start inside box

    # — Team label ────────────────────────────────────────────
    team_name = TEAM_NAMES.get(player.team, f"Team {player.team}").upper()
    team_emoji = TEAM_EMOJIS.get(player.team, "")
    team_text = f"{team_emoji} {team_name}"
    bbox = draw.textbbox((0, 0), team_text, font=font_team)
    tw = bbox[2] - bbox[0]
    draw.text((BOX_CENTER_X - (tw // 2), y), team_text, fill=TEXT_ACCENT, font=font_team)
    y += 50

    # — Player name (RICH TEXT) ───────────────────────────────
    name_display = player.name.upper()
    bbox = draw.textbbox((0, 0), name_display, font=font_name)
    tw = bbox[2] - bbox[0]
    if tw > BOX_W - 120:
        font_name = _load_font(True, 64)
        bbox = draw.textbbox((0, 0), name_display, font=font_name)
        tw = bbox[2] - bbox[0]
    
    _draw_rich_text(img, name_display, BOX_CENTER_X - (tw // 2), y, font_name, fill=TEXT_INK)
    y += 105

    # Divider line
    draw = ImageDraw.Draw(img)
    line_w = 460
    draw.line([(BOX_CENTER_X - line_w // 2, y), (BOX_CENTER_X + line_w // 2, y)], fill=(*LABEL_DIM, 80), width=2)
    y += 45

    # — Stats block (Tightened further) ───────────────────────
    stats = [
        (str(player.kills_total), "KILLS",          TEXT_ACCENT),
        (str(player.deaths),      "DEATHS",         LABEL_DIM),
        (f"{player.kda:.1f}",     "K/D RATIO",      TEXT_INK),
        (str(player.points),      "TOTAL POINTS",   ACCENT_GOLD_INKEY),
    ]
    if player.best_streak >= 3:
        stats.append((str(player.best_streak), "BEST STREAK", TEXT_ACCENT))

    for value, label, colour in stats:
        bbox_v = draw.textbbox((0, 0), value, font=font_stat_value)
        vw = bbox_v[2] - bbox_v[0]
        bbox_l = draw.textbbox((0, 0), f"  {label}", font=font_stat_label)
        lw = bbox_l[2] - bbox_l[0]
        
        tw = vw + lw
        x_start = BOX_CENTER_X - (tw // 2)
        draw.text((x_start, y), value, fill=colour, font=font_stat_value)
        draw.text((x_start + vw, y + 20), f"  {label}", fill=LABEL_DIM, font=font_stat_label)
        y += 66

    y += 25
    # — Award section ─────────────────────────────────────────
    draw = ImageDraw.Draw(img)
    draw.line([(BOX_CENTER_X - line_w // 2, y), (BOX_CENTER_X + line_w // 2, y)], fill=(*LABEL_DIM, 60), width=1)
    y += 30

    award_line = f"{emoji}  {title}".upper()
    bbox = draw.textbbox((0, 0), award_line, font=font_award_title)
    tw = bbox[2] - bbox[0]
    if tw > BOX_W - 100:
        font_award_title = _load_font(True, 42)
        bbox = draw.textbbox((0, 0), award_line, font=font_award_title)
        tw = bbox[2] - bbox[0]

    _draw_rich_text(img, award_line, BOX_CENTER_X - (tw // 2), y, font_award_title, fill=TEXT_ACCENT)
    y += 65

    # Award description
    draw = ImageDraw.Draw(img)
    desc_line = f'"{description}"'
    bbox = draw.textbbox((0, 0), desc_line, font=font_award_desc)
    tw = bbox[2] - bbox[0]
    draw.text((BOX_CENTER_X - (tw // 2), y), desc_line, fill=TEXT_INK, font=font_award_desc)
    y += 45

    # — Funny Quote ───────────────────────────────────────────
    draw = ImageDraw.Draw(img)
    quote_line = f"❝ {quote} ❞"
    bbox = draw.textbbox((0, 0), quote_line, font=font_quote)
    tw = bbox[2] - bbox[0]
    draw.text((BOX_CENTER_X - (tw // 2), y), quote_line, fill=TEXT_ACCENT, font=font_quote)
    y += 60

    # — Footer stats breakdown ────────────────────────────────
    if player.kills_total > 0:
        breakdown = f"{player.kills_normal} normal kills  ·  {player.kills_stealth} stealth"
        bbox = draw.textbbox((0, 0), breakdown, font=font_footer)
        draw.text((BOX_CENTER_X - (bbox[2] - bbox[0]) // 2, y), breakdown, fill=LABEL_DIM, font=font_footer)
        y += 30

    if player.achievements:
        ach_txt = f"{len(player.achievements)} ACHIEVEMENTS UNLOCKED"
        bbox = draw.textbbox((0, 0), ach_txt, font=font_footer)
        draw.text((BOX_CENTER_X - (bbox[2] - bbox[0]) // 2, y), ach_txt, fill=LABEL_DIM, font=font_footer)

    # — Export ─────────────────────────────────────────────────
    buf = io.BytesIO()
    # Save as RGB to save file size
    img.convert("RGB").save(buf, format="PNG", quality=95)
    buf.seek(0)
    return buf.getvalue()


def generate_all_wrapped(players: List[Player] = None) -> List[Tuple[Player, bytes, Tuple[str, str, str, str]]]:
    """
    Generate Wrapped cards for all players using the image background.
    """
    if players is None:
        players = get_all_players()

    if not players:
        return []

    superlatives = calculate_superlatives(players)
    results = []

    # Sort by points desc
    sorted_players = sorted(players, key=lambda p: p.points, reverse=True)

    for p in sorted_players:
        sup = superlatives.get(p.user_id, ("🎖️", "Survivor", "You made it through the game.", "Still breathing!"))
        img_bytes = generate_wrapped_card(p, sup)
        results.append((p, img_bytes, sup))

    return results
