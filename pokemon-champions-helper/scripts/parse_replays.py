"""
리플레이 로그 파싱 스크립트
실행: python scripts/parse_replays.py

data/replays/*.log → data/replay_dataset.csv

CSV 컬럼:
  id, p1_t1~p1_t6, p2_t1~p2_t6, winner("p1"|"p2")
"""

import csv
from pathlib import Path

ROOT       = Path(__file__).parent.parent
REPLAY_DIR = ROOT / "data" / "replays"
OUT_CSV    = ROOT / "data" / "replay_dataset.csv"

P1_COLS = [f"p1_t{i}" for i in range(1, 7)]
P2_COLS = [f"p2_t{i}" for i in range(1, 7)]
FIELDNAMES = ["id"] + P1_COLS + P2_COLS + ["winner"]


def extract_name(raw: str) -> str:
    """'Garchomp, L50, M' → 'Garchomp'"""
    return raw.split(",")[0].strip()


def parse_log(text: str) -> dict | None:
    """
    리플레이 로그에서 팀 구성 + 승자 추출.
    teampreview가 없거나 6마리 미만이면 None 반환.
    """
    p1_name = p2_name = ""
    p1_team: list[str] = []
    p2_team: list[str] = []
    winner: str | None = None

    for line in text.splitlines():
        parts = line.split("|")
        if len(parts) < 2:
            continue
        tag = parts[1]

        if tag == "player" and len(parts) >= 4:
            if parts[2] == "p1":
                p1_name = parts[3]
            elif parts[2] == "p2":
                p2_name = parts[3]

        elif tag == "poke" and len(parts) >= 4:
            side, raw = parts[2], parts[3]
            name = extract_name(raw)
            if side == "p1" and len(p1_team) < 6:
                p1_team.append(name)
            elif side == "p2" and len(p2_team) < 6:
                p2_team.append(name)

        elif tag == "win" and len(parts) >= 3:
            w = parts[2].strip()
            if w == p1_name:
                winner = "p1"
            elif w == p2_name:
                winner = "p2"

    if len(p1_team) != 6 or len(p2_team) != 6 or winner is None:
        return None

    return {"p1_team": p1_team, "p2_team": p2_team, "winner": winner}


def main():
    log_files = sorted(REPLAY_DIR.glob("*.log"))
    if not log_files:
        print(f"로그 파일 없음: {REPLAY_DIR}")
        print("fetch_replays.py 먼저 실행하세요")
        return

    print(f"로그 파일: {len(log_files)}개")

    rows: list[dict] = []
    skipped = 0

    for i, path in enumerate(log_files, 1):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            skipped += 1
            continue

        result = parse_log(text)
        if result is None:
            skipped += 1
            continue

        row: dict = {"id": path.stem, "winner": result["winner"]}
        for col, val in zip(P1_COLS, result["p1_team"]):
            row[col] = val
        for col, val in zip(P2_COLS, result["p2_team"]):
            row[col] = val
        rows.append(row)

        if i % 500 == 0:
            print(f"  {i}/{len(log_files)} 처리 중... (유효 {len(rows)}개)")

    print(f"\n파싱 완료: 유효 {len(rows)}개 / 스킵 {skipped}개")

    if not rows:
        print("저장할 데이터 없음")
        return

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    p1_wins = sum(1 for r in rows if r["winner"] == "p1")
    p2_wins = len(rows) - p1_wins
    print(f"승패 분포: p1 승 {p1_wins} ({p1_wins/len(rows)*100:.1f}%)  "
          f"/ p2 승 {p2_wins} ({p2_wins/len(rows)*100:.1f}%)")
    print(f"→ {OUT_CSV}")


if __name__ == "__main__":
    main()
