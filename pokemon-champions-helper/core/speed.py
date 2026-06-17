"""스피드 실수치 계산 및 선제/후제 판정"""

import math


NATURE_MOD = {"plus": 1.1, "neutral": 1.0, "minus": 0.9}


def calc_speed(base_spe: int, ev: int = 0, iv: int = 31,
               level: int = 50, nature: str = "neutral",
               rank: int = 0, scarf: bool = False,
               weather_boost: bool = False, paralysis: bool = False,
               trick_room: bool = False) -> int:
    """
    최종 스피드 실수치 계산.
    rank: -6 ~ +6
    반환: 정수 실수치
    """
    base = math.floor((2 * base_spe + iv + math.floor(ev / 4)) * level / 100) + 5
    stat = math.floor(base * NATURE_MOD[nature])

    # 랭크 보정
    if rank >= 0:
        ranked = math.floor(stat * (2 + rank) / 2)
    else:
        ranked = math.floor(stat * 2 / (2 + abs(rank)))

    final = ranked
    if scarf:
        final = math.floor(final * 1.5)
    if weather_boost:
        final = math.floor(final * 2.0)
    if paralysis:
        final = math.floor(final * 0.5)

    return final


def min_ev_to_outspeed(base_spe: int, target_speed: int,
                        iv: int = 31, level: int = 50,
                        nature: str = "neutral", rank: int = 0,
                        scarf: bool = False, weather_boost: bool = False) -> int | None:
    """
    target_speed를 넘기 위한 최소 EV 반환 (불가능하면 None)
    """
    for ev in range(0, 253, 4):
        spd = calc_speed(base_spe, ev, iv, level, nature, rank, scarf, weather_boost)
        if spd > target_speed:
            return ev
    return None


def speed_comparison(my_speed: int, opp_speed: int, trick_room: bool = False) -> str:
    """'선제' / '후제' / '동속' 반환"""
    if trick_room:
        if my_speed < opp_speed:
            return "선제 (트릭룸)"
        elif my_speed > opp_speed:
            return "후제 (트릭룸)"
        else:
            return "동속"
    else:
        if my_speed > opp_speed:
            return "선제"
        elif my_speed < opp_speed:
            return "후제"
        else:
            return "동속"


def priority_order(my_move_priority: int, opp_move_priority: int,
                   my_speed: int, opp_speed: int,
                   trick_room: bool = False) -> str:
    """
    우선도까지 고려한 행동 순서 판정.
    반환: '내가 먼저' / '상대 먼저' / '동시'
    """
    if my_move_priority > opp_move_priority:
        return "내가 먼저"
    if my_move_priority < opp_move_priority:
        return "상대 먼저"
    # 우선도 동일 → 스피드 비교
    cmp = speed_comparison(my_speed, opp_speed, trick_room)
    if "선제" in cmp:
        return "내가 먼저"
    elif "후제" in cmp:
        return "상대 먼저"
    else:
        return "동시"
