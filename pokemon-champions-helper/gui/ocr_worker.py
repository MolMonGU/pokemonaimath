import cv2
from PyQt6.QtCore import QThread, pyqtSignal
from core.battle_state import BattleState, detect_screen


class OcrWorker(QThread):
    my_pokemon_changed  = pyqtSignal(str)
    opp_pokemon_changed = pyqtSignal(str)
    my_hp_changed       = pyqtSignal(int)
    teams_updated       = pyqtSignal(list, list)
    status_changed      = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._running = False

    def run(self):
        self._running = True
        state = BattleState()

        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        if not cap.isOpened():
            self.status_changed.emit("카메라 열기 실패")
            return

        self.status_changed.emit("OCR 연결됨 (첫 인식 시 로딩...)")

        prev_my   = ""
        prev_opp  = ""
        prev_hp: int | None = None
        prev_teams: tuple[list, list] = ([], [])

        while self._running:
            ret, frame = cap.read()
            if not ret:
                self.msleep(30)
                continue

            screen = detect_screen(frame)
            state.screen = screen
            state.update(frame)

            if screen == "battle":
                if state.my_pokemon and state.my_pokemon != prev_my:
                    prev_my = state.my_pokemon
                    self.my_pokemon_changed.emit(prev_my)

                if state.opp_pokemon and state.opp_pokemon != prev_opp:
                    prev_opp = state.opp_pokemon
                    self.opp_pokemon_changed.emit(prev_opp)

                if state.my_hp is not None and state.my_hp != prev_hp:
                    prev_hp = state.my_hp
                    self.my_hp_changed.emit(prev_hp)
            else:
                curr = (list(state.my_team), list(state.opp_team))
                if curr != prev_teams and (curr[0] or curr[1]):
                    prev_teams = curr
                    self.teams_updated.emit(curr[0], curr[1])

        cap.release()
        self.status_changed.emit("OCR 꺼짐")

    def stop(self):
        self._running = False
