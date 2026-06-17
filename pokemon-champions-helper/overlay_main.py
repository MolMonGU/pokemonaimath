"""
포켓몬 챔피언스 실시간 오버레이
실행: python overlay_main.py

키 조작:
  Q       : 종료
  H       : OFF -> 선출 -> 배틀 -> OFF 순환
  D       : ROI 디버그 토글
  C       : ROI 크롭 저장
  1/2/3/4 : (배틀) 상대 기술 관찰 등록 (번호 = 예상 기술 순서)
  R       : (배틀) 관찰 기술 + 상대 랭크 초기화
  Z / X   : (배틀) 내 ATK 랭크 +1 / -1
  N / M   : (배틀) 내 SPA 랭크 +1 / -1
  V       : (배틀) 내 랭크 전체 초기화
"""
import json
import cv2
import numpy as np
from pathlib import Path
from PIL import ImageFont, ImageDraw, Image
from core.battle_state import BattleState, SETUP_MOVES
from core.ocr_engine import ROI

ABILITY_IMMUNITIES: dict[str, list[str]] = {
    "Levitate":        ["Ground"],
    "Water Absorb":    ["Water"],
    "Dry Skin":        ["Water"],
    "Storm Drain":     ["Water"],
    "Flash Fire":      ["Fire"],
    "Volt Absorb":     ["Electric"],
    "Lightning Rod":   ["Electric"],
    "Motor Drive":     ["Electric"],
    "Sap Sipper":      ["Grass"],
    "Earth Eater":     ["Ground"],
    "Well-Baked Body": ["Fire"],
}


def stage_mul(stage: int) -> float:
    stage = max(-6, min(6, stage))
    return (2 + stage) / 2 if stage >= 0 else 2 / (2 - stage)


def calc_damage_pct(bp, my_stat, opp_stat, opp_hp, type_mul,
                    my_stage=0, opp_def_stage=0) -> float | None:
    if bp == 0 or opp_stat == 0 or opp_hp == 0:
        return None
    my_eff  = my_stat  * stage_mul(my_stage)
    opp_eff = opp_stat * stage_mul(opp_def_stage)
    raw     = ((22 * bp * my_eff / opp_eff) / 50 + 2) * type_mul
    return raw / opp_hp * 100

_FONT_PATH = r"C:\Windows\Fonts\malgun.ttf"
_fonts = {}

def _get_font(size):
    if size not in _fonts:
        _fonts[size] = ImageFont.truetype(_FONT_PATH, size)
    return _fonts[size]


DATA_DIR = Path(__file__).parent / "data"

TYPE_COLOR = {
    "Normal":   (180,180,180), "Fire":    (0,  80, 255),
    "Water":    (255,150, 50), "Electric":(0, 220, 255),
    "Grass":    (50, 200,  50), "Ice":    (255,220,100),
    "Fighting": (0,  60, 200), "Poison":  (160, 0, 160),
    "Ground":   (50, 180, 220), "Flying":  (220,180,  0),
    "Psychic":  (80,  0, 255), "Bug":     (30, 150,  30),
    "Rock":     (80, 120, 160), "Ghost":  (100,  0, 100),
    "Dragon":   (180, 50,  50), "Dark":   (40,  40,  80),
    "Steel":    (160,160,180), "Fairy":   (180, 80, 255),
}


def load_pokedex():
    path = DATA_DIR / "pokemon.json"
    pokedex = {}
    if path.exists():
        pokedex = json.loads(path.read_text(encoding="utf-8"))
    # 내 팀 포켓몬이 없으면 my_team.json 데이터로 보완
    team_path = DATA_DIR / "my_team.json"
    if team_path.exists():
        for p in json.loads(team_path.read_text(encoding="utf-8")):
            pokedex.setdefault(p["name"], p["pokedex_entry"])
    return pokedex


def load_type_chart():
    path = DATA_DIR / "type_chart.json"
    if path.exists():
        d = json.loads(path.read_text(encoding="utf-8"))
        return d["types"], d["chart"]
    return [], []


def get_type_multiplier(atk_type, def_types, types, chart):
    if not types or atk_type not in types:
        return 1.0
    ai = types.index(atk_type)
    mul = 1.0
    for dt in def_types:
        if dt in types:
            di = types.index(dt)
            mul *= chart[ai][di]
    return mul


def best_attack_type(my_types, opp_def_types, types, chart):
    best_mul, best_type = 0.0, ""
    for t in my_types:
        mul = get_type_multiplier(t, opp_def_types, types, chart)
        if mul > best_mul:
            best_mul, best_type = mul, t
    return best_type, best_mul


def draw_panel(frame, x, y, w, h, alpha=0.6):
    overlay = frame.copy()
    cv2.rectangle(overlay, (x, y), (x+w, y+h), (20, 20, 20), -1)
    cv2.addWeighted(overlay, alpha, frame, 1-alpha, 0, frame)


def draw_text(frame, text, x, y, color=(255,255,255), scale=0.5):
    size = max(10, int(scale * 28))
    pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)
    font = _get_font(size)
    draw.text((x+1, y-size+1), text, font=font, fill=(0, 0, 0))
    r, g, b = color[2], color[1], color[0]
    draw.text((x, y-size), text, font=font, fill=(r, g, b))
    frame[:] = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


def draw_type_badge(frame, type_name, x, y):
    color = TYPE_COLOR.get(type_name, (128,128,128))
    cv2.rectangle(frame, (x, y-14), (x+65, y+4), color, -1)
    cv2.putText(frame, type_name, (x+3, y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255,255,255), 1)


def fmt_move(move: str) -> str:
    return " ".join(w.capitalize() for w in move.replace("-", " ").split())


# ── 배틀 오버레이 ────────────────────────────────────────────────────────────

# 현재 프레임의 상대 예상 기술 목록 (숫자키 입력에 공유)
_current_opp_moves: list[dict] = []


def draw_battle_overlay(frame, state, pokedex, types, chart):
    my_name  = state.my_pokemon
    opp_name = state.opp_pokemon

    my_entry  = pokedex.get(my_name, {})
    opp_entry = pokedex.get(opp_name, {})

    my_types  = my_entry.get("types", [])
    opp_types = opp_entry.get("types", [])
    my_stats  = my_entry.get("base_stats", {})
    opp_stats = opp_entry.get("base_stats", {})

    # ── 우상단: 기본 정보 + 승리 확률 ────────────────────────────────────────
    px, py, pw, ph = 445, 85, 190, 200
    draw_panel(frame, px, py, pw, ph)

    y = py + 18
    draw_text(frame, f"My:  {my_name or '?'}", px+5, y, (100,255,100), 0.45)
    y += 18
    for i, t in enumerate(my_types):
        draw_type_badge(frame, t, px+5 + i*70, y)
    y += 22

    draw_text(frame, f"Opp: {opp_name or '?'}", px+5, y, (100,180,255), 0.45)
    y += 18
    for i, t in enumerate(opp_types):
        draw_type_badge(frame, t, px+5 + i*70, y)
    y += 22

    if my_types and opp_types:
        best_t, mul = best_attack_type(my_types, opp_types, types, chart)
        color = (0,255,0) if mul >= 2 else (0,200,255) if mul == 1 else (0,0,255)
        draw_text(frame, f"상성: {best_t} x{mul:.1f}", px+5, y, color, 0.45)
        y += 18

    my_spe  = my_stats.get("spe", 0)
    opp_spe = opp_stats.get("spe", 0)
    if my_spe and opp_spe:
        spd_col = (0,255,0) if my_spe > opp_spe else (0,100,255)
        draw_text(frame, f"SPE {my_spe} vs {opp_spe}", px+5, y, spd_col, 0.42)
        y += 18

    if state.my_hp:
        draw_text(frame, f"HP: {state.my_hp}", px+5, y, (200,200,200), 0.42)
        y += 18

    # 팀 정보 있으면 승리 확률 표시
    win_prob = state.get_win_prob()
    if win_prob is not None:
        pct = int(win_prob * 100)
        col = (0,255,100) if pct >= 55 else (0,100,255) if pct <= 45 else (0,220,255)
        draw_text(frame, f"승리: {pct}%", px+5, y, col, 0.42)

    # ── 우하단: 상대 예상 기술 + 아이템 예측 ─────────────────────────────────
    _draw_opp_moves_panel(frame, state, opp_name, my_types, types, chart)

    # ── 좌하단: 행동 추천 ─────────────────────────────────────────────────────
    _draw_action_panel(frame, state, my_name, opp_name, pokedex, opp_types, types, chart)


def _draw_opp_moves_panel(frame, state, opp_name, my_types, types, chart):
    global _current_opp_moves

    px, py, pw, ph = 445, 290, 190, 150
    draw_panel(frame, px, py, pw, ph)

    y = py + 16
    draw_text(frame, "[ 상대 예상 기술 ]", px+5, y, (255,200,100), 0.42)
    y += 16

    opp_moves = state.get_opp_top_moves(opp_name)
    _current_opp_moves = opp_moves  # 숫자키 입력용 공유

    if opp_moves:
        for i, m in enumerate(opp_moves):
            move_type = m["type"]
            label = fmt_move(m["move"])
            observed = m["move"] in state.observed_opp_moves

            if observed:
                prefix = f"[{i+1}][V]"
                col = (100, 255, 100)
            else:
                prefix = f"[{i+1}]   "
                col = (200, 200, 200)

            if move_type:
                mul = get_type_multiplier(move_type, my_types, types, chart)
                if mul >= 2.0:
                    col = (80, 80, 255) if not observed else col
                    suffix = f" x{mul:.0f}!"
                elif mul == 0.0:
                    suffix = " x0"
                elif mul < 1.0:
                    suffix = f" x{mul:.1f}"
                else:
                    suffix = f"({move_type[:3]})"
            else:
                suffix = ""

            draw_text(frame, f"{prefix}{label}{suffix}", px+5, y, col, 0.36)
            y += 14
    else:
        draw_text(frame, "  데이터 없음", px+5, y, (150,150,150), 0.38)
        y += 14

    # 관찰 기술 있으면 아이템 예측 표시
    if state.observed_opp_moves:
        y += 4
        item_preds = state.get_item_prediction(opp_name)
        if item_preds:
            draw_text(frame, "예상 아이템:", px+5, y, (200,180,255), 0.38)
            y += 13
            for pred in item_preds[:2]:
                draw_text(frame,
                    f"  {pred['item']} {pred['prob']:.0f}%",
                    px+5, y, (180,160,230), 0.36)
                y += 12


def _fmt_stages(stages: dict) -> str:
    parts = [f"{k.upper()}{'+' if v>0 else ''}{v}" for k, v in stages.items() if v != 0]
    return " ".join(parts)


def _draw_action_panel(frame, state, my_name, opp_name, pokedex, opp_types, types, chart):
    px, py, pw, ph = 5, 300, 220, 160
    draw_panel(frame, px, py, pw, ph)

    y = py + 16
    stage_str = _fmt_stages(state.my_stat_stages)
    header = "[ 행동 추천 ]" + (f" {stage_str}" if stage_str else "")
    draw_text(frame, header, px+5, y, (100,255,200), 0.40)
    y += 16

    my_entry  = pokedex.get(my_name, {})
    opp_entry = pokedex.get(opp_name, {})
    my_stats  = my_entry.get("base_stats", {})
    opp_stats = opp_entry.get("base_stats", {})

    # 특성 면역 타입 집합
    immune_types: set[str] = set()
    for ab in opp_entry.get("abilities", []):
        immune_types.update(ABILITY_IMMUNITIES.get(ab, []))

    # 선공 여부 (SPE 랭크 반영)
    my_spe_eff  = my_stats.get("spe", 0)  * stage_mul(state.my_stat_stages.get("spe", 0))
    opp_spe_eff = opp_stats.get("spe", 0) * stage_mul(state.opp_stat_stages.get("spe", 0))

    my_moves = state.get_my_top_moves(my_name)

    if my_moves and opp_types:
        scored = []
        for m in my_moves:
            mtype = m.get("type")
            bp    = m.get("bp", 0)
            cat   = m.get("cat", "Status")
            pri   = m.get("pri", 0)

            if cat == "Status":
                setup = SETUP_MOVES.get(m["move"], {})
                scored.append((500, m["move"], mtype, bp, cat, pri, None, setup))
                continue

            type_mul = 0.0 if mtype in immune_types else \
                       get_type_multiplier(mtype, opp_types, types, chart)

            if cat == "Physical":
                my_stat, opp_def = my_stats.get("atk", 80), opp_stats.get("def", 80)
                my_stg, opp_stg  = state.my_stat_stages.get("atk", 0), state.opp_stat_stages.get("def", 0)
            else:
                my_stat, opp_def = my_stats.get("spa", 80), opp_stats.get("spd", 80)
                my_stg, opp_stg  = state.my_stat_stages.get("spa", 0), state.opp_stat_stages.get("spd", 0)

            dmg = calc_damage_pct(bp, my_stat, opp_def,
                                  opp_stats.get("hp", 100), type_mul,
                                  my_stage=my_stg, opp_def_stage=opp_stg)
            scored.append((type_mul * 1000 + (dmg or 0) + pri * 500,
                           m["move"], mtype, bp, cat, pri, dmg, {}))

        scored.sort(reverse=True)

        for _, move_id, mtype, bp, cat, pri, dmg, setup in scored[:4]:
            label = fmt_move(move_id)

            if cat == "Status":
                desc = " ".join(f"{k.upper()}+{v}" for k, v in setup.items() if v > 0)
                draw_text(frame, f"   {label} [{desc or '변화기'}]", px+5, y, (180,180,255), 0.36)
                y += 14
                continue

            immune   = mtype in immune_types
            type_mul = 0.0 if immune else get_type_multiplier(mtype, opp_types, types, chart)

            if immune:
                mark, col = "[X]", (100, 100, 100)
            elif type_mul >= 2.0:
                mark, col = "[*]", (0, 255, 100)
            elif type_mul >= 1.0:
                mark, col = "   ", (200, 200, 200)
            else:
                mark, col = "[v]", (120, 120, 200)

            first   = "先" if (pri > 0 or my_spe_eff > opp_spe_eff) else "  "
            dmg_str = f" ~{dmg:.0f}%" if dmg is not None and not immune else (" 무효" if immune else "")
            ttype   = (mtype or "?")[:3]
            draw_text(frame, f"{mark}{first} {label}({ttype})x{type_mul:.1f}{dmg_str}",
                      px+5, y, col, 0.36)
            y += 14

        # 특성 면역 경고
        if immune_types:
            warn_abs = [a for a in opp_entry.get("abilities", []) if ABILITY_IMMUNITIES.get(a)]
            if warn_abs:
                draw_text(frame, f"  특성:{'/'.join(warn_abs)}", px+5, y+2, (80,160,255), 0.34)

    elif not my_name:
        draw_text(frame, "  포켓몬 인식 대기 중", px+5, y, (150,150,150), 0.38)
    else:
        draw_text(frame, f"  {my_name} smogon 데이터 없음", px+5, y, (150,150,150), 0.36)


# ── 선출 오버레이 ────────────────────────────────────────────────────────────

def draw_select_overlay(frame, state, pokedex, types, chart):
    if not state.my_team and not state.opp_team:
        draw_panel(frame, 215, 120, 210, 40)
        draw_text(frame, "팀 인식 중...", 220, 145, (200,200,200), 0.5)
        return

    draw_panel(frame, 215, 80, 210, 310)
    y = 100
    draw_text(frame, "[ 내 팀 ]", 220, y, (100,255,100), 0.45)
    y += 18
    for name in state.my_team:
        entry = pokedex.get(name, {})
        types_str = "/".join(entry.get("types", ["?"]))
        draw_text(frame, f"  {name} ({types_str})", 222, y, (200,255,200), 0.38)
        y += 15

    y += 8
    draw_text(frame, "[ 상대 팀 ]", 220, y, (100,180,255), 0.45)
    y += 18
    for name in state.opp_team:
        entry = pokedex.get(name, {})
        types_str = "/".join(entry.get("types", ["?"]))
        draw_text(frame, f"  {name} ({types_str})", 222, y, (180,210,255), 0.38)
        y += 15

    # 승리 확률
    win_prob = state.get_win_prob()
    if win_prob is not None:
        draw_panel(frame, 215, 395, 210, 40)
        pct = int(win_prob * 100)
        col = (0,255,100) if pct >= 55 else (0,100,255) if pct <= 45 else (0,220,255)
        draw_text(frame, f"승리 확률: {pct}%", 220, 420, col, 0.5)


# ── ROI 디버그 / 크롭 ────────────────────────────────────────────────────────

BATTLE_ROIS = ["my_pokemon", "my_hp", "opp_pokemon"]
SELECT_ROIS = ["my_team", "opp_team"]


def draw_roi_debug(frame, screen):
    keys = BATTLE_ROIS if screen == "battle" else SELECT_ROIS
    colors = {
        "my_pokemon": (0,255,0), "my_hp": (0,200,100),
        "opp_pokemon": (0,150,255), "my_team": (0,255,0), "opp_team": (0,150,255),
    }
    for key in keys:
        x1, y1, x2, y2 = ROI[key]
        cv2.rectangle(frame, (x1,y1), (x2,y2), colors[key], 1)
        cv2.putText(frame, key, (x1+2, y1+10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, colors[key], 1)


def save_roi_crops(frame, screen):
    keys = BATTLE_ROIS if screen == "battle" else SELECT_ROIS
    for key in keys:
        x1, y1, x2, y2 = ROI[key]
        cv2.imwrite(f"roi_{key}.png", frame[y1:y2, x1:x2])
    print("ROI 크롭 저장 완료: roi_*.png")


# ── 메인 루프 ────────────────────────────────────────────────────────────────

def main():
    pokedex = load_pokedex()
    types, chart = load_type_chart()
    state = BattleState()

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    cv2.namedWindow("Pokemon Champions Helper", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Pokemon Champions Helper", 1280, 960)
    print("오버레이 시작")
    print("  Q: 종료 | H: 모드 전환 | D: ROI 디버그 | C: ROI 크롭")
    print("  배틀 모드: 1/2/3/4=상대기술 | R=초기화 | Z/X=내ATK+/- | N/M=내SPA+/- | V=내랭크초기화")

    debug = False
    MODE = ["off", "select", "battle"]
    mode_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        mode = MODE[mode_idx]

        if mode != "off":
            state.screen = mode
            state.update(frame)

            if debug:
                draw_roi_debug(frame, mode)

            if mode == "battle":
                draw_battle_overlay(frame, state, pokedex, types, chart)
            else:
                draw_select_overlay(frame, state, pokedex, types, chart)

            draw_text(frame, mode.upper(), 5, 15, (255,255,0), 0.5)

        cv2.imshow("Pokemon Champions Helper", frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord('q'):
            break
        elif key == ord('h'):
            mode_idx = (mode_idx + 1) % len(MODE)
            print(f"모드: {MODE[mode_idx].upper()}")
        elif key == ord('d'):
            debug = not debug
            print(f"ROI 디버그: {'ON' if debug else 'OFF'}")
        elif key == ord('c'):
            save_roi_crops(frame, mode if mode != "off" else "battle")
        elif key == ord('r') and mode == "battle":
            state.observed_opp_moves.clear()
            state._cache_item_pred = ("", "", [])
            state.reset_stages("opp")
            print("관찰 기술 + 상대 랭크 초기화")
        elif key in (ord('1'), ord('2'), ord('3'), ord('4')) and mode == "battle":
            idx = key - ord('1')
            if idx < len(_current_opp_moves):
                move = _current_opp_moves[idx]["move"]
                if move not in state.observed_opp_moves:
                    state.observed_opp_moves.append(move)
                    state._cache_item_pred = ("", "", [])
                    state.apply_setup_effect(move, "opp")
                    print(f"기술 관찰 등록: {move}")
                else:
                    state.observed_opp_moves.remove(move)
                    state._cache_item_pred = ("", "", [])
                    print(f"기술 관찰 해제: {move}")
        elif mode == "battle":
            if key == ord('z'):
                state.my_stat_stages["atk"] = min(6, state.my_stat_stages["atk"] + 1)
                print(f"내 ATK 랭크: {state.my_stat_stages['atk']:+d}")
            elif key == ord('x'):
                state.my_stat_stages["atk"] = max(-6, state.my_stat_stages["atk"] - 1)
                print(f"내 ATK 랭크: {state.my_stat_stages['atk']:+d}")
            elif key == ord('n'):
                state.my_stat_stages["spa"] = min(6, state.my_stat_stages["spa"] + 1)
                print(f"내 SPA 랭크: {state.my_stat_stages['spa']:+d}")
            elif key == ord('m'):
                state.my_stat_stages["spa"] = max(-6, state.my_stat_stages["spa"] - 1)
                print(f"내 SPA 랭크: {state.my_stat_stages['spa']:+d}")
            elif key == ord('v'):
                state.reset_stages("my")
                print("내 랭크 초기화")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
