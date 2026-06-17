import cv2
import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt


class CameraWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("카메라 프리뷰")
        self.setStyleSheet("background-color: #000000;")
        self._worker = None
        self._build_ui()

    def set_worker(self, worker):
        self._worker = worker

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.lbl_frame = QLabel()
        self.lbl_frame.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_frame.setStyleSheet("background-color: #000000;")
        layout.addWidget(self.lbl_frame)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.close()
        elif self._worker:
            if key == Qt.Key.Key_1:
                self._worker.toggle_panel(0)
            elif key == Qt.Key.Key_2:
                self._worker.toggle_panel(1)
            elif key == Qt.Key.Key_3:
                self._worker.toggle_panel(2)

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
