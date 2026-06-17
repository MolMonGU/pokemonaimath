"""6×6 유불리 그리드 탭"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QComboBox, QPushButton, QGroupBox, QFrame
)
from PyQt6.QtCore import Qt
from core.type_calc import TYPES
from core.party import Party, Pokemon, grid_score


COLOR_MAP = {
    "green":  "#a6e3a1",
    "red":    "#f38ba8",
    "yellow": "#f9e2af",
}


class GridTab(QWidget):
    def __init__(self):
        super().__init__()
        self._my_types:  list[list[str]] = [["Normal"]] * 6
        self._opp_types: list[list[str]] = [["Normal"]] * 6
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)

        # ── 파티 입력 ─────────────────────────────────────────────────────────
        party_row = QHBoxLayout()

        my_grp = QGroupBox("내 파티 타입 (각 6마리)")
        mg = QGridLayout(my_grp)
        self._my_cmbs = []
        for i in range(6):
            mg.addWidget(QLabel(f"{i+1}:"), i, 0)
            c1 = QComboBox(); c1.addItems(TYPES); c1.setFixedWidth(90)
            c2 = QComboBox(); c2.addItems(["(없음)"] + TYPES); c2.setFixedWidth(90)
            mg.addWidget(c1, i, 1); mg.addWidget(c2, i, 2)
            self._my_cmbs.append((c1, c2))

        opp_grp = QGroupBox("상대 파티 타입 (각 6마리)")
        og = QGridLayout(opp_grp)
        self._opp_cmbs = []
        for i in range(6):
            og.addWidget(QLabel(f"{i+1}:"), i, 0)
            c1 = QComboBox(); c1.addItems(TYPES); c1.setFixedWidth(90)
            c2 = QComboBox(); c2.addItems(["(없음)"] + TYPES); c2.setFixedWidth(90)
            og.addWidget(c1, i, 1); og.addWidget(c2, i, 2)
            self._opp_cmbs.append((c1, c2))

        party_row.addWidget(my_grp)
        party_row.addWidget(opp_grp)
        root.addLayout(party_row)

        btn = QPushButton("그리드 계산")
        btn.clicked.connect(self._calc)
        root.addWidget(btn)

        # ── 그리드 표시 ───────────────────────────────────────────────────────
        self._grid_frame = QWidget()
        self._grid_layout = QGridLayout(self._grid_frame)
        root.addWidget(self._grid_frame)
        root.addStretch()

    def _get_party_types(self, cmbs) -> list[list[str]]:
        result = []
        for c1, c2 in cmbs:
            types = [c1.currentText()]
            if c2.currentText() != "(없음)":
                types.append(c2.currentText())
            result.append(types)
        return result

    def _calc(self):
        my_types  = self._get_party_types(self._my_cmbs)
        opp_types = self._get_party_types(self._opp_cmbs)

        my_party  = Party(members=[Pokemon(name=f"My{i+1}", types=t) for i, t in enumerate(my_types)])
        opp_party = Party(members=[Pokemon(name=f"Opp{i+1}", types=t) for i, t in enumerate(opp_types)])

        data = grid_score(my_party, opp_party)

        # 기존 그리드 클리어
        for i in reversed(range(self._grid_layout.count())):
            w = self._grid_layout.itemAt(i).widget()
            if w:
                w.deleteLater()

        # 헤더 행 (상대)
        self._grid_layout.addWidget(QLabel(""), 0, 0)
        for j, name in enumerate(data["opp_names"]):
            lbl = QLabel(name); lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._grid_layout.addWidget(lbl, 0, j + 1)

        # 데이터 행 (내 파티)
        for i, my_name in enumerate(data["my_names"]):
            lbl = QLabel(my_name)
            self._grid_layout.addWidget(lbl, i + 1, 0)
            for j, (val, color) in enumerate(zip(data["matrix"][i], data["color"][i])):
                cell = QLabel(f"×{val:.1f}")
                cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cell.setFixedSize(70, 28)
                cell.setStyleSheet(
                    f"background-color: {COLOR_MAP[color]}; color: #1e1e2e; "
                    f"border-radius: 3px; font-weight: bold;"
                )
                self._grid_layout.addWidget(cell, i + 1, j + 1)
