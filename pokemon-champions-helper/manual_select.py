"""
포켓몬 수동 선택 패널
overlay_main.py 실행 시 별도 창으로 자동 실행됨

내 포켓몬 버튼 클릭 → 행동 추천 패널 즉시 갱신
상대 포켓몬 입력 → 타입/SPE/상성 패널 즉시 갱신
"""
import json
import tkinter as tk
from tkinter import ttk
import threading
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

BG       = "#1e1e2e"
FG       = "#cdd6f4"
BTN_BG   = "#313244"
BTN_SEL  = "#89b4fa"
BTN_SEL_FG = "#1e1e2e"
GREEN    = "#a6e3a1"
BLUE     = "#89b4fa"
YELLOW   = "#f9e2af"
RED      = "#f38ba8"
FONT     = ("맑은 고딕", 9)
FONT_B   = ("맑은 고딕", 10, "bold")


def _load_my_team() -> list[dict]:
    path = DATA_DIR / "my_team.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _load_all_pokemon_names() -> list[str]:
    names: set[str] = set()
    for fname in ("pokemon.json", "smogon_sets.json"):
        path = DATA_DIR / fname
        if path.exists():
            names.update(json.loads(path.read_text(encoding="utf-8")).keys())
    return sorted(names)


class ManualSelectPanel:
    def __init__(self, state):
        self.state = state
        self.team = _load_my_team()
        self.all_pokemon = _load_all_pokemon_names()
        self._selected_my_idx: int | None = None
        self._my_buttons: list[tk.Button] = []
        self.root: tk.Tk | None = None

    # ── 시작 ──────────────────────────────────────────────────────────────────

    def start(self):
        self.root = tk.Tk()
        self.root.title("포켓몬 선택")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self._build()
        self.root.mainloop()

    # ── UI 구성 ───────────────────────────────────────────────────────────────

    def _build(self):
        root = self.root
        pad = {"padx": 6, "pady": 3}

        # ── 내 포켓몬 ──────────────────────────────────────────────────────────
        tk.Label(root, text="▶ 내 포켓몬", bg=BG, fg=GREEN, font=FONT_B).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=8, pady=(10, 2))

        for i, p in enumerate(self.team):
            row = 1 + i // 3
            col = i % 3
            btn = tk.Button(
                root, text=p["name_kr"], width=9, height=2,
                bg=BTN_BG, fg=FG, activebackground=BTN_SEL,
                font=FONT, relief="flat",
                command=lambda idx=i: self._select_my(idx)
            )
            btn.grid(row=row, column=col, **pad)
            self._my_buttons.append(btn)

        self._my_info = tk.Label(root, text="선택 안 됨", bg=BG, fg=YELLOW, font=FONT)
        self._my_info.grid(row=3, column=0, columnspan=3, pady=(0, 4))

        ttk.Separator(root, orient="horizontal").grid(
            row=4, column=0, columnspan=3, sticky="ew", padx=8, pady=4)

        # ── 상대 포켓몬 ────────────────────────────────────────────────────────
        tk.Label(root, text="▶ 상대 포켓몬", bg=BG, fg=BLUE, font=FONT_B).grid(
            row=5, column=0, columnspan=3, sticky="w", padx=8, pady=(2, 2))

        self._opp_var = tk.StringVar()
        combo = ttk.Combobox(root, textvariable=self._opp_var,
                             values=self.all_pokemon, width=18, font=FONT)
        combo.grid(row=6, column=0, columnspan=2, padx=6, pady=3, sticky="w")
        combo.bind("<<ComboboxSelected>>", self._select_opp)
        combo.bind("<Return>", self._select_opp)

        tk.Button(root, text="확인", width=5, bg=BTN_BG, fg=FG,
                  font=FONT, relief="flat",
                  command=self._select_opp).grid(row=6, column=2, **pad)

        self._opp_info = tk.Label(root, text="선택 안 됨", bg=BG, fg=RED, font=FONT)
        self._opp_info.grid(row=7, column=0, columnspan=3, pady=(0, 4))

        ttk.Separator(root, orient="horizontal").grid(
            row=8, column=0, columnspan=3, sticky="ew", padx=8, pady=4)

        # ── 유틸 버튼 ──────────────────────────────────────────────────────────
        btn_frame = tk.Frame(root, bg=BG)
        btn_frame.grid(row=9, column=0, columnspan=3, pady=(0, 8))

        tk.Button(btn_frame, text="관찰기술+랭크 초기화", width=16,
                  bg="#45475a", fg=FG, font=FONT, relief="flat",
                  command=self._reset_opp).pack(side="left", padx=4)

        tk.Button(btn_frame, text="내 랭크 초기화", width=12,
                  bg="#45475a", fg=FG, font=FONT, relief="flat",
                  command=self._reset_my).pack(side="left", padx=4)

    # ── 이벤트 ────────────────────────────────────────────────────────────────

    def _select_my(self, idx: int):
        p = self.team[idx]
        self.state.my_pokemon = p["name"]
        self.state.my_moves = list(p["moves"])

        for i, btn in enumerate(self._my_buttons):
            if i == idx:
                btn.configure(bg=BTN_SEL, fg=BTN_SEL_FG)
            else:
                btn.configure(bg=BTN_BG, fg=FG)

        self._selected_my_idx = idx
        item = p.get("item", "")
        self._my_info.configure(text=f"{p['name_kr']}  [{item}]")

    def _select_opp(self, event=None):
        name = self._opp_var.get().strip()
        if not name:
            return
        prev = self.state.opp_pokemon
        self.state.opp_pokemon = name
        if name != prev:
            self.state.observed_opp_moves.clear()
            self.state.reset_stages("opp")
            self.state._cache_item_pred = ("", "", [])
            self.state._cache_opp_moves = ("", [])
        self._opp_info.configure(text=name)

    def _reset_opp(self):
        self.state.observed_opp_moves.clear()
        self.state._cache_item_pred = ("", "", [])
        self.state.reset_stages("opp")

    def _reset_my(self):
        self.state.reset_stages("my")


# ── 외부 호출용 ───────────────────────────────────────────────────────────────

def start_panel_thread(state) -> threading.Thread:
    """overlay_main.py에서 호출 — 백그라운드 스레드로 패널 실행"""
    t = threading.Thread(
        target=lambda: ManualSelectPanel(state).start(),
        daemon=True
    )
    t.start()
    return t
