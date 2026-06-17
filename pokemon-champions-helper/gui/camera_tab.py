import cv2
import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt


class CameraTab(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_frame = QLabel("OCR 연결 버튼을 누르면 화면이 표시됩니다")
        self.lbl_frame.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_frame.setMinimumSize(640, 480)
        self.lbl_frame.setStyleSheet("background-color: #000000; color: #6c7086;")
        layout.addWidget(self.lbl_frame)

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
