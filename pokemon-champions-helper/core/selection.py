"""선출 추천 — 내 팀 6마리 중 3마리 조합 점수화"""

import json
from itertools import combinations
from pathlib import Path
from core.type_calc import effectiveness

DATA_DIR = Path(__file__).parent.parent / "data"


def load_my_team() -> list[dict]:
    p = DATA_DIR / "my_team.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def load_opp_team() -> list[dict]:
    p = DATA_DIR / "opp_team.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def _best_coverage(my_combo: list[dict], opp: dict) -> tuple[float, str]:
    """내 3마리 중 상대 한 마리에 가장 유리한 포켓몬 + 배율 반환"""
    opp_types = opp["pokedex_entry"]["types"]
    best_eff = 0.0
    best_name = ""
    for p in my_combo:
        eff = effectiveness(p["pokedex_entry"]["types"], opp_types)
        if eff > best_eff:
            best_eff = eff
            best_name = p["name_kr"]
    return best_eff, best_name


def _score_combo(my_combo: list[dict], opp_team: list[dict]) -> float:
    """상대 6마리 전체 커버리지 합산 점수"""
    total = 0.0
    for opp in opp_team:
        eff, _ = _best_coverage(my_combo, opp)
        total += eff
    return total


def recommend(my_team: list[dict] | None = None,
              opp_team: list[dict] | None = None,
              top_n: int = 5) -> list[dict]:
    """
    선출 추천.
    반환: [{"combo": [name_kr...], "score": float, "coverage": {opp_name_kr: {"eff": float, "by": name_kr}}}, ...]
    """
    if my_team is None:
        my_team = load_my_team()
    if opp_team is None:
        opp_team = load_opp_team()

    results = []
    for combo in combinations(my_team, 3):
        combo = list(combo)
        score = _score_combo(combo, opp_team)
        coverage = {}
        for opp in opp_team:
            eff, by = _best_coverage(combo, opp)
            coverage[opp["name_kr"]] = {"eff": eff, "by": by}
        results.append({
            "combo": [p["name_kr"] for p in combo],
            "score": round(score, 2),
            "coverage": coverage,
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_n]
