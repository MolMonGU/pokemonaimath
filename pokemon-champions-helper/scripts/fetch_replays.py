"""
Smogon 리플레이 다운로드 스크립트
실행: python scripts/fetch_replays.py

gen9ou 포맷, 1500+ 레이팅 배틀 로그를 data/replays/ 에 저장.
재실행하면 이미 받은 파일은 건너뜀 (중단 후 재개 가능).
"""

import time
import requests
from pathlib import Path

ROOT       = Path(__file__).parent.parent
REPLAY_DIR = ROOT / "data" / "replays"
REPLAY_DIR.mkdir(parents=True, exist_ok=True)

FORMAT     = "gen9ou"
MIN_RATING = 1500
TARGET     = 10000

SEARCH_URL = "https://replay.pokemonshowdown.com/search.json"
LOG_URL    = "https://replay.pokemonshowdown.com/{id}.log"


def fetch_list(before: int | None = None) -> list[dict]:
    params: dict = {"format": FORMAT}
    if before:
        params["before"] = before
    r = requests.get(SEARCH_URL, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else []


def download_log(replay_id: str) -> str:
    r = requests.get(LOG_URL.format(id=replay_id), timeout=15)
    r.raise_for_status()
    return r.text


def main():
    existing = {p.stem for p in REPLAY_DIR.glob("*.log")}
    print(f"기존 파일: {len(existing)}개  |  목표: {TARGET}개")

    downloaded = 0
    before: int | None = None
    consecutive_empty = 0

    while len(existing) < TARGET:
        try:
            items = fetch_list(before)
        except Exception as e:
            print(f"  ! 목록 조회 실패: {e}  (5초 후 재시도)")
            time.sleep(5)
            continue

        if not items:
            consecutive_empty += 1
            if consecutive_empty >= 3:
                print("  더 이상 리플레이 없음 — 종료")
                break
            time.sleep(2)
            continue
        consecutive_empty = 0

        for item in items:
            rid    = item.get("id", "")
            rating = item.get("rating") or 0

            if not rid:
                continue
            if rating < MIN_RATING:
                continue
            if rid in existing:
                continue

            try:
                log = download_log(rid)
                (REPLAY_DIR / f"{rid}.log").write_text(log, encoding="utf-8")
                existing.add(rid)
                downloaded += 1
                print(f"  [{len(existing):4d}/{TARGET}] {rid}  rating={rating}")
                time.sleep(0.4)
            except Exception as e:
                print(f"  ! {rid}: {e}")

            if len(existing) >= TARGET:
                break

        # 다음 페이지: 가장 오래된 uploadtime 기준
        before = items[-1].get("uploadtime")
        time.sleep(1.0)

    print(f"\n완료: 총 {len(existing)}개  (이번 세션 {downloaded}개 신규)")
    print(f"저장 위치: {REPLAY_DIR}")


if __name__ == "__main__":
    main()
