"""대미지 계산 + HP 임계점 판정"""

import math
from core.type_calc import move_effectiveness


def _rank_mod(stat: int, rank: int) -> int:
    """랭크 보정 후 실수치"""
    if rank >= 0:
        return math.floor(stat * (2 + rank) / 2)
    else:
        return math.floor(stat * 2 / (2 + abs(rank)))


def calc_damage(
    level: int,
    power: int,
    atk: int, atk_rank: int,
    def_: int, def_rank: int,
    move_type: str,
    attacker_types: list[str],
    defender_types: list[str],
    weather: float = 1.0,
    is_crit: bool = False,
    stab: bool | None = None,
    burn: bool = False,
    other: float = 1.0,
) -> dict:
    """
    포켓몬 대미지 공식 계산.
    반환: {"min": int, "max": int, "avg": float, "rolls": list[int]}
    """
    atk_eff = _rank_mod(atk, 0 if is_crit and atk_rank < 0 else atk_rank)
    def_eff = _rank_mod(def_, 0 if is_crit and def_rank > 0 else def_rank)

    raw = math.floor(
        math.floor(
            math.floor(2 * level / 5 + 2) * power * atk_eff / def_eff / 50
        ) + 2
    )

    # 타입 배율
    type_mul = move_effectiveness(move_type, defender_types)

    # STAB (자동 판정)
    if stab is None:
        stab = move_type in attacker_types
    stab_mul = 1.5 if stab else 1.0

    # 급소
    crit_mul = 1.5 if is_crit else 1.0

    # 화상 (물리기 + 화상 = 0.5)
    burn_mul = 0.5 if burn else 1.0

    # 난수 85~100 → 16 롤
    rolls = []
    for r in range(85, 101):
        d = math.floor(
            math.floor(
                math.floor(
                    math.floor(
                        math.floor(raw * weather) * crit_mul
                    ) * r / 100
                ) * stab_mul
            ) * type_mul
        )
        d = math.floor(math.floor(d * burn_mul) * other)
        rolls.append(max(1, d))

    return {
        "min": rolls[0],
        "max": rolls[-1],
        "avg": round(sum(rolls) / len(rolls), 1),
        "rolls": rolls,
        "type_effectiveness": type_mul,
    }


def ohko_check(damage_result: dict, target_hp: int, current_hp: int | None = None) -> dict:
    """
    처치 가능 여부 판정.
    current_hp: None이면 최대 HP 기준
    반환: {"can_ohko": bool, "guaranteed": bool, "pct": float, "min_pct": float, "max_pct": float}
    """
    hp = current_hp if current_hp is not None else target_hp
    dmg_min = damage_result["min"]
    dmg_max = damage_result["max"]
    rolls = damage_result["rolls"]

    hits_that_ko = sum(1 for r in rolls if r >= hp)
    pct = hits_that_ko / len(rolls)

    return {
        "can_ohko": dmg_max >= hp,
        "guaranteed": dmg_min >= hp,
        "pct": round(pct * 100, 1),
        "min_pct": round(dmg_min / target_hp * 100, 1),
        "max_pct": round(dmg_max / target_hp * 100, 1),
    }


def hp_threshold(
    level: int, power: int,
    atk: int, atk_rank: int,
    def_: int, def_rank: int,
    move_type: str,
    attacker_types: list[str],
    defender_types: list[str],
    target_max_hp: int,
    **kwargs,
) -> dict:
    """
    상대가 몇 HP 이하면 확정/최대 처치 가능한지 계산.
    반환: {"guaranteed_threshold": int | None, "possible_threshold": int | None}
    """
    res = calc_damage(
        level, power, atk, atk_rank, def_, def_rank,
        move_type, attacker_types, defender_types, **kwargs
    )
    return {
        "guaranteed_threshold": res["min"],   # min 이하면 확정 처치
        "possible_threshold": res["max"],      # max 이하면 처치 가능
        "damage": res,
    }
