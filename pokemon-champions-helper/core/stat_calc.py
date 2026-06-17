"""
레벨 50 실수치 계산
- IV: 31 고정 (6V)
- EV: my_team.json 직접 지정 / 상대는 Smogon top_spreads 가중평균 추정
"""
import math

LEVEL = 50
STAT_KEYS = ["hp", "atk", "def", "spa", "spd", "spe"]

NATURE_BOOSTS: dict[str, tuple[str, str]] = {
    "Lonely":  ("atk", "def"),  "Brave":   ("atk", "spe"),
    "Adamant": ("atk", "spa"),  "Naughty": ("atk", "spd"),
    "Bold":    ("def", "atk"),  "Relaxed": ("def", "spe"),
    "Impish":  ("def", "spa"),  "Lax":     ("def", "spd"),
    "Timid":   ("spe", "atk"),  "Hasty":   ("spe", "def"),
    "Jolly":   ("spe", "spa"),  "Naive":   ("spe", "spd"),
    "Modest":  ("spa", "atk"),  "Mild":    ("spa", "def"),
    "Quiet":   ("spa", "spe"),  "Rash":    ("spa", "spd"),
    "Calm":    ("spd", "atk"),  "Gentle":  ("spd", "def"),
    "Sassy":   ("spd", "spe"),  "Careful": ("spd", "spa"),
}


def _nature_mods(nature: str) -> dict[str, float]:
    mods = {k: 1.0 for k in STAT_KEYS}
    info = NATURE_BOOSTS.get(nature)
    if info:
        mods[info[0]] = 1.1
        mods[info[1]] = 0.9
    return mods


def calc_hp(base: int, iv: int = 31, ev: int = 0) -> int:
    return math.floor((2 * base + iv + math.floor(ev / 4)) * LEVEL / 100) + LEVEL + 10


def calc_stat(base: int, iv: int = 31, ev: int = 0, nature: float = 1.0) -> int:
    raw = math.floor((2 * base + iv + math.floor(ev / 4)) * LEVEL / 100) + 5
    return math.floor(raw * nature)


def _parse_spread(spread_str: str) -> tuple[dict[str, int], str]:
    """'Jolly:0/252/0/0/4/252' → (evs_dict, nature_name)"""
    parts = spread_str.split(":")
    if len(parts) != 2:
        return {k: 0 for k in STAT_KEYS}, "Hardy"
    nature_name = parts[0]
    ev_parts = parts[1].split("/")
    if len(ev_parts) != 6:
        return {k: 0 for k in STAT_KEYS}, nature_name
    evs = {k: int(ev_parts[i]) for i, k in enumerate(STAT_KEYS)}
    return evs, nature_name


def estimate_spread(smogon_sets: dict, poke_name: str) -> tuple[dict[str, int], str]:
    """Smogon top_spreads 가중평균 → 추정 EV + 최다 사용 nature"""
    spreads = smogon_sets.get(poke_name, {}).get("top_spreads", [])
    if not spreads:
        return {k: 0 for k in STAT_KEYS}, "Hardy"

    total = sum(s["usage"] for s in spreads)
    nature_usage: dict[str, float] = {}
    weighted_evs = {k: 0.0 for k in STAT_KEYS}

    for s in spreads:
        evs, nat = _parse_spread(s["spread"])
        w = s["usage"] / total
        nature_usage[nat] = nature_usage.get(nat, 0.0) + s["usage"]
        for k in STAT_KEYS:
            weighted_evs[k] += evs[k] * w

    best_nature = max(nature_usage, key=lambda n: nature_usage[n])
    final_evs   = {k: round(v) for k, v in weighted_evs.items()}
    return final_evs, best_nature


def calc_lv50_stats(base_stats: dict, evs: dict, nature: str) -> dict[str, int]:
    """base_stats + EV + nature → 레벨 50 실수치"""
    mods   = _nature_mods(nature)
    result = {}
    for key in STAT_KEYS:
        base = base_stats.get(key, 50)
        ev   = evs.get(key, 0)
        if key == "hp":
            result[key] = calc_hp(base, ev=ev)
        else:
            result[key] = calc_stat(base, ev=ev, nature=mods[key])
    return result
