"""대미지 계산기 탭"""

import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
    QComboBox, QPushButton, QCheckBox, QTextEdit, QGroupBox, QLineEdit
)
from core.damage import calc_damage, ohko_check
from core.type_calc import TYPES
from core.stat_calc import calc_lv50_stats, calc_stat, calc_hp, estimate_spread, _nature_mods

DATA_DIR = Path(__file__).parent.parent / "data"


def _load_pokemon_db() -> dict:
    p = DATA_DIR / "pokemon.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _load_smogon() -> dict:
    p = DATA_DIR / "smogon_sets.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _load_move_db() -> dict:
    p = DATA_DIR / "move_types.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _load_my_team() -> dict:
    """my_team.json + opp_team.json → {검색키: entry}"""
    result = {}
    for fname in ["my_team.json", "opp_team.json"]:
        p = DATA_DIR / fname
        if not p.exists():
            continue
        team = json.loads(p.read_text(encoding="utf-8"))
        for entry in team:
            for key in [entry.get("name", ""), entry.get("ocr_alias", ""), entry.get("name_kr", "")]:
                if key:
                    result[key.lower()] = entry
    return result


class DamageTab(QWidget):
    def __init__(self):
        super().__init__()
        self._poke_db = _load_pokemon_db()
        self._smogon  = _load_smogon()
        self._my_team = _load_my_team()
        self._move_db = _load_move_db()
        # EV 범위 계산용 베이스 저장
        self._atk_base: dict | None = None
        self._atk_nature: str = "Hardy"
        self._def_base: dict | None = None
        self._def_nature: str = "Hardy"
        self._build_ui()

    # ── 데이터 탐색 ──────────────────────────────────────────────────────────

    def _lookup(self, name: str) -> dict | None:
        """이름 → lv50 실수치 + 타입 + 베이스스탯/nature. my_team 우선, 없으면 Smogon 추정."""
        key = name.strip().lower()

        entry = self._my_team.get(key)
        if entry:
            base   = entry["pokedex_entry"]["base_stats"]
            evs    = entry.get("evs", {})
            nature = entry.get("nature", "Hardy")
            types  = entry["pokedex_entry"]["types"]
            moves  = entry.get("moves", [])
            src    = "내 팀" if evs else "상대 팀"
            return {
                "stats": calc_lv50_stats(base, evs, nature),
                "types": types,
                "src": src,
                "base": base,
                "nature": nature,
                "moves": moves,
            }

        poke_key = next((k for k in self._poke_db if k.lower() == key), None)
        if poke_key:
            data   = self._poke_db[poke_key]
            evs, nature = estimate_spread(self._smogon, poke_key)
            top_moves = [m["move"] for m in self._smogon.get(poke_key, {}).get("top_moves", [])[:4]]
            return {
                "stats": calc_lv50_stats(data["base_stats"], evs, nature),
                "types": data["types"],
                "src": "Smogon 추정",
                "base": data["base_stats"],
                "nature": nature,
                "moves": top_moves,
            }

        return None

    # ── UI 구성 ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)

        # 기술 선택 드롭다운 (포켓몬 자동입력 시 자동 채워짐)
        move_row = QHBoxLayout()
        move_row.addWidget(QLabel("기술:"))
        self.cmb_move = QComboBox()
        self.cmb_move.setFixedWidth(200)
        self.cmb_move.addItem("(포켓몬 먼저 선택)")
        self.cmb_move.currentIndexChanged.connect(self._on_move_selected)
        move_row.addWidget(self.cmb_move)
        self.lbl_move = QLabel("")
        self.lbl_move.setStyleSheet("font-size: 11px;")
        move_row.addWidget(self.lbl_move)
        move_row.addStretch()
        root.addLayout(move_row)

        # 물리 / 특수 (기술 선택 시 자동 변경됨)
        cat_row = QHBoxLayout()
        cat_row.addWidget(QLabel("기술 카테고리:"))
        self.cmb_cat = QComboBox()
        self.cmb_cat.addItems(["물리", "특수"])
        cat_row.addWidget(self.cmb_cat)
        cat_row.addStretch()
        root.addLayout(cat_row)

        # ── 공격 측 ──────────────────────────────────────────────────────────
        atk_grp = QGroupBox("공격 측")
        ag = QVBoxLayout(atk_grp)

        name_a = QHBoxLayout()
        name_a.addWidget(QLabel("포켓몬:"))
        self.edit_atk = QLineEdit()
        self.edit_atk.setPlaceholderText("예: Charizard-Mega-Y 또는 리자몽")
        self.edit_atk.setFixedWidth(210)
        self.edit_atk.returnPressed.connect(lambda: self._auto_fill("atk"))
        name_a.addWidget(self.edit_atk)
        btn_a = QPushButton("자동입력")
        btn_a.setFixedWidth(70)
        btn_a.clicked.connect(lambda: self._auto_fill("atk"))
        name_a.addWidget(btn_a)
        self.lbl_atk = QLabel("")
        self.lbl_atk.setStyleSheet("font-size: 11px;")
        name_a.addWidget(self.lbl_atk)
        name_a.addStretch()
        ag.addLayout(name_a)

        stat_a = QHBoxLayout()
        stat_a.addWidget(QLabel("공격(특공):"))
        self.spn_atk = QSpinBox(); self.spn_atk.setRange(1, 500); self.spn_atk.setValue(100)
        stat_a.addWidget(self.spn_atk)

        stat_a.addWidget(QLabel("랭크:"))
        self.spn_atk_rank = QSpinBox(); self.spn_atk_rank.setRange(-6, 6)
        stat_a.addWidget(self.spn_atk_rank)

        stat_a.addWidget(QLabel("기술 위력:"))
        self.spn_power = QSpinBox(); self.spn_power.setRange(1, 300); self.spn_power.setValue(80)
        stat_a.addWidget(self.spn_power)

        stat_a.addWidget(QLabel("기술 타입:"))
        self.cmb_move_type = QComboBox(); self.cmb_move_type.addItems(TYPES)
        stat_a.addWidget(self.cmb_move_type)

        stat_a.addWidget(QLabel("공격자 타입:"))
        self.cmb_atk_type1 = QComboBox(); self.cmb_atk_type1.addItems(["(없음)"] + TYPES)
        self.cmb_atk_type2 = QComboBox(); self.cmb_atk_type2.addItems(["(없음)"] + TYPES)
        stat_a.addWidget(self.cmb_atk_type1); stat_a.addWidget(self.cmb_atk_type2)
        stat_a.addStretch()
        ag.addLayout(stat_a)
        root.addWidget(atk_grp)

        # ── 방어 측 ──────────────────────────────────────────────────────────
        def_grp = QGroupBox("방어 측")
        dg = QVBoxLayout(def_grp)

        name_d = QHBoxLayout()
        name_d.addWidget(QLabel("포켓몬:"))
        self.edit_def = QLineEdit()
        self.edit_def.setPlaceholderText("예: Garchomp")
        self.edit_def.setFixedWidth(210)
        self.edit_def.returnPressed.connect(lambda: self._auto_fill("def"))
        name_d.addWidget(self.edit_def)
        btn_d = QPushButton("자동입력")
        btn_d.setFixedWidth(70)
        btn_d.clicked.connect(lambda: self._auto_fill("def"))
        name_d.addWidget(btn_d)
        self.lbl_def = QLabel("")
        self.lbl_def.setStyleSheet("font-size: 11px;")
        name_d.addWidget(self.lbl_def)
        name_d.addStretch()
        dg.addLayout(name_d)

        stat_d = QHBoxLayout()
        stat_d.addWidget(QLabel("방어(특방):"))
        self.spn_def = QSpinBox(); self.spn_def.setRange(1, 500); self.spn_def.setValue(100)
        stat_d.addWidget(self.spn_def)

        stat_d.addWidget(QLabel("랭크:"))
        self.spn_def_rank = QSpinBox(); self.spn_def_rank.setRange(-6, 6)
        stat_d.addWidget(self.spn_def_rank)

        stat_d.addWidget(QLabel("HP:"))
        self.spn_hp = QSpinBox(); self.spn_hp.setRange(1, 714); self.spn_hp.setValue(252)
        stat_d.addWidget(self.spn_hp)

        stat_d.addWidget(QLabel("현재 HP:"))
        self.spn_cur_hp = QSpinBox(); self.spn_cur_hp.setRange(1, 714); self.spn_cur_hp.setValue(252)
        stat_d.addWidget(self.spn_cur_hp)

        stat_d.addWidget(QLabel("방어 타입:"))
        self.cmb_def_type1 = QComboBox(); self.cmb_def_type1.addItems(["(없음)"] + TYPES)
        self.cmb_def_type2 = QComboBox(); self.cmb_def_type2.addItems(["(없음)"] + TYPES)
        stat_d.addWidget(self.cmb_def_type1); stat_d.addWidget(self.cmb_def_type2)
        stat_d.addStretch()
        dg.addLayout(stat_d)
        root.addWidget(def_grp)

        # ── 스왑 버튼 ─────────────────────────────────────────────────────────
        swap_row = QHBoxLayout()
        btn_swap = QPushButton("⇅ 공격/방어 바꾸기")
        btn_swap.clicked.connect(self._swap_sides)
        swap_row.addWidget(btn_swap)
        swap_row.addStretch()
        root.addLayout(swap_row)

        # ── 옵션 + 계산 버튼 ──────────────────────────────────────────────────
        opt = QHBoxLayout()
        self.chk_crit  = QCheckBox("급소")
        self.chk_burn  = QCheckBox("화상")
        self.cmb_weather = QComboBox()
        self.cmb_weather.addItems(["날씨 없음 (×1.0)", "쾌청/우천 강화 (×1.5)", "쾌청/우천 약화 (×0.5)"])
        opt.addWidget(self.chk_crit); opt.addWidget(self.chk_burn)
        opt.addWidget(QLabel("날씨:")); opt.addWidget(self.cmb_weather)
        btn_calc = QPushButton("계산")
        btn_calc.clicked.connect(self._calc)
        opt.addWidget(btn_calc)
        opt.addStretch()
        root.addLayout(opt)

        # ── 결과 ──────────────────────────────────────────────────────────────
        self.result = QTextEdit(); self.result.setReadOnly(True); self.result.setMaximumHeight(160)
        root.addWidget(self.result)
        root.addStretch()

    # ── 슬롯 ─────────────────────────────────────────────────────────────────

    def _swap_sides(self):
        """공격/방어 포켓몬 이름 교체 후 자동입력 재실행"""
        atk_name = self.edit_atk.text()
        def_name = self.edit_def.text()
        self.edit_atk.setText(def_name)
        self.edit_def.setText(atk_name)
        if def_name:
            self._auto_fill("atk")
        if atk_name:
            self._auto_fill("def")

    def _populate_moves(self, moves: list[str]):
        """포켓몬의 기술 목록으로 드롭다운 채우기"""
        self.cmb_move.blockSignals(True)
        self.cmb_move.clear()
        for move in moves:
            data = self._move_db.get(move.lower().replace(" ", ""))
            if data:
                cat_kr = "물리" if data["cat"] == "Physical" else "특수"
                label = f"{move}  ({data['type']} / {cat_kr} / {data['bp']}BP)"
            else:
                label = move
            self.cmb_move.addItem(label, userData=move)
        self.cmb_move.blockSignals(False)
        if self.cmb_move.count() > 0:
            self.cmb_move.setCurrentIndex(0)
            self._on_move_selected(0)

    def _on_move_selected(self, idx: int):
        """드롭다운에서 기술 선택 시 위력/타입/카테고리 자동 적용"""
        move = self.cmb_move.currentData()
        if not move:
            return
        data = self._move_db.get(move.lower().replace(" ", ""))
        if not data:
            self.lbl_move.setText("❌ 데이터 없음")
            self.lbl_move.setStyleSheet("color: #f38ba8; font-size: 11px;")
            return

        bp  = data.get("bp", 0)
        cat = data.get("cat", "")
        typ = data.get("type", "")

        if bp > 0:
            self.spn_power.setValue(bp)
        type_idx = self.cmb_move_type.findText(typ)
        if type_idx >= 0:
            self.cmb_move_type.setCurrentIndex(type_idx)
        if cat == "Physical":
            self.cmb_cat.setCurrentIndex(0)
        elif cat == "Special":
            self.cmb_cat.setCurrentIndex(1)

        cat_kr = "물리" if cat == "Physical" else ("특수" if cat == "Special" else cat)
        self.lbl_move.setText(f"{typ} / {cat_kr} / {bp}BP")
        self.lbl_move.setStyleSheet("color: #a6e3a1; font-size: 11px;")

    def _auto_fill(self, side: str):
        physical = self.cmb_cat.currentText() == "물리"
        name = (self.edit_atk if side == "atk" else self.edit_def).text()
        res = self._lookup(name)

        if res is None:
            lbl = self.lbl_atk if side == "atk" else self.lbl_def
            lbl.setText("❌ 못 찾음")
            lbl.setStyleSheet("color: #f38ba8; font-size: 11px;")
            return

        s = res["stats"]
        types = res["types"]
        src = res["src"]

        moves = res.get("moves", [])

        if side == "atk":
            self._atk_base   = res["base"]
            self._atk_nature = res["nature"]
            self.spn_atk.setValue(s["atk"] if physical else s["spa"])
            self._fill_types(self.cmb_atk_type1, self.cmb_atk_type2, types)
            self.lbl_atk.setText(f"ATK {s['atk']} / SPA {s['spa']}  [{src}]")
            self.lbl_atk.setStyleSheet("color: #a6e3a1; font-size: 11px;")
            if moves:
                self._populate_moves(moves)
        else:
            self._def_base   = res["base"]
            self._def_nature = res["nature"]
            self.spn_def.setValue(s["def"] if physical else s["spd"])
            self.spn_hp.setValue(s["hp"])
            self.spn_cur_hp.setValue(s["hp"])
            self._fill_types(self.cmb_def_type1, self.cmb_def_type2, types)
            self.lbl_def.setText(f"HP {s['hp']} / DEF {s['def']} / SPD {s['spd']}  [{src}]")
            self.lbl_def.setStyleSheet("color: #a6e3a1; font-size: 11px;")

    def _fill_types(self, cmb1: QComboBox, cmb2: QComboBox, types: list[str]):
        cmb1.setCurrentIndex(max(0, cmb1.findText(types[0])) if types else 0)
        cmb2.setCurrentIndex(cmb2.findText(types[1]) if len(types) > 1 else 0)

    def _get_types(self, cmb1, cmb2) -> list[str]:
        return [c.currentText() for c in [cmb1, cmb2] if c.currentText() != "(없음)"]

    def _ev_stat(self, base: dict, nature: str, stat_key: str, ev: int) -> int:
        """특정 EV로 lv50 실수치 계산"""
        mods = _nature_mods(nature)
        b = base.get(stat_key, 50)
        if stat_key == "hp":
            return calc_hp(b, ev=ev)
        return calc_stat(b, ev=ev, nature=mods[stat_key])

    def _calc(self):
        physical = self.cmb_cat.currentText() == "물리"
        atk_key  = "atk" if physical else "spa"
        def_key  = "def" if physical else "spd"
        weather_map = {0: 1.0, 1: 1.5, 2: 0.5}
        weather  = weather_map[self.cmb_weather.currentIndex()]
        move_type = self.cmb_move_type.currentText()
        atk_types = self._get_types(self.cmb_atk_type1, self.cmb_atk_type2)
        def_types = self._get_types(self.cmb_def_type1, self.cmb_def_type2)
        power    = self.spn_power.value()
        atk_rank = self.spn_atk_rank.value()
        def_rank = self.spn_def_rank.value()
        is_crit  = self.chk_crit.isChecked()
        burn     = self.chk_burn.isChecked()

        # EV 케이스 목록 구성
        # 자동입력 됐으면 0/252 두 케이스, 아니면 현재 스핀박스 값 단일
        if self._atk_base and self._def_base:
            cases = [
                ("최선 (내 252EV × 상대 0EV)",
                 self._ev_stat(self._atk_base, self._atk_nature, atk_key, 252),
                 self._ev_stat(self._def_base, self._def_nature, def_key, 0),
                 self._ev_stat(self._def_base, self._def_nature, "hp", 0)),
                ("최악 (내 0EV  × 상대 252EV)",
                 self._ev_stat(self._atk_base, self._atk_nature, atk_key, 0),
                 self._ev_stat(self._def_base, self._def_nature, def_key, 252),
                 self._ev_stat(self._def_base, self._def_nature, "hp", 252)),
            ]
        elif self._def_base:
            atk_val = self.spn_atk.value()
            cases = [
                ("상대 0EV",
                 atk_val,
                 self._ev_stat(self._def_base, self._def_nature, def_key, 0),
                 self._ev_stat(self._def_base, self._def_nature, "hp", 0)),
                ("상대 252EV",
                 atk_val,
                 self._ev_stat(self._def_base, self._def_nature, def_key, 252),
                 self._ev_stat(self._def_base, self._def_nature, "hp", 252)),
            ]
        elif self._atk_base:
            def_val = self.spn_def.value()
            hp_val  = self.spn_hp.value()
            cases = [
                ("내 252EV",
                 self._ev_stat(self._atk_base, self._atk_nature, atk_key, 252),
                 def_val, hp_val),
                ("내 0EV",
                 self._ev_stat(self._atk_base, self._atk_nature, atk_key, 0),
                 def_val, hp_val),
            ]
        else:
            cases = [
                ("현재 입력값",
                 self.spn_atk.value(),
                 self.spn_def.value(),
                 self.spn_hp.value()),
            ]

        # 타입 배율은 공통
        from core.type_calc import move_effectiveness
        type_mul = move_effectiveness(move_type, def_types)
        type_label = {4.0:"4배", 2.0:"2배", 1.0:"보통", 0.5:"반감",
                      0.25:"1/4", 0.0:"무효"}.get(type_mul, f"×{type_mul}")

        lines = [f"타입 배율: {type_label}", ""]
        for label, atk_val, def_val, hp_val in cases:
            res = calc_damage(
                level=50, power=power,
                atk=atk_val, atk_rank=atk_rank,
                def_=def_val, def_rank=def_rank,
                move_type=move_type,
                attacker_types=atk_types,
                defender_types=def_types,
                weather=weather, is_crit=is_crit, burn=burn,
            )
            ko = ohko_check(res, hp_val, hp_val)
            ohko = "확정" if ko["guaranteed"] else ("가능" if ko["can_ohko"] else "불가")
            lines += [
                f"[{label}]  ATK={atk_val} DEF={def_val} HP={hp_val}",
                f"  대미지: {res['min']}~{res['max']}  {ko['min_pct']}%~{ko['max_pct']}%  처치:{ohko}({ko['pct']}%)",
            ]

        self.result.setPlainText("\n".join(lines))

    def set_my_pokemon(self, name: str):
        self.edit_atk.setText(name)
        self._auto_fill("atk")

    def set_opp_pokemon(self, name: str):
        self.edit_def.setText(name)
        self._auto_fill("def")

    def reset_ranks(self):
        self.spn_atk_rank.setValue(0)
        self.spn_def_rank.setValue(0)
