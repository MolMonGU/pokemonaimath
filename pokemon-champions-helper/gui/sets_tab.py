"""세트 조회 탭 — Smogon 채용 세트 + 운영 방식"""

import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QLineEdit, QPushButton, QTextEdit, QGroupBox
)

DATA_DIR = Path(__file__).parent.parent / "data"


class SetsTab(QWidget):
    def __init__(self):
        super().__init__()
        self._smogon: dict = {}
        self._build_ui()
        self._load_data()

    def _load_data(self):
        p = DATA_DIR / "smogon_sets.json"
        if p.exists():
            self._smogon = json.loads(p.read_text(encoding="utf-8"))

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        grp = QGroupBox("포켓몬 세트 조회")
        g = QHBoxLayout(grp)

        g.addWidget(QLabel("포켓몬 이름(영문):"))
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("예: Garchomp")
        self.edit_name.setFixedWidth(160)
        self.edit_name.returnPressed.connect(self._search)
        g.addWidget(self.edit_name)

        btn = QPushButton("조회")
        btn.clicked.connect(self._search)
        g.addWidget(btn)
        g.addStretch()
        root.addWidget(grp)

        self.result = QTextEdit()
        self.result.setReadOnly(True)
        root.addWidget(self.result)

    def _search(self):
        name = self.edit_name.text().strip()
        if not name:
            return
        # 대소문자 무관 검색
        key = next((k for k in self._smogon if k.lower() == name.lower()), None)
        if key is None:
            self.result.setPlainText(f"'{name}' 데이터 없음\n(smogon_sets.json에 없거나 fetch_data.py 미실행)")
            return

        data = self._smogon[key]
        lines = [f"=== {key} ===", ""]

        lines.append("▶ 상위 기술 채용률")
        for m in data.get("top_moves", []):
            lines.append(f"  {m['move']:<20} {m['usage']*100:.1f}%")

        lines.append("")
        lines.append("▶ 상위 아이템")
        for it in data.get("top_items", []):
            lines.append(f"  {it['item']:<20} {it['usage']*100:.1f}%")

        lines.append("")
        lines.append("▶ 상위 특성")
        for ab in data.get("top_abilities", []):
            lines.append(f"  {ab['ability']:<20} {ab['usage']*100:.1f}%")

        lines.append("")
        lines.append("▶ 상위 배분")
        for sp in data.get("top_spreads", []):
            lines.append(f"  {sp['spread']:<30} {sp['usage']*100:.1f}%")

        self.result.setPlainText("\n".join(lines))

    def set_pokemon(self, name: str):
        """외부에서 포켓몬 이름을 직접 설정하고 조회"""
        self.edit_name.setText(name)
        self._search()
