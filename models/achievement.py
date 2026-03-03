"""Achievement definitions for the Assassins Game."""


# Each achievement: {id: (emoji, name, description)}
ACHIEVEMENTS = {
    # Kill milestones
    "first_blood": ("🩸", "First Blood", "Get your first kill"),
    "serial_killer": ("💀", "Serial Killer", "Get 10 total kills"),
    "legend": ("👑", "Legend", "Get 20 total kills"),

    # Streak achievements
    "triple_kill": ("🔥", "Triple Kill", "Reach a 3 kill streak"),
    "penta_kill": ("💥", "Penta Kill", "Reach a 5 kill streak"),
    "unstoppable": ("⚡", "Unstoppable", "Reach a 10 kill streak"),

    # Stealth achievements
    "shadow": ("🥷", "Shadow", "Get 3 stealth kills"),
    "silent_assassin": ("🗡️", "Silent Assassin", "Get 5 stealth kills"),

    # Bounty achievements
    "bounty_hunter": ("💰", "Bounty Hunter", "Claim your first bounty"),

    # Resilience achievements
    "survivor": ("🛡️", "Survivor", "Die 5 times and still have positive KDA"),
    "comeback_kid": ("🔄", "Comeback Kid", "Get a kill within 10 min of respawning"),
}

# Streak thresholds for group announcements
STREAK_MILESTONES = {
    3: ("🔥", "TRIPLE KILL"),
    5: ("💥", "PENTA KILL"),
    7: ("⚡", "DOMINATING"),
    10: ("☄️", "UNSTOPPABLE"),
    15: ("👑", "GODLIKE"),
}
