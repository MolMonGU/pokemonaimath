"""대미지 계산기 탭"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
    QComboBox, QPushButton, QCheckBox, QTextEdit, QGroupBox
)
from core.damage import calc_damage, ohko_check
from core.type_calc import TYPES

NATURES = ["neutral", "plus", "minus"]


class DamageTab(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)

        # ── 공격 측 ───────────────────────────────────────────────────────────
        atk_grp = QGroupBox("공격 측")
        ag = QHBoxLayout(atk_grp)

        ag.addWidget(QLabel("공격(특공):"))
        self.spn_atk = QSpinBox(); self.spn_atk.setRange(1, 500); self.spn_atk.setValue(100)
        ag.addWidget(self.spn_atk)

        ag.addWidget(QLabel("랭크:"))
        self.spn_atk_rank = QSpinBox(); self.spn_atk_rank.setRange(-6, 6)
        ag.addWidget(self.spn_atk_rank)

        ag.addWidget(QLabel("기술 위력:"))
        self.spn_power = QSpinBox(); self.spn_power.setRange(1, 300); self.spn_power.setValue(80)
        ag.addWidget(self.spn_power)

        ag.addWidget(QLabel("기술 타입:"))
        self.cmb_move_type = QComboBox()
        self.cmb_move_type.addItems(TYPES)
        ag.addWidget(self.cmb_move_type)

        ag.addWidget(QLabel("공격자 타입:"))
        self.cmb_atk_type1 = QComboBox(); self.cmb_atk_type1.addItems(["(없음)"] + TYPES)
        self.cmb_atk_type2 = QComboBox(); self.cmb_atk_type2.addItems(["(없음)"] + TYPES)
        ag.addWidget(self.cmb_atk_type1); ag.addWidget(self.cmb_atk_type2)

        root.addWidget(atk_grp)

        # ── 방어 측 ───────────────────────────────────────────────────────────
        def_grp = QGroupBox("방어 측")
        dg = QHBoxLayout(def_grp)

        dg.addWidget(QLabel("방어(특방):"))
        self.spn_def = QSpinBox(); self.spn_def.setRange(1, 500); self.spn_def.setValue(100)
        dg.addWidget(self.spn_def)

        dg.addWidget(QLabel("랭크:"))
        self.spn_def_rank = QSpinBox(); self.spn_def_rank.setRange(-6, 6)
        dg.addWidget(self.spn_def_rank)

        dg.addWidget(QLabel("HP:"))
        self.spn_hp = QSpinBox(); self.spn_hp.setRange(1, 714); self.spn_hp.setValue(252)
        dg.addWidget(self.spn_hp)

        dg.addWidget(QLabel("현재 HP:"))
        self.spn_cur_hp = QSpinBox(); self.spn_cur_hp.setRange(1, 714); self.spn_cur_hp.setValue(252)
        dg.addWidget(self.spn_cur_hp)

        dg.addWidget(QLabel("방어 타입:"))
        self.cmb_def_type1 = QComboBox(); self.cmb_def_type1.addItems(["(없음)"] + TYPES)
        self.cmb_def_type2 = QComboBox(); self.cmb_def_type2.addItems(["(없음)"] + TYPES)
        dg.addWidget(self.cmb_def_type1); dg.addWidget(self.cmb_def_type2)

        root.addWidget(def_grp)

        # ── 옵션 ──────────────────────────────────────────────────────────────
        opt = QHBoxLayout()
        self.chk_crit  = QCheckBox("급소")
        self.chk_burn  = QCheckBox("화상")
        self.cmb_weather = QComboBox()
        self.cmb_weather.addItems(["날씨 없음 (×1.0)", "쾌청/우천 강화 (×1.5)", "쾌청/우천 약화 (×0.5)"])
        opt.addWidget(self.chk_crit); opt.addWidget(self.chk_burn)
        opt.addWidget(QLabel("날씨:"))
        opt.addWidget(self.cmb_weather)

        btn = QPushButton("계산")
        btn.clicked.connect(self._calc)
        opt.addWidget(btn)
        opt.addStretch()
        root.addLayout(opt)

        # ── 결과 ──────────────────────────────────────────────────────────────
        self.result = QTextEdit(); self.result.setReadOnly(True); self.result.setMaximumHeight(160)
        root.addWidget(self.result)
        root.addStretch()

    def _get_types(self, cmb1, cmb2) -> list[str]:
        types = []
        for c in [cmb1, cmb2]:
            t = c.currentText()
            if t != "(없음)":
                types.append(t)
        return types

    def _calc(self):
        weather_map = {0: 1.0, 1: 1.5, 2: 0.5}
        weather = weather_map[self.cmb_weather.currentIndex()]

        atk_types = self._get_types(self.cmb_atk_type1, self.cmb_atk_type2)
        def_types = self._get_types(self.cmb_def_type1, self.cmb_def_type2)
        move_type = self.cmb_move_type.currentText()

        res = calc_damage(
            level=50,
            power=self.spn_power.value(),
            atk=self.spn_atk.value(),
            atk_rank=self.spn_atk_rank.value(),
            def_=self.spn_def.value(),
            def_rank=self.spn_def_rank.value(),
            move_type=move_type,
            attacker_types=atk_types,
            defender_types=def_types,
            weather=weather,
            is_crit=self.chk_crit.isChecked(),
            burn=self.chk_burn.isChecked(),
        )

        ko = ohko_check(res, self.spn_hp.value(), self.spn_cur_hp.value())
        type_label = {4.0:"4배", 2.0:"2배", 1.0:"보통", 0.5:"반감", 0.25:"1/4", 0.0:"무효"}.get(
            res["type_effectiveness"], f"×{res['type_effectiveness']}"
        )

        lines = [
            f"타입 배율: {type_label}",
            f"대미지: {res['min']} ~ {res['max']}  (평균 {res['avg']})",
            f"비율: {ko['min_pct']}% ~ {ko['max_pct']}%",
            "",
            f"처치 가능: {'예' if ko['can_ohko'] else '아니오'}",
            f"확정 처치: {'예' if ko['guaranteed'] else '아니오'}  ({ko['pct']}% 확률)",
        ]
        self.result.setPlainText("\n".join(lines))

    def reset_ranks(self):
        self.spn_atk_rank.setValue(0)
        self.spn_def_rank.setValue(0)
