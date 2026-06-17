"""배틀 로그 탭 — 관찰 기술 체크 + 세트 분류기 + SVD 잔여 기술 예측"""

import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QGroupBox, QCheckBox, QComboBox
)
from PyQt6.QtCore import Qt
from core.battle_log import BattleLog

DATA_DIR = Path(__file__).parent.parent / "data"


class LogTab(QWidget):
    def __init__(self):
        super().__init__()
        self._log = BattleLog()
        self._classifier = None
        self._embeddings = None
        self._try_load_models()
        self._build_ui()

    def _try_load_models(self):
        try:
            from ml.set_classifier import SetClassifier
            self._classifier = SetClassifier.load()
        except Exception:
            pass
        try:
            from ml.embeddings import get_embeddings
            emb = get_embeddings()
            emb.load()
            self._embeddings = emb
        except Exception:
            pass

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)

        # ── 기술 관찰 입력 ────────────────────────────────────────────────────
        grp = QGroupBox("상대 기술 관찰")
        g = QHBoxLayout(grp)

        g.addWidget(QLabel("포켓몬:"))
        self.edit_poke = QLineEdit(); self.edit_poke.setPlaceholderText("예: Garchomp"); self.edit_poke.setFixedWidth(130)
        g.addWidget(self.edit_poke)

        g.addWidget(QLabel("사용 기술:"))
        self.edit_move = QLineEdit(); self.edit_move.setPlaceholderText("예: Earthquake"); self.edit_move.setFixedWidth(160)
        self.edit_move.returnPressed.connect(self._log_move)
        g.addWidget(self.edit_move)

        btn_log = QPushButton("기록")
        btn_log.clicked.connect(self._log_move)
        g.addWidget(btn_log)

        btn_turn = QPushButton("다음 턴")
        btn_turn.clicked.connect(self._next_turn)
        g.addWidget(btn_turn)

        self.chk_trick = QCheckBox("트릭룸")
        self.chk_trick.toggled.connect(self._toggle_trick)
        g.addWidget(self.chk_trick)

        g.addStretch()
        root.addWidget(grp)

        # ── 상태 표시 ─────────────────────────────────────────────────────────
        self._turn_label = QLabel("턴: 0")
        root.addWidget(self._turn_label)

        self.result = QTextEdit()
        self.result.setReadOnly(True)
        root.addWidget(self.result)

    def _log_move(self):
        poke = self.edit_poke.text().strip()
        move = self.edit_move.text().strip()
        if not poke or not move:
            return

        self._log.opp_used_move(poke, move)
        self.edit_move.clear()
        self._refresh(poke)

    def _next_turn(self):
        self._log.next_turn()
        self._turn_label.setText(f"턴: {self._log.turn}")

    def _toggle_trick(self, checked):
        self._log.toggle_trick_room()

    def _refresh(self, focus_poke: str):
        summary = self._log.get_opp_summary(focus_poke)
        if not summary:
            return

        lines = [f"=== {focus_poke} ==="]
        lines.append(f"관찰된 기술: {', '.join(summary['unique_moves'])}")
        if summary["possible_choice"]:
            lines.append("⚠ 구애 아이템 가능성 (같은 기술 2회 이상)")
        if summary["item_confirmed"]:
            lines.append(f"확정 아이템: {summary['item_confirmed']}")

        # 세트 분류기
        if self._classifier:
            preds = self._classifier.predict(focus_poke, summary["unique_moves"])
            if preds:
                lines.append("")
                lines.append("▶ 세트 예측 (Naive Bayes)")
                for p in preds[:4]:
                    bar = "█" * int(p["prob"] / 5)
                    lines.append(f"  {p['item']:<22} {p['prob']:5.1f}%  {bar}")

        # SVD 잔여 기술 예측
        if self._embeddings:
            candidates = self._embeddings.predict_moves(focus_poke, summary["unique_moves"], top_n=5)
            if candidates:
                lines.append("")
                lines.append("▶ 잔여 기술 후보 (SVD)")
                for move, score in candidates:
                    lines.append(f"  {move:<22} score={score:.3f}")

        self.result.setPlainText("\n".join(lines))

    def reset(self):
        self._log.reset()
        self._turn_label.setText("턴: 0")
        self.result.clear()
        self.chk_trick.setChecked(False)
