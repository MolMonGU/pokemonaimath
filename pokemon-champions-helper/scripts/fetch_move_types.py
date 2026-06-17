"""
Pokemon Showdown moves.ts → data/move_types.json 저장
실행: python scripts/fetch_move_types.py

저장 형식:
  {"icebeam": {"type": "Ice", "bp": 90, "cat": "Special", "pri": 0}, ...}
"""
import json
import re
import requests
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
MOVES_TS_URL = "https://raw.githubusercontent.com/smogon/pokemon-showdown/master/data/moves.ts"


def to_showdown_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def fetch_move_data() -> dict[str, dict]:
    print("Showdown moves.ts 다운로드 중...")
    r = requests.get(MOVES_TS_URL, timeout=30)
    r.raise_for_status()
    content = r.text
    print(f"  다운로드 완료 ({len(content):,} bytes)")

    header_re = re.compile(r'^\t(?:"([^"]+)"|([A-Za-z]\w*)):\s*\{')
    type_re   = re.compile(r'^\t\ttype:\s*"([A-Za-z]+)"')
    bp_re     = re.compile(r'^\t\tbasePower:\s*(\d+)')
    cat_re    = re.compile(r'^\t\tcategory:\s*"([A-Za-z]+)"')
    pri_re    = re.compile(r'^\t\tpriority:\s*(-?\d+)')

    result: dict[str, dict] = {}
    current_id = None
    current_data: dict = {}

    for line in content.splitlines():
        hm = header_re.match(line)
        if hm:
            if current_id and current_data:
                result[current_id] = current_data
            raw_name = hm.group(1) or hm.group(2)
            current_id = to_showdown_id(raw_name)
            current_data = {}
            continue
        if current_id is None:
            continue
        m = type_re.match(line)
        if m:
            current_data["type"] = m.group(1).capitalize()
            continue
        m = bp_re.match(line)
        if m:
            current_data["bp"] = int(m.group(1))
            continue
        m = cat_re.match(line)
        if m:
            current_data["cat"] = m.group(1)
            continue
        m = pri_re.match(line)
        if m:
            current_data["pri"] = int(m.group(1))

    if current_id and current_data:
        result[current_id] = current_data

    return result


def main():
    out_path = DATA_DIR / "move_types.json"

    move_data = fetch_move_data()
    print(f"  파싱 완료: {len(move_data)}개 기술")

    smogon_path = DATA_DIR / "smogon_sets.json"
    if smogon_path.exists():
        smogon = json.loads(smogon_path.read_text(encoding="utf-8"))
        used: set[str] = set()
        for entry in smogon.values():
            for m in entry.get("top_moves", []):
                used.add(m["move"])
        covered = used & set(move_data.keys())
        missing = used - set(move_data.keys())
        print(f"  smogon 기술 {len(used)}개 중 {len(covered)}개 커버")
        if missing:
            print(f"  미커버: {sorted(missing)}")

    out_path.write_text(
        json.dumps(move_data, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8"
    )
    print(f"완료 → {out_path} ({len(move_data)}개)")


if __name__ == "__main__":
    main()
