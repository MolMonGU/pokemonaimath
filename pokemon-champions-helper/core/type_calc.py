"""타입 상성 계산 — numpy 18×18 행렬 연산"""

import json
import numpy as np
from pathlib import Path
from functools import lru_cache

DATA_DIR = Path(__file__).parent.parent / "data"

TYPES = [
    "Normal","Fire","Water","Electric","Grass","Ice",
    "Fighting","Poison","Ground","Flying","Psychic","Bug",
    "Rock","Ghost","Dragon","Dark","Steel","Fairy"
]
TYPE_IDX = {t: i for i, t in enumerate(TYPES)}

_chart: np.ndarray | None = None


def get_chart() -> np.ndarray:
    global _chart
    if _chart is None:
        path = DATA_DIR / "type_chart.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            _chart = np.array(data["chart"], dtype=np.float32)
        else:
            # fetch_data 미실행 시 하드코딩 폴백
            _chart = np.ones((18, 18), dtype=np.float32)
    return _chart


def type_vector(types: list[str]) -> np.ndarray:
    """타입 목록 → 18차원 원핫 벡터 (듀얼타입이면 2개 1.0)"""
    v = np.zeros(18, dtype=np.float32)
    for t in types:
        if t in TYPE_IDX:
            v[TYPE_IDX[t]] = 1.0
    return v


def effectiveness(atk_types: list[str], def_types: list[str]) -> float:
    """
    atk_types 중 최대 배율 반환 (여러 공격 타입 중 best pick)
    def_types는 상대 포켓몬 타입 (듀얼타입이면 곱셈 적용)
    """
    T = get_chart()
    best = 0.0
    for atk in atk_types:
        if atk not in TYPE_IDX:
            continue
        mul = 1.0
        for def_t in def_types:
            if def_t in TYPE_IDX:
                mul *= T[TYPE_IDX[atk], TYPE_IDX[def_t]]
        if mul > best:
            best = mul
    return best


def move_effectiveness(move_type: str, def_types: list[str]) -> float:
    """특정 기술 타입 vs 방어 타입 배율"""
    T = get_chart()
    if move_type not in TYPE_IDX:
        return 1.0
    mul = 1.0
    for def_t in def_types:
        if def_t in TYPE_IDX:
            mul *= T[TYPE_IDX[move_type], TYPE_IDX[def_t]]
    return mul


def party_coverage_matrix(my_party: list[list[str]], opp_party: list[list[str]]) -> np.ndarray:
    """
    내 파티 vs 상대 파티 커버리지 스코어 행렬
    반환: (내 파티수 × 상대 파티수) float 배열
    각 값 = 내 포켓몬이 상대에게 줄 수 있는 최대 타입 배율
    """
    T = get_chart()
    n, m = len(my_party), len(opp_party)
    mat = np.zeros((n, m), dtype=np.float32)
    for i, my_types in enumerate(my_party):
        my_vec = type_vector(my_types)
        for j, opp_types in enumerate(opp_party):
            opp_vec = type_vector(opp_types)
            # 내 각 타입 × 상대 방어 타입 → 최대값
            scores = T @ my_vec  # shape (18,): 각 공격타입이 상대에 주는 배율 합
            # 실제로는 상대 듀얼타입 곱셈이 필요
            mat[i, j] = effectiveness(my_types, opp_types)
    return mat


def weakness_summary(def_types: list[str]) -> dict:
    """특정 포켓몬의 타입 약점/저항/무효 정리"""
    T = get_chart()
    result = {"4x": [], "2x": [], "1x": [], "0.5x": [], "0.25x": [], "0x": []}
    for atk in TYPES:
        mul = move_effectiveness(atk, def_types)
        if mul == 4.0:
            result["4x"].append(atk)
        elif mul == 2.0:
            result["2x"].append(atk)
        elif mul == 1.0:
            result["1x"].append(atk)
        elif mul == 0.5:
            result["0.5x"].append(atk)
        elif mul == 0.25:
            result["0.25x"].append(atk)
        elif mul == 0.0:
            result["0x"].append(atk)
    return result
