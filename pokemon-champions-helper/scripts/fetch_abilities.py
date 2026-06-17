"""
PokeAPI에서 포켓몬 특성 수집 → data/pokemon.json 업데이트
실행: python scripts/fetch_abilities.py
"""
import json
import re
import time
import requests
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
POKEAPI  = "https://pokeapi.co/api/v2/pokemon/{}"

NAME_FIXES = {
    "Farfetch'd":   "farfetchd",
    "Sirfetch'd":   "sirfetchd",
    "Mr. Mime":     "mr-mime",
    "Mr. Rime":     "mr-rime",
    "Mime Jr.":     "mime-jr",
    "Porygon-Z":    "porygon-z",
    "Porygon2":     "porygon2",
    "Ho-Oh":        "ho-oh",
    "Nidoran♂":     "nidoran-m",
    "Nidoran♀":     "nidoran-f",
    "Flabébé":      "flabebe",
    "Type: Null":   "type-null",
    "Jangmo-o":     "jangmo-o",
    "Hakamo-o":     "hakamo-o",
    "Kommo-o":      "kommo-o",
    "Tapu Koko":    "tapu-koko",
    "Tapu Lele":    "tapu-lele",
    "Tapu Bulu":    "tapu-bulu",
    "Tapu Fini":    "tapu-fini",
    "Ting-Lu":      "ting-lu",
    "Chien-Pao":    "chien-pao",
    "Wo-Chien":     "wo-chien",
    "Chi-Yu":       "chi-yu",
    "Flutter Mane": "flutter-mane",
    "Slither Wing": "slither-wing",
    "Sandy Shocks": "sandy-shocks",
    "Roaring Moon": "roaring-moon",
    "Great Tusk":   "great-tusk",
    "Scream Tail":  "scream-tail",
    "Brute Bonnet": "brute-bonnet",
    "Walking Wake": "walking-wake",
    "Gouging Fire": "gouging-fire",
    "Raging Bolt":  "raging-bolt",
    "Iron Valiant": "iron-valiant",
    "Iron Bundle":  "iron-bundle",
    "Iron Hands":   "iron-hands",
    "Iron Jugulis": "iron-jugulis",
    "Iron Moth":    "iron-moth",
    "Iron Thorns":  "iron-thorns",
    "Iron Treads":  "iron-treads",
    "Iron Leaves":  "iron-leaves",
    "Iron Boulder": "iron-boulder",
    "Iron Crown":   "iron-crown",
}


def to_api_name(name: str) -> str:
    if name in NAME_FIXES:
        return NAME_FIXES[name]
    return re.sub(r"[^a-z0-9-]", "", name.lower().replace(" ", "-").replace("'", "").replace(".", ""))


def main():
    path    = DATA_DIR / "pokemon.json"
    pokedex = json.loads(path.read_text(encoding="utf-8"))

    total = len(pokedex)
    updated = skipped = 0
    failed  = []

    for i, (name, entry) in enumerate(pokedex.items()):
        if "abilities" in entry:
            skipped += 1
            continue

        api_key = to_api_name(name)
        try:
            r = requests.get(POKEAPI.format(api_key), timeout=10)
            if r.status_code == 200:
                data      = r.json()
                abilities = [a["ability"]["name"].replace("-", " ").title()
                             for a in data["abilities"]]
                entry["abilities"] = abilities
                updated += 1
                print(f"[{i+1}/{total}] {name}: {abilities}")
            else:
                failed.append(name)
                print(f"[{i+1}/{total}] {name} 실패 (HTTP {r.status_code}, key={api_key})")
        except Exception as e:
            failed.append(name)
            print(f"[{i+1}/{total}] {name} 오류: {e}")

        time.sleep(0.25)

    path.write_text(json.dumps(pokedex, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n완료: 업데이트 {updated}개 / 스킵(이미있음) {skipped}개 / 실패 {len(failed)}개")
    if failed:
        print(f"실패 목록: {failed}")


if __name__ == "__main__":
    main()
