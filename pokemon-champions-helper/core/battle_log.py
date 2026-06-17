"""배틀 로그 추적 + 구애 아이템 추론"""

from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class PokemonLog:
    name: str
    observed_moves: list[str] = field(default_factory=list)  # 순서 있는 관찰 기록
    move_counts: dict = field(default_factory=lambda: defaultdict(int))
    item_confirmed: str | None = None
    item_flags: dict = field(default_factory=dict)  # {"choice": bool, ...}
    rank_changes: dict = field(default_factory=lambda: {
        "atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0, "acc": 0, "eva": 0
    })
    hp_pct: float = 100.0
    is_fainted: bool = False


class BattleLog:
    """
    배틀 중 관찰 정보를 누적하고 구애 아이템 여부를 추론.
    """

    CHOICE_ITEMS = {"Choice Scarf", "Choice Band", "Choice Specs"}

    def __init__(self):
        self.turn: int = 0
        self.opp: dict[str, PokemonLog] = {}
        self.my: dict[str, PokemonLog] = {}
        self.trick_room_active: bool = False
        self.trick_room_turns: int = 0

    def reset(self):
        self.__init__()

    # ── 조회/추가 ─────────────────────────────────────────────────────────────

    def _get_or_create(self, store: dict, name: str) -> PokemonLog:
        if name not in store:
            store[name] = PokemonLog(name=name)
        return store[name]

    def opp_used_move(self, pokemon: str, move: str):
        """상대 포켓몬이 기술을 사용했을 때 호출"""
        log = self._get_or_create(self.opp, pokemon)
        log.observed_moves.append(move)
        log.move_counts[move] += 1
        self._infer_choice(log)

    def my_used_move(self, pokemon: str, move: str):
        log = self._get_or_create(self.my, pokemon)
        log.observed_moves.append(move)
        log.move_counts[move] += 1

    def update_rank(self, side: str, pokemon: str, stat: str, delta: int):
        store = self.opp if side == "opp" else self.my
        log = self._get_or_create(store, pokemon)
        log.rank_changes[stat] = max(-6, min(6, log.rank_changes[stat] + delta))

    def update_hp(self, side: str, pokemon: str, pct: float):
        store = self.opp if side == "opp" else self.my
        log = self._get_or_create(store, pokemon)
        log.hp_pct = pct

    def confirm_item(self, side: str, pokemon: str, item: str):
        store = self.opp if side == "opp" else self.my
        log = self._get_or_create(store, pokemon)
        log.item_confirmed = item

    def next_turn(self):
        self.turn += 1
        if self.trick_room_active:
            self.trick_room_turns -= 1
            if self.trick_room_turns <= 0:
                self.trick_room_active = False

    def toggle_trick_room(self):
        if self.trick_room_active:
            self.trick_room_active = False
            self.trick_room_turns = 0
        else:
            self.trick_room_active = True
            self.trick_room_turns = 5

    # ── 구애 추론 ─────────────────────────────────────────────────────────────

    def _infer_choice(self, log: PokemonLog):
        """
        같은 기술 2회 이상 + 다른 기술 없음 → 구애 아이템 플래그
        다른 기술 관찰되면 플래그 해제
        """
        if log.item_confirmed:
            return
        unique_moves = set(log.observed_moves)
        if len(unique_moves) == 1 and list(log.move_counts.values())[0] >= 2:
            log.item_flags["possible_choice"] = True
        elif len(unique_moves) > 1:
            log.item_flags["possible_choice"] = False

    # ── 조회 ─────────────────────────────────────────────────────────────────

    def get_opp_summary(self, pokemon: str) -> dict:
        if pokemon not in self.opp:
            return {}
        log = self.opp[pokemon]
        return {
            "observed_moves": log.observed_moves,
            "unique_moves": list(log.move_counts.keys()),
            "possible_choice": log.item_flags.get("possible_choice", False),
            "item_confirmed": log.item_confirmed,
            "ranks": log.rank_changes,
            "hp_pct": log.hp_pct,
        }

    def get_all_opp_names(self) -> list[str]:
        return list(self.opp.keys())
