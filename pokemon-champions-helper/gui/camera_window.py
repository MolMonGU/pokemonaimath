import cv2
import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt


class CameraWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("카메라 프리뷰")
        self.resize(1280, 960)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 상단 컨트롤 바
        ctrl = QHBoxLayout()
        ctrl.setContentsMargins(4, 4, 4, 4)

        self.btn_fs = QPushButton("⛶ 전체화면")
        self.btn_fs.setCheckable(True)
        self.btn_fs.setFixedWidth(100)
        self.btn_fs.toggled.connect(self._toggle_fullscreen)
        ctrl.addWidget(self.btn_fs)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        # 카메라 화면
        self.lbl_frame = QLabel("OCR 연결 버튼을 누르면 화면이 표시됩니다")
        self.lbl_frame.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_frame.setStyleSheet("background-color: #000000; color: #6c7086; font-size: 14px;")
        layout.addWidget(self.lbl_frame, stretch=1)

    def _toggle_fullscreen(self, checked: bool):
        if checked:
            self.showFullScreen()
            self.btn_fs.setText("✕ 전체화면 해제")
        else:
            self.showNormal()
            self.btn_fs.setText("⛶ 전체화면")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.btn_fs.setChecked(False)

    def update_frame(self, frame: np.ndarray):
        rgb  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        data = rgb.tobytes()
        img  = QImage(data, w, h, ch * w, QImage.Format.Format_RGB888)
        pix  = QPixmap.fromImage(img).scaled(
            self.lbl_frame.width(),
            self.lbl_frame.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        self.lbl_frame.setPixmap(pix)
