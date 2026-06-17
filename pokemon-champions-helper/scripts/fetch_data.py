"""
Smogon / Pokémon Showdown 데이터 수집 스크립트
실행: python scripts/fetch_data.py
"""

import json
import time
import requests
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Smogon 월별 통계 — gen9ou 1695 레이팅대
SMOGON_CHAOS_URL = "https://www.smogon.com/stats/2024-11/chaos/gen9ou-1695.json"
# Showdown 포켓몬 데이터
SHOWDOWN_POKEDEX_URL = "https://raw.githubusercontent.com/smogon/pokemon-showdown/master/data/pokedex.ts"
SHOWDOWN_MOVES_URL   = "https://raw.githubusercontent.com/smogon/pokemon-showdown/master/data/moves.ts"


# ── 타입 상성 행렬 (하드코딩 — 변경 없음) ────────────────────────────────────

TYPES = [
    "Normal","Fire","Water","Electric","Grass","Ice",
    "Fighting","Poison","Ground","Flying","Psychic","Bug",
    "Rock","Ghost","Dragon","Dark","Steel","Fairy"
]

# T[atk][def] = 배율  (0=무효, 0.5=반감, 1=보통, 2=효과적)
TYPE_CHART_RAW = {
    "Normal":   {"Rock":0.5,"Ghost":0,"Steel":0.5},
    "Fire":     {"Fire":0.5,"Water":0.5,"Rock":0.5,"Dragon":0.5,
                 "Grass":2,"Ice":2,"Bug":2,"Steel":2},
    "Water":    {"Water":0.5,"Grass":0.5,"Dragon":0.5,
                 "Fire":2,"Ground":2,"Rock":2},
    "Electric": {"Electric":0.5,"Grass":0.5,"Dragon":0.5,"Ground":0,
                 "Water":2,"Flying":2},
    "Grass":    {"Fire":0.5,"Grass":0.5,"Poison":0.5,"Flying":0.5,
                 "Bug":0.5,"Dragon":0.5,"Steel":0.5,
                 "Water":2,"Ground":2,"Rock":2},
    "Ice":      {"Water":0.5,"Ice":0.5,
                 "Fire":0.5,"Steel":0.5,
                 "Grass":2,"Ground":2,"Flying":2,"Dragon":2},
    "Fighting": {"Ghost":0,"Poison":0.5,"Flying":0.5,"Psychic":0.5,"Bug":0.5,"Fairy":0.5,
                 "Normal":2,"Ice":2,"Rock":2,"Dark":2,"Steel":2},
    "Poison":   {"Poison":0.5,"Ground":0.5,"Rock":0.5,"Ghost":0.5,"Steel":0,
                 "Grass":2,"Fairy":2},
    "Ground":   {"Grass":0.5,"Bug":0.5,"Flying":0,
                 "Fire":2,"Electric":2,"Poison":2,"Rock":2,"Steel":2},
    "Flying":   {"Electric":0.5,"Rock":0.5,"Steel":0.5,
                 "Grass":2,"Fighting":2,"Bug":2},
    "Psychic":  {"Psychic":0.5,"Steel":0.5,"Dark":0,
                 "Fighting":2,"Poison":2},
    "Bug":      {"Fire":0.5,"Fighting":0.5,"Flying":0.5,"Ghost":0.5,
                 "Steel":0.5,"Fairy":0.5,
                 "Grass":2,"Psychic":2,"Dark":2},
    "Rock":     {"Fighting":0.5,"Ground":0.5,"Steel":0.5,
                 "Fire":2,"Ice":2,"Flying":2,"Bug":2},
    "Ghost":    {"Normal":0,"Dark":0.5,
                 "Psychic":2,"Ghost":2},
    "Dragon":   {"Steel":0.5,"Fairy":0,
                 "Dragon":2},
    "Dark":     {"Fighting":0.5,"Dark":0.5,"Fairy":0.5,
                 "Psychic":2,"Ghost":2},
    "Steel":    {"Fire":0.5,"Water":0.5,"Electric":0.5,"Steel":0.5,
                 "Ice":2,"Rock":2,"Fairy":2},
    "Fairy":    {"Fire":0.5,"Poison":0.5,"Steel":0.5,
                 "Fighting":2,"Dragon":2,"Dark":2},
}

def build_type_chart():
    n = len(TYPES)
    idx = {t: i for i, t in enumerate(TYPES)}
    chart = [[1.0] * n for _ in range(n)]
    for atk, defmap in TYPE_CHART_RAW.items():
        for def_t, mul in defmap.items():
            chart[idx[atk]][idx[def_t]] = mul
    return {"types": TYPES, "chart": chart}


# ── 우선도 기술 목록 (하드코딩) ───────────────────────────────────────────────

PRIORITY_MOVES = {
    "2":  ["Extreme Speed"],
    "1":  ["Aqua Jet","Bullet Punch","Fake Out","Feint","First Impression",
            "Ice Shard","Mach Punch","Quick Attack","Shadow Sneak","Sucker Punch",
            "Accelerock","Jet Punch","Water Shuriken"],
    "0":  [],
    "-1": ["Vital Throw"],
    "-3": ["Focus Punch"],
    "-6": ["Counter","Mirror Coat","Metal Burst"],
    "-7": ["Trick Room"],
}


# ── PokeAPI 포켓몬 데이터 수집 ───────────────────────────────────────────────

POKEAPI_URL = "https://pokeapi.co/api/v2/pokemon/{name}"

def smogon_name_to_pokeapi(name: str) -> str:
    """Smogon 이름 → PokeAPI slug 변환"""
    n = name.lower().replace(" ", "-").replace("'", "").replace(".", "")
    # 포름 이름 매핑 (필요한 경우)
    overrides = {
        "landorus-therian": "landorus-therian",
        "tornadus-therian": "tornadus-therian",
        "thundurus-therian": "thundurus-therian",
        "urshifu-rapid-strike": "urshifu-rapid-strike",
        "ogerpon-wellspring": "ogerpon-wellspring",
        "ogerpon-hearthflame": "ogerpon-hearthflame",
        "ogerpon-cornerstone": "ogerpon-cornerstone",
        "terapagos-terastal": "terapagos-terastal",
    }
    return overrides.get(n, n)

def fetch_pokedex_from_smogon_list(smogon_sets: dict) -> dict:
    """smogon_sets 포켓몬 목록을 기준으로 PokeAPI에서 스탯/타입 수집"""
    result = {}
    names = sorted(smogon_sets.keys())
    print(f"PokeAPI에서 {len(names)}마리 데이터 수집 중...")

    for i, smogon_name in enumerate(names, 1):
        api_name = smogon_name_to_pokeapi(smogon_name)
        try:
            r = requests.get(POKEAPI_URL.format(name=api_name), timeout=10)
            if r.status_code == 404:
                # 폼 이름 제거 후 재시도 (예: landorus-therian → landorus)
                base_name = api_name.split("-")[0]
                r = requests.get(POKEAPI_URL.format(name=base_name), timeout=10)
            r.raise_for_status()
            data = r.json()

            stats = {s["stat"]["name"]: s["base_stat"] for s in data["stats"]}
            types = [t["type"]["name"].capitalize() for t in data["types"]]

            result[smogon_name] = {
                "types": types,
                "base_stats": {
                    "hp":  stats.get("hp", 0),
                    "atk": stats.get("attack", 0),
                    "def": stats.get("defense", 0),
                    "spa": stats.get("special-attack", 0),
                    "spd": stats.get("special-defense", 0),
                    "spe": stats.get("speed", 0),
                }
            }
            if i % 20 == 0:
                print(f"  {i}/{len(names)} 완료...")
            time.sleep(0.3)
        except Exception as e:
            print(f"  ! {smogon_name} ({api_name}) 스킵: {e}")
            continue

    return result


# ── Smogon chaos JSON 파싱 ───────────────────────────────────────────────────

def fetch_smogon_chaos():
    print("Smogon chaos JSON 다운로드 중...")
    r = requests.get(SMOGON_CHAOS_URL, timeout=60)
    r.raise_for_status()
    return r.json()

def parse_smogon_chaos(chaos: dict) -> dict:
    """포켓몬별 상위 세트 추출"""
    result = {}
    data = chaos.get("data", {})
    for poke_name, poke_data in data.items():
        moves_usage = poke_data.get("Moves", {})
        items_usage = poke_data.get("Items", {})
        abilities_usage = poke_data.get("Abilities", {})
        spreads_usage = poke_data.get("Spreads", {})

        # 상위 5개씩 추출
        top_moves = sorted(moves_usage.items(), key=lambda x: x[1], reverse=True)[:10]
        top_items = sorted(items_usage.items(), key=lambda x: x[1], reverse=True)[:5]
        top_abilities = sorted(abilities_usage.items(), key=lambda x: x[1], reverse=True)[:3]
        top_spreads = sorted(spreads_usage.items(), key=lambda x: x[1], reverse=True)[:5]

        result[poke_name] = {
            "top_moves": [{"move": m, "usage": round(u, 4)} for m, u in top_moves],
            "top_items": [{"item": i, "usage": round(u, 4)} for i, u in top_items],
            "top_abilities": [{"ability": a, "usage": round(u, 4)} for a, u in top_abilities],
            "top_spreads": [{"spread": s, "usage": round(u, 4)} for s, u in top_spreads],
        }
    return result


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main():
    # 1) 타입 상성 저장
    print("타입 상성 행렬 생성 중...")
    type_chart = build_type_chart()
    (DATA_DIR / "type_chart.json").write_text(
        json.dumps(type_chart, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  → data/type_chart.json 저장 완료 ({len(TYPES)}×{len(TYPES)} 행렬)")

    # 2) 우선도 기술 저장
    print("우선도 기술 목록 저장 중...")
    (DATA_DIR / "priority_moves.json").write_text(
        json.dumps(PRIORITY_MOVES, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("  → data/priority_moves.json 저장 완료")

    # 3) Smogon chaos (먼저 받아야 포켓몬 목록 파악 가능)
    try:
        chaos = fetch_smogon_chaos()
        smogon_sets = parse_smogon_chaos(chaos)
        (DATA_DIR / "smogon_sets.json").write_text(
            json.dumps(smogon_sets, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  → data/smogon_sets.json 저장 완료 ({len(smogon_sets)}마리)")
        # 4) PokeAPI로 포켓몬 스탯/타입 수집
        try:
            pokedex = fetch_pokedex_from_smogon_list(smogon_sets)
            (DATA_DIR / "pokemon.json").write_text(
                json.dumps(pokedex, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"  → data/pokemon.json 저장 완료 ({len(pokedex)}마리)")
        except Exception as e2:
            print(f"  ! PokeAPI 수집 실패: {e2}")
    except Exception as e:
        print(f"  ! Smogon 다운로드 실패: {e}")

    print("\n데이터 수집 완료.")


if __name__ == "__main__":
    main()
