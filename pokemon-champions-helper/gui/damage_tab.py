"""대미지 계산기 탭"""

import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
    QComboBox, QPushButton, QCheckBox, QTextEdit, QGroupBox, QLineEdit
)
from core.damage import calc_damage, ohko_check
from core.type_calc import TYPES
from core.stat_calc import calc_lv50_stats, estimate_spread

DATA_DIR = Path(__file__).parent.parent / "data"


def _load_pokemon_db() -> dict:
    p = DATA_DIR / "pokemon.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _load_smogon() -> dict:
    p = DATA_DIR / "smogon_sets.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _load_my_team() -> dict:
    """my_team.json → {검색키: entry} (name / ocr_alias / name_kr 모두 등록)"""
    p = DATA_DIR / "my_team.json"
    if not p.exists():
        return {}
    team = json.loads(p.read_text(encoding="utf-8"))
    result = {}
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
        self._build_ui()

    # ── 데이터 탐색 ──────────────────────────────────────────────────────────

    def _lookup(self, name: str) -> dict | None:
        """이름 → lv50 실수치 + 타입. my_team 우선, 없으면 Smogon 추정."""
        key = name.strip().lower()

        entry = self._my_team.get(key)
        if entry:
            base  = entry["pokedex_entry"]["base_stats"]
            evs   = entry["evs"]
            nature = entry["nature"]
            types = entry["pokedex_entry"]["types"]
            return {"stats": calc_lv50_stats(base, evs, nature), "types": types, "src": "내 팀"}

        poke_key = next((k for k in self._poke_db if k.lower() == key), None)
        if poke_key:
            data   = self._poke_db[poke_key]
            evs, nature = estimate_spread(self._smogon, poke_key)
            return {
                "stats": calc_lv50_stats(data["base_stats"], evs, nature),
                "types": data["types"],
                "src": "Smogon 추정",
            }

        return None

    # ── UI 구성 ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)

        # 물리 / 특수 선택
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

        if side == "atk":
            self.spn_atk.setValue(s["atk"] if physical else s["spa"])
            self._fill_types(self.cmb_atk_type1, self.cmb_atk_type2, types)
            self.lbl_atk.setText(f"ATK {s['atk']} / SPA {s['spa']}  [{src}]")
            self.lbl_atk.setStyleSheet("color: #a6e3a1; font-size: 11px;")
        else:
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

    def _calc(self):
        weather_map = {0: 1.0, 1: 1.5, 2: 0.5}
        res = calc_damage(
            level=50,
            power=self.spn_power.value(),
            atk=self.spn_atk.value(),
            atk_rank=self.spn_atk_rank.value(),
            def_=self.spn_def.value(),
            def_rank=self.spn_def_rank.value(),
            move_type=self.cmb_move_type.currentText(),
            attacker_types=self._get_types(self.cmb_atk_type1, self.cmb_atk_type2),
            defender_types=self._get_types(self.cmb_def_type1, self.cmb_def_type2),
            weather=weather_map[self.cmb_weather.currentIndex()],
            is_crit=self.chk_crit.isChecked(),
            burn=self.chk_burn.isChecked(),
        )
        ko = ohko_check(res, self.spn_hp.value(), self.spn_cur_hp.value())
        type_label = {4.0:"4배", 2.0:"2배", 1.0:"보통", 0.5:"반감", 0.25:"1/4", 0.0:"무효"}.get(
            res["type_effectiveness"], f"×{res['type_effectiveness']}"
        )
        self.result.setPlainText("\n".join([
            f"타입 배율: {type_label}",
            f"대미지: {res['min']} ~ {res['max']}  (평균 {res['avg']})",
            f"비율: {ko['min_pct']}% ~ {ko['max_pct']}%",
            "",
            f"처치 가능: {'예' if ko['can_ohko'] else '아니오'}",
            f"확정 처치: {'예' if ko['guaranteed'] else '아니오'}  ({ko['pct']}% 확률)",
        ]))

    def reset_ranks(self):
        self.spn_atk_rank.setValue(0)
        self.spn_def_rank.setValue(0)
