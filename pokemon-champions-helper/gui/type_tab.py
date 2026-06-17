"""타입 상성 분석 탭"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QTextEdit, QGroupBox
)
from core.type_calc import TYPES, weakness_summary, move_effectiveness


class TypeTab(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        grp = QGroupBox("포켓몬 타입 입력")
        g = QHBoxLayout(grp)

        g.addWidget(QLabel("타입1:"))
        self.cmb1 = QComboBox(); self.cmb1.addItems(TYPES)
        g.addWidget(self.cmb1)

        g.addWidget(QLabel("타입2:"))
        self.cmb2 = QComboBox(); self.cmb2.addItems(["(없음)"] + TYPES)
        g.addWidget(self.cmb2)

        btn = QPushButton("약점 분석")
        btn.clicked.connect(self._analyze)
        g.addWidget(btn)
        g.addStretch()
        root.addWidget(grp)

        # 기술 vs 타입 단일 계산
        grp2 = QGroupBox("기술 타입 vs 방어 타입")
        g2 = QHBoxLayout(grp2)
        g2.addWidget(QLabel("기술 타입:"))
        self.cmb_move = QComboBox(); self.cmb_move.addItems(TYPES)
        g2.addWidget(self.cmb_move)
        btn2 = QPushButton("배율 계산")
        btn2.clicked.connect(self._single_calc)
        g2.addWidget(btn2)
        g2.addStretch()
        root.addWidget(grp2)

        self.result = QTextEdit(); self.result.setReadOnly(True)
        root.addWidget(self.result)

    def _get_types(self) -> list[str]:
        types = [self.cmb1.currentText()]
        t2 = self.cmb2.currentText()
        if t2 != "(없음)":
            types.append(t2)
        return types

    def _analyze(self):
        def_types = self._get_types()
        ws = weakness_summary(def_types)
        lines = [f"방어 타입: {' / '.join(def_types)}", ""]
        labels = {"4x":"4배 약점", "2x":"2배 약점", "0.5x":"반감", "0.25x":"1/4 저항", "0x":"무효"}
        for key, label in labels.items():
            moves = ws[key]
            if moves:
                lines.append(f"{label}: {', '.join(moves)}")
        self.result.setPlainText("\n".join(lines))

    def _single_calc(self):
        move_type = self.cmb_move.currentText()
        def_types = self._get_types()
        mul = move_effectiveness(move_type, def_types)
        label = {4.0:"4배", 2.0:"2배", 1.0:"보통", 0.5:"반감", 0.25:"1/4", 0.0:"무효"}.get(mul, f"×{mul}")
        self.result.setPlainText(
            f"{move_type} → {' / '.join(def_types)}\n배율: {label} (×{mul})"
        )
