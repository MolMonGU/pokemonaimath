"""6×6 유불리 그리드 탭 + 선출 추천"""

import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QComboBox, QPushButton, QGroupBox, QTextEdit
)
from PyQt6.QtCore import Qt
from core.type_calc import TYPES
from core.party import Party, Pokemon, grid_score
from core.selection import recommend, load_my_team, load_opp_team

DATA_DIR = Path(__file__).parent.parent / "data"

COLOR_MAP = {
    "green":  "#a6e3a1",
    "red":    "#f38ba8",
    "yellow": "#f9e2af",
}


class GridTab(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)

        # ── 자동 로드 버튼 ────────────────────────────────────────────────────
        top_row = QHBoxLayout()
        btn_auto = QPushButton("팀 자동 불러오기 (my_team + opp_team)")
        btn_auto.clicked.connect(self._auto_load)
        top_row.addWidget(btn_auto)
        self.lbl_load = QLabel("")
        self.lbl_load.setStyleSheet("color: #a6e3a1; font-size: 11px;")
        top_row.addWidget(self.lbl_load)
        top_row.addStretch()
        root.addLayout(top_row)

        # ── 파티 입력 ─────────────────────────────────────────────────────────
        party_row = QHBoxLayout()

        my_grp = QGroupBox("내 파티 타입")
        mg = QGridLayout(my_grp)
        self._my_cmbs = []
        self._my_labels = []
        for i in range(6):
            lbl = QLabel(f"{i+1}:")
            mg.addWidget(lbl, i, 0)
            self._my_labels.append(lbl)
            c1 = QComboBox(); c1.addItems(TYPES); c1.setFixedWidth(90)
            c2 = QComboBox(); c2.addItems(["(없음)"] + TYPES); c2.setFixedWidth(90)
            mg.addWidget(c1, i, 1); mg.addWidget(c2, i, 2)
            self._my_cmbs.append((c1, c2))

        opp_grp = QGroupBox("상대 파티 타입")
        og = QGridLayout(opp_grp)
        self._opp_cmbs = []
        self._opp_labels = []
        for i in range(6):
            lbl = QLabel(f"{i+1}:")
            og.addWidget(lbl, i, 0)
            self._opp_labels.append(lbl)
            c1 = QComboBox(); c1.addItems(TYPES); c1.setFixedWidth(90)
            c2 = QComboBox(); c2.addItems(["(없음)"] + TYPES); c2.setFixedWidth(90)
            og.addWidget(c1, i, 1); og.addWidget(c2, i, 2)
            self._opp_cmbs.append((c1, c2))

        party_row.addWidget(my_grp)
        party_row.addWidget(opp_grp)
        root.addLayout(party_row)

        # ── 계산 버튼 ──────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_grid = QPushButton("그리드 계산")
        btn_grid.clicked.connect(self._calc_grid)
        btn_row.addWidget(btn_grid)
        btn_pick = QPushButton("선출 추천")
        btn_pick.clicked.connect(self._calc_selection)
        btn_row.addWidget(btn_pick)
        btn_row.addStretch()
        root.addLayout(btn_row)

        # ── 그리드 표시 ───────────────────────────────────────────────────────
        self._grid_frame = QWidget()
        self._grid_layout = QGridLayout(self._grid_frame)
        root.addWidget(self._grid_frame)

        # ── 선출 추천 결과 ────────────────────────────────────────────────────
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMaximumHeight(220)
        root.addWidget(self.result_text)

    # ── 자동 로드 ─────────────────────────────────────────────────────────────

    def _auto_load(self):
        try:
            my_team = load_my_team()
            opp_team = load_opp_team()
        except Exception as e:
            self.lbl_load.setText(f"❌ {e}")
            self.lbl_load.setStyleSheet("color: #f38ba8; font-size: 11px;")
            return

        for i, entry in enumerate(my_team[:6]):
            types = entry["pokedex_entry"]["types"]
            name = entry["name_kr"]
            self._my_labels[i].setText(f"{name}:")
            self._set_type_cmbs(self._my_cmbs[i], types)

        for i, entry in enumerate(opp_team[:6]):
            types = entry["pokedex_entry"]["types"]
            name = entry["name_kr"]
            self._opp_labels[i].setText(f"{name}:")
            self._set_type_cmbs(self._opp_cmbs[i], types)

        self.lbl_load.setText(f"✅ 내 팀 {len(my_team)}마리 / 상대 {len(opp_team)}마리 로드 완료")
        self.lbl_load.setStyleSheet("color: #a6e3a1; font-size: 11px;")
        self._calc_grid()

    def _set_type_cmbs(self, cmbs: tuple, types: list[str]):
        c1, c2 = cmbs
        if types:
            idx = c1.findText(types[0])
            if idx >= 0:
                c1.setCurrentIndex(idx)
        if len(types) > 1:
            idx = c2.findText(types[1])
            if idx >= 0:
                c2.setCurrentIndex(idx)
        else:
            c2.setCurrentIndex(0)

    # ── 그리드 계산 ───────────────────────────────────────────────────────────

    def _get_party_types(self, cmbs, labels) -> tuple[list[list[str]], list[str]]:
        types_list, names = [], []
        for (c1, c2), lbl in zip(cmbs, labels):
            types = [c1.currentText()]
            if c2.currentText() != "(없음)":
                types.append(c2.currentText())
            types_list.append(types)
            names.append(lbl.text().rstrip(":"))
        return types_list, names

    def _calc_grid(self):
        my_types, my_names = self._get_party_types(self._my_cmbs, self._my_labels)
        opp_types, opp_names = self._get_party_types(self._opp_cmbs, self._opp_labels)

        my_party  = Party(members=[Pokemon(name=n, types=t) for n, t in zip(my_names, my_types)])
        opp_party = Party(members=[Pokemon(name=n, types=t) for n, t in zip(opp_names, opp_types)])

        data = grid_score(my_party, opp_party)

        for i in reversed(range(self._grid_layout.count())):
            w = self._grid_layout.itemAt(i).widget()
            if w:
                w.deleteLater()

        self._grid_layout.addWidget(QLabel(""), 0, 0)
        for j, name in enumerate(data["opp_names"]):
            lbl = QLabel(name); lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._grid_layout.addWidget(lbl, 0, j + 1)

        for i, my_name in enumerate(data["my_names"]):
            self._grid_layout.addWidget(QLabel(my_name), i + 1, 0)
            for j, (val, color) in enumerate(zip(data["matrix"][i], data["color"][i])):
                cell = QLabel(f"×{val:.1f}")
                cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cell.setFixedSize(70, 28)
                cell.setStyleSheet(
                    f"background-color: {COLOR_MAP[color]}; color: #1e1e2e; "
                    f"border-radius: 3px; font-weight: bold;"
                )
                self._grid_layout.addWidget(cell, i + 1, j + 1)

    # ── OCR 팀 업데이트 ───────────────────────────────────────────────────────

    def update_teams_from_ocr(self, my_names: list[str], opp_names: list[str]):
        """OCR 선출 화면 감지 시 팀 타입 자동 반영"""
        p = DATA_DIR / "pokemon.json"
        db = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

        for i in range(6):
            if i < len(my_names):
                name = my_names[i]
                types = db.get(name, {}).get("types", ["Normal"])
                self._my_labels[i].setText(f"{name}:")
                self._set_type_cmbs(self._my_cmbs[i], types)
            else:
                self._my_labels[i].setText(f"{i+1}:")

        for i in range(6):
            if i < len(opp_names):
                name = opp_names[i]
                types = db.get(name, {}).get("types", ["Normal"])
                self._opp_labels[i].setText(f"{name}:")
                self._set_type_cmbs(self._opp_cmbs[i], types)
            else:
                self._opp_labels[i].setText(f"{i+1}:")

        self.lbl_load.setText(
            f"✅ OCR: 내 팀 {len(my_names)}마리 / 상대 {len(opp_names)}마리"
        )
        self.lbl_load.setStyleSheet("color: #a6e3a1; font-size: 11px;")
        if my_names or opp_names:
            self._calc_grid()

    # ── 선출 추천 ─────────────────────────────────────────────────────────────

    def _calc_selection(self):
        try:
            picks = recommend(top_n=5)
        except Exception as e:
            self.result_text.setPlainText(f"오류: {e}\nopp_team.json이 없거나 데이터 문제")
            return

        lines = ["=== 선출 추천 (타입 커버리지 기준) ===", ""]
        for rank, pick in enumerate(picks, 1):
            combo_str = " / ".join(pick["combo"])
            lines.append(f"#{rank}  {combo_str}  (점수 {pick['score']})")
            for opp_name, info in pick["coverage"].items():
                eff = info["eff"]
                by  = info["by"]
                bar = "●" * int(eff * 2)
                lines.append(f"   vs {opp_name:<6} ×{eff:.1f} ({by}) {bar}")
            lines.append("")

        self.result_text.setPlainText("\n".join(lines))
