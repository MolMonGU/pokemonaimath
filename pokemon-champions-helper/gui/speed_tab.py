"""스피드 계산기 탭"""

import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QSpinBox, QPushButton, QCheckBox, QTextEdit, QGroupBox
)
from core.speed import calc_speed, min_ev_to_outspeed, speed_comparison, priority_order

DATA_DIR = Path(__file__).parent.parent / "data"
PRIORITY_MOVES: dict = {}


def _load_priority():
    global PRIORITY_MOVES
    p = DATA_DIR / "priority_moves.json"
    if p.exists():
        PRIORITY_MOVES = json.loads(p.read_text(encoding="utf-8"))


_load_priority()


class SpeedTab(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # ── 입력 그룹 ─────────────────────────────────────────────────────────
        grp = QGroupBox("스피드 계산")
        g = QHBoxLayout(grp)

        # 기본 스피드
        g.addWidget(QLabel("기본 스피드:"))
        self.spn_base = QSpinBox(); self.spn_base.setRange(1, 200); self.spn_base.setValue(100)
        g.addWidget(self.spn_base)

        # EV
        g.addWidget(QLabel("EV:"))
        self.spn_ev = QSpinBox(); self.spn_ev.setRange(0, 252); self.spn_ev.setSingleStep(4)
        g.addWidget(self.spn_ev)

        # IV
        g.addWidget(QLabel("IV:"))
        self.spn_iv = QSpinBox(); self.spn_iv.setRange(0, 31); self.spn_iv.setValue(31)
        g.addWidget(self.spn_iv)

        # 성격
        g.addWidget(QLabel("성격:"))
        self.cmb_nature = QComboBox()
        self.cmb_nature.addItems(["neutral", "plus", "minus"])
        g.addWidget(self.cmb_nature)

        # 랭크
        g.addWidget(QLabel("랭크:"))
        self.spn_rank = QSpinBox(); self.spn_rank.setRange(-6, 6)
        g.addWidget(self.spn_rank)

        root.addWidget(grp)

        # ── 조건 체크박스 ──────────────────────────────────────────────────────
        cond = QHBoxLayout()
        self.chk_scarf   = QCheckBox("구애스카프")
        self.chk_weather = QCheckBox("날씨특성 2×")
        self.chk_para    = QCheckBox("마비")
        self.chk_trick   = QCheckBox("트릭룸")
        for w in [self.chk_scarf, self.chk_weather, self.chk_para, self.chk_trick]:
            cond.addWidget(w)
        cond.addStretch()
        root.addLayout(cond)

        # ── 계산 버튼 ─────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_calc = QPushButton("계산")
        btn_calc.clicked.connect(self._calc)
        btn_row.addWidget(btn_calc)

        # 상대 스피드 비교
        btn_row.addWidget(QLabel("  상대 스피드:"))
        self.spn_opp = QSpinBox(); self.spn_opp.setRange(1, 1000); self.spn_opp.setValue(100)
        btn_row.addWidget(self.spn_opp)
        btn_cmp = QPushButton("선/후제 비교")
        btn_cmp.clicked.connect(self._compare)
        btn_row.addWidget(btn_cmp)
        btn_row.addStretch()
        root.addLayout(btn_row)

        # ── 결과 ──────────────────────────────────────────────────────────────
        self.result = QTextEdit()
        self.result.setReadOnly(True)
        self.result.setMaximumHeight(200)
        root.addWidget(self.result)
        root.addStretch()

    def _get_speed(self) -> int:
        return calc_speed(
            base_spe=self.spn_base.value(),
            ev=self.spn_ev.value(),
            iv=self.spn_iv.value(),
            nature=self.cmb_nature.currentText(),
            rank=self.spn_rank.value(),
            scarf=self.chk_scarf.isChecked(),
            weather_boost=self.chk_weather.isChecked(),
            paralysis=self.chk_para.isChecked(),
        )

    def _calc(self):
        spd = self._get_speed()
        lines = [f"실수치: {spd}"]

        # 역방향: target을 넘으려면 몇 EV?
        opp = self.spn_opp.value()
        min_ev = min_ev_to_outspeed(
            self.spn_base.value(), opp,
            iv=self.spn_iv.value(),
            nature=self.cmb_nature.currentText(),
            rank=self.spn_rank.value(),
            scarf=self.chk_scarf.isChecked(),
        )
        if min_ev is not None:
            lines.append(f"상대({opp}) 앞서려면 최소 EV: {min_ev}")
        else:
            lines.append(f"상대({opp})를 앞서는 것 불가")

        self.result.setPlainText("\n".join(lines))

    def _compare(self):
        my = self._get_speed()
        opp = self.spn_opp.value()
        trick = self.chk_trick.isChecked()
        result = speed_comparison(my, opp, trick)
        self.result.setPlainText(
            f"내 스피드: {my}  /  상대: {opp}\n결과: {result}"
        )

    def reset_ranks(self):
        self.spn_rank.setValue(0)
