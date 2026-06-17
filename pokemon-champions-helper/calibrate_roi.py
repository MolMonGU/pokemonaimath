"""
ROI 캘리브레이터 — 마우스로 드래그해서 ROI 조정 후 S키로 저장
실행: python calibrate_roi.py

조작:
  드래그     : ROI 이동 / 모서리·변 드래그로 크기 조정
  S          : data/roi_config.json 저장
  M          : 배틀 ↔ 선출 모드 전환
  C          : 현재 프레임의 ROI 크롭 이미지 저장 (roi_*.png)
  Q          : 종료
"""
import cv2
import json
import numpy as np
from pathlib import Path

DEFAULT_ROI = {
    "my_pokemon":   (100, 420, 290, 452),
    "my_hp":        (40,  448, 215, 478),
    "opp_pokemon":  (530, 28,  638, 75),
    "my_team":      (5,   80,  210, 450),
    "opp_team":     (460, 50,  640, 420),
}

CONFIG_PATH = Path(__file__).parent / "data" / "roi_config.json"

COLORS = {
    "my_pokemon":  (0, 255, 0),
    "my_hp":       (50, 220, 100),
    "opp_pokemon": (0, 150, 255),
    "my_team":     (0, 255, 0),
    "opp_team":    (0, 150, 255),
}

BATTLE_ROIS = ["my_pokemon", "my_hp", "opp_pokemon"]
SELECT_ROIS = ["my_team", "opp_team"]
EDGE_THRESH = 10

roi_state = {}
selected   = None
drag_start = None
drag_type  = None
mode       = "battle"
last_frame  = None


def load_config():
    roi_state.update(DEFAULT_ROI)
    if CONFIG_PATH.exists():
        data = json.loads(CONFIG_PATH.read_text())
        for k, v in data.items():
            roi_state[k] = tuple(v)
        print("roi_config.json 로드 완료")
    else:
        print("기본 ROI 사용")


def save_config():
    CONFIG_PATH.parent.mkdir(exist_ok=True)
    CONFIG_PATH.write_text(json.dumps({k: list(v) for k, v in roi_state.items()}, indent=2))
    print("저장 완료:", CONFIG_PATH)
    for k, v in roi_state.items():
        print(f"  {k}: {v}")


def save_crops(frame):
    keys = BATTLE_ROIS if mode == "battle" else SELECT_ROIS
    for k in keys:
        x1, y1, x2, y2 = roi_state[k]
        crop = frame[y1:y2, x1:x2]
        path = f"roi_{k}.png"
        cv2.imwrite(path, crop)
    print("크롭 저장 완료: roi_*.png")


def active_keys():
    return BATTLE_ROIS if mode == "battle" else SELECT_ROIS


def hit_test(x, y):
    for key in reversed(active_keys()):
        x1, y1, x2, y2 = roi_state[key]
        if not (x1 <= x <= x2 and y1 <= y <= y2):
            continue
        nl = abs(x - x1) < EDGE_THRESH
        nr = abs(x - x2) < EDGE_THRESH
        nt = abs(y - y1) < EDGE_THRESH
        nb = abs(y - y2) < EDGE_THRESH
        if nl and nt: return key, "tl"
        if nr and nt: return key, "tr"
        if nl and nb: return key, "bl"
        if nr and nb: return key, "br"
        if nl: return key, "l"
        if nr: return key, "r"
        if nt: return key, "t"
        if nb: return key, "b"
        return key, "move"
    return None, None


def mouse_cb(event, x, y, flags, param):
    global selected, drag_start, drag_type

    if event == cv2.EVENT_LBUTTONDOWN:
        key, dtype = hit_test(x, y)
        selected   = key
        drag_start = (x, y)
        drag_type  = dtype

    elif event == cv2.EVENT_MOUSEMOVE and drag_start and selected:
        dx = x - drag_start[0]
        dy = y - drag_start[1]
        x1, y1, x2, y2 = roi_state[selected]

        if drag_type == "move":
            w, h = x2 - x1, y2 - y1
            x1 = max(0, x1 + dx)
            y1 = max(0, y1 + dy)
            x2 = x1 + w
            y2 = y1 + h
        elif drag_type == "tl": x1 += dx; y1 += dy
        elif drag_type == "tr": x2 += dx; y1 += dy
        elif drag_type == "bl": x1 += dx; y2 += dy
        elif drag_type == "br": x2 += dx; y2 += dy
        elif drag_type == "l":  x1 += dx
        elif drag_type == "r":  x2 += dx
        elif drag_type == "t":  y1 += dy
        elif drag_type == "b":  y2 += dy

        if x2 - x1 >= 6 and y2 - y1 >= 4:
            roi_state[selected] = (x1, y1, x2, y2)
        drag_start = (x, y)

    elif event == cv2.EVENT_LBUTTONUP:
        drag_start = None


def draw_frame(frame):
    disp = frame.copy()
    for key in active_keys():
        x1, y1, x2, y2 = roi_state[key]
        col  = COLORS[key]
        thick = 2 if key == selected else 1
        cv2.rectangle(disp, (x1, y1), (x2, y2), col, thick)
        cv2.putText(disp, key, (x1 + 2, y1 + 13),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, col, 1)
        for cx, cy in [(x1,y1),(x2,y1),(x1,y2),(x2,y2)]:
            cv2.circle(disp, (cx, cy), 5, col, -1)

    info = f"[{mode.upper()}]  S=Save  M=Mode  C=Crop  Q=Quit"
    cv2.putText(disp, info, (5, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255,255,0), 1)

    if selected:
        x1, y1, x2, y2 = roi_state[selected]
        cv2.putText(disp, f"{selected}: ({x1},{y1})-({x2},{y2})  w={x2-x1} h={y2-y1}",
                    (5, 472), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0,255,255), 1)
    return disp


def main():
    global mode, selected, last_frame
    load_config()

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    cv2.namedWindow("ROI Calibrator", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("ROI Calibrator", 1280, 960)
    cv2.setMouseCallback("ROI Calibrator", mouse_cb)

    print("\n=== ROI 캘리브레이터 ===")
    print("  ROI 박스 위/변/모서리 드래그로 조정")
    print("  S: 저장  M: 배틀/선출 전환  C: 크롭저장  Q: 종료\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        last_frame = frame.copy()

        cv2.imshow("ROI Calibrator", draw_frame(frame))
        key = cv2.waitKey(1) & 0xFF

        if key == ord('q'):
            break
        elif key == ord('s'):
            save_config()
        elif key == ord('m'):
            mode = "select" if mode == "battle" else "battle"
            selected = None
            print(f"모드: {mode.upper()}")
        elif key == ord('c') and last_frame is not None:
            save_crops(last_frame)

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
