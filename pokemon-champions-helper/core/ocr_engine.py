"""
EasyOCR 기반 화면 텍스트 인식
배틀/선출 화면에서 포켓몬 이름과 HP 추출
"""
import json
import re
import cv2
import numpy as np
from pathlib import Path

_DEFAULT_ROI = {
    "my_pokemon":   (100, 420, 290, 452),
    "my_hp":        (40,  448, 215, 478),
    "opp_pokemon":  (530, 28,  638, 75),
    "my_team":      (5,   80,  210, 450),
    "opp_team":     (460, 50,  640, 420),
}

def _load_roi():
    config = Path(__file__).parent.parent / "data" / "roi_config.json"
    if config.exists():
        data = json.loads(config.read_text())
        return {k: tuple(v) for k, v in data.items()}
    return dict(_DEFAULT_ROI)

ROI = _load_roi()


def crop(frame: np.ndarray, key: str) -> np.ndarray:
    x1, y1, x2, y2 = ROI[key]
    return frame[y1:y2, x1:x2]


def preprocess(img: np.ndarray) -> np.ndarray:
    """OCR 전처리: 4x 업스케일 + 샤프닝"""
    if img is None or img.size == 0:
        return img
    h, w = img.shape[:2]
    img = cv2.resize(img, (w * 4, h * 4), interpolation=cv2.INTER_CUBIC)
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
    img = cv2.filter2D(img, -1, kernel)
    return img


class OcrEngine:

    def __init__(self):
        self._reader = None

    def _lazy_init(self):
        if self._reader is None:
            import easyocr
            try:
                import torch
                use_gpu = torch.cuda.is_available()
            except ImportError:
                use_gpu = False
            print(f"EasyOCR 초기화 중... ({'GPU' if use_gpu else 'CPU'})")
            self._reader = easyocr.Reader(["ko", "en"], gpu=use_gpu)
            print("OCR 준비 완료")

    def read(self, img: np.ndarray) -> list[str]:
        """이미지에서 텍스트 목록 반환"""
        self._lazy_init()
        if img is None or img.size == 0:
            return []
        img = preprocess(img)
        results = self._reader.readtext(img, detail=0, paragraph=False)
        return [r.strip() for r in results if r.strip()]

    def read_hp(self, img: np.ndarray) -> int | None:
        """HP 수치 추출 (숫자만)"""
        texts = self.read(img)
        for t in texts:
            m = re.search(r"(\d+)", t)
            if m:
                val = int(m.group(1))
                if 1 <= val <= 999:
                    return val
        return None
