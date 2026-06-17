"""메인 창 — 탭 컨테이너 + always-on-top + 컴팩트 모드"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QTabWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QLabel, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon

from gui.speed_tab     import SpeedTab
from gui.damage_tab    import DamageTab
from gui.type_tab      import TypeTab
from gui.grid_tab      import GridTab
from gui.sets_tab      import SetsTab
from gui.log_tab       import LogTab
from gui.ocr_worker    import OcrWorker
from gui.camera_window import CameraWindow


DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: "Malgun Gothic", "맑은 고딕", sans-serif;
    font-size: 12px;
}
QTabWidget::pane {
    border: 1px solid #45475a;
    background-color: #1e1e2e;
}
QTabBar::tab {
    background-color: #313244;
    color: #cdd6f4;
    padding: 6px 14px;
    border: 1px solid #45475a;
    border-bottom: none;
}
QTabBar::tab:selected {
    background-color: #89b4fa;
    color: #1e1e2e;
    font-weight: bold;
}
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 10px;
}
QPushButton:hover {
    background-color: #45475a;
}
QPushButton:checked {
    background-color: #89b4fa;
    color: #1e1e2e;
}
QLineEdit, QComboBox, QSpinBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #585b70;
    border-radius: 3px;
    padding: 3px 6px;
}
QLabel { color: #cdd6f4; }
QGroupBox {
    border: 1px solid #45475a;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 4px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    color: #89b4fa;
}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("포켓몬 챔피언스 헬퍼")
        self.setMinimumSize(700, 500)
        self.setStyleSheet(DARK_STYLE)
        self._always_on_top = False
        self._compact = False

        self._build_ui()

        self._camera_win = CameraWindow()

        self._ocr_worker = OcrWorker()
        self._ocr_worker.my_pokemon_changed.connect(self._on_my_pokemon)
        self._ocr_worker.opp_pokemon_changed.connect(self._on_opp_pokemon)
        self._ocr_worker.my_hp_changed.connect(self._on_my_hp)
        self._ocr_worker.teams_updated.connect(self._on_teams_updated)
        self._ocr_worker.status_changed.connect(self._on_ocr_status)
        self._ocr_worker.frame_ready.connect(self._camera_win.update_frame)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # ── 상단 툴바 ─────────────────────────────────────────────────────────
        toolbar = QHBoxLayout()

        self.btn_ontop = QPushButton("📌 항상 위")
        self.btn_ontop.setCheckable(True)
        self.btn_ontop.setFixedWidth(90)
        self.btn_ontop.toggled.connect(self._toggle_on_top)

        self.btn_compact = QPushButton("⊡ 컴팩트")
        self.btn_compact.setCheckable(True)
        self.btn_compact.setFixedWidth(90)
        self.btn_compact.toggled.connect(self._toggle_compact)

        self.btn_ocr = QPushButton("👁 OCR 연결")
        self.btn_ocr.setCheckable(True)
        self.btn_ocr.setFixedWidth(100)
        self.btn_ocr.toggled.connect(self._toggle_ocr)

        self.btn_camera = QPushButton("📷 카메라 창")
        self.btn_camera.setFixedWidth(100)
        self.btn_camera.clicked.connect(self._open_camera_window)

        self.lbl_ocr = QLabel("OCR 꺼짐")
        self.lbl_ocr.setStyleSheet("color: #6c7086; font-size: 11px;")

        self.btn_battle_start = QPushButton("⚔ 배틀 시작 (리셋)")
        self.btn_battle_start.setFixedWidth(130)
        self.btn_battle_start.clicked.connect(self._battle_reset)

        toolbar.addWidget(self.btn_ontop)
        toolbar.addWidget(self.btn_compact)
        toolbar.addWidget(self.btn_ocr)
        toolbar.addWidget(self.btn_camera)
        toolbar.addWidget(self.lbl_ocr)
        toolbar.addStretch()
        toolbar.addWidget(self.btn_battle_start)
        layout.addLayout(toolbar)

        # ── 탭 ───────────────────────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.tab_speed  = SpeedTab()
        self.tab_damage = DamageTab()
        self.tab_type   = TypeTab()
        self.tab_grid   = GridTab()
        self.tab_sets   = SetsTab()
        self.tab_log    = LogTab()

        self.tabs.addTab(self.tab_speed,  "스피드")
        self.tabs.addTab(self.tab_damage, "대미지")
        self.tabs.addTab(self.tab_type,   "타입")
        self.tabs.addTab(self.tab_grid,   "6×6 그리드")
        self.tabs.addTab(self.tab_sets,   "세트 조회")
        self.tabs.addTab(self.tab_log,    "배틀 로그")

        layout.addWidget(self.tabs)

    # ── 슬롯 ─────────────────────────────────────────────────────────────────

    def _open_camera_window(self):
        self._camera_win.show()
        self._camera_win.raise_()
        self._camera_win.activateWindow()

    def _toggle_on_top(self, checked: bool):
        self._always_on_top = checked
        flags = self.windowFlags()
        if checked:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def _toggle_compact(self, checked: bool):
        self._compact = checked
        if checked:
            self.setFixedHeight(220)
            self.tabs.setCurrentWidget(self.tab_log)
        else:
            self.setMinimumSize(700, 500)
            self.setMaximumSize(16777215, 16777215)
            self.resize(800, 600)

    def _toggle_ocr(self, checked: bool):
        if checked:
            self._ocr_worker.start()
            self._camera_win.showFullScreen()
        else:
            self._ocr_worker.stop()
            self._camera_win.close()

    def _on_ocr_status(self, msg: str):
        self.lbl_ocr.setText(msg)
        color = "#a6e3a1" if "연결" in msg else "#6c7086"
        self.lbl_ocr.setStyleSheet(f"color: {color}; font-size: 11px;")

    def _on_my_pokemon(self, name: str):
        self.tab_damage.set_my_pokemon(name)
        self.tab_speed.set_pokemon("my", name)

    def _on_opp_pokemon(self, name: str):
        self.tab_damage.set_opp_pokemon(name)
        self.tab_speed.set_pokemon("opp", name)

    def _on_my_hp(self, hp: int):
        pass  # 추후 확장용

    def _on_teams_updated(self, my_team: list, opp_team: list):
        self.tab_grid.update_teams_from_ocr(my_team, opp_team)

    def closeEvent(self, event):
        self._camera_win.close()
        self._ocr_worker.stop()
        self._ocr_worker.wait(2000)
        super().closeEvent(event)

    def _battle_reset(self):
        self.tab_log.reset()
        self.tab_damage.reset_ranks()
        self.tab_speed.reset_ranks()
