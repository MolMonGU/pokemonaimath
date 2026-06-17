"""파티 관리 + 6×6 유불리 그리드 계산"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from core.type_calc import party_coverage_matrix, weakness_summary

SAVES_DIR = Path(__file__).parent.parent / "saves" / "my_teams"
SAVES_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Pokemon:
    name: str
    name_ko: str = ""
    types: list[str] = field(default_factory=list)
    base_stats: dict = field(default_factory=dict)
    ev: dict = field(default_factory=lambda: {
        "hp": 0, "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0
    })
    iv: dict = field(default_factory=lambda: {
        "hp": 31, "atk": 31, "def": 31, "spa": 31, "spd": 31, "spe": 31
    })
    nature: str = "neutral"
    nature_stat: dict = field(default_factory=lambda: {"plus": None, "minus": None})
    moves: list[str] = field(default_factory=list)
    item: str = ""
    ability: str = ""
    level: int = 50


@dataclass
class Party:
    members: list[Pokemon] = field(default_factory=list)

    def add(self, poke: Pokemon):
        if len(self.members) < 6:
            self.members.append(poke)

    def remove(self, name: str):
        self.members = [p for p in self.members if p.name != name]

    def get(self, name: str) -> Pokemon | None:
        return next((p for p in self.members if p.name == name), None)

    def type_lists(self) -> list[list[str]]:
        return [p.types for p in self.members]

    def names(self) -> list[str]:
        return [p.name_ko or p.name for p in self.members]

    def to_dict(self) -> dict:
        return {
            "members": [
                {
                    "name": p.name, "name_ko": p.name_ko,
                    "types": p.types, "base_stats": p.base_stats,
                    "ev": p.ev, "iv": p.iv, "nature": p.nature,
                    "moves": p.moves, "item": p.item,
                    "ability": p.ability, "level": p.level,
                }
                for p in self.members
            ]
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Party":
        party = cls()
        for m in d.get("members", []):
            party.add(Pokemon(**m))
        return party

    def save(self, filename: str):
        path = SAVES_DIR / f"{filename}.json"
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, filename: str) -> "Party":
        path = SAVES_DIR / f"{filename}.json"
        if not path.exists():
            raise FileNotFoundError(f"{path} 없음")
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    @staticmethod
    def list_saves() -> list[str]:
        return [p.stem for p in SAVES_DIR.glob("*.json")]


def grid_score(my_party: Party, opp_party: Party) -> dict:
    """
    6×6 유불리 그리드 계산.
    반환: {
      "matrix": [[float]],         # 타입 배율 (내 6 × 상대 6)
      "my_names": [str],
      "opp_names": [str],
      "color": [["green"|"red"|"yellow"]],
    }
    """
    my_types = my_party.type_lists()
    opp_types = opp_party.type_lists()

    mat = party_coverage_matrix(my_types, opp_types)

    colors = []
    for row in mat:
        color_row = []
        for val in row:
            if val >= 2.0:
                color_row.append("green")
            elif val <= 0.5:
                color_row.append("red")
            else:
                color_row.append("yellow")
        colors.append(color_row)

    return {
        "matrix": mat.tolist(),
        "my_names": my_party.names(),
        "opp_names": opp_party.names(),
        "color": colors,
    }
