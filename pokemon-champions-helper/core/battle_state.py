"""
배틀 상태 감지 및 포켓몬 이름 파싱
"""
import json
import numpy as np
from difflib import get_close_matches
from pathlib import Path
from core.ocr_engine import OcrEngine, crop
from core.stat_calc import calc_lv50_stats, estimate_spread

DATA_DIR = Path(__file__).parent.parent / "data"

SETUP_MOVES: dict[str, dict[str, int]] = {
    "swordsdance":    {"atk": +2},
    "dragondance":    {"atk": +1, "spe": +1},
    "nastyplot":      {"spa": +2},
    "calmmind":       {"spa": +1, "spd": +1},
    "quiverdance":    {"spa": +1, "spd": +1, "spe": +1},
    "shellsmash":     {"atk": +2, "spa": +2, "spe": +2, "def": -1, "spd": -1},
    "bulkup":         {"atk": +1, "def": +1},
    "irondefense":    {"def": +2},
    "acidarmor":      {"def": +2},
    "agility":        {"spe": +2},
    "rockpolish":     {"spe": +2},
    "growth":         {"atk": +1, "spa": +1},
    "workup":         {"atk": +1, "spa": +1},
    "coil":           {"atk": +1, "def": +1},
    "honeclaws":      {"atk": +1},
    "shiftgear":      {"atk": +1, "spe": +2},
    "geomancy":       {"spa": +2, "spd": +2, "spe": +2},
    "tidyup":         {"atk": +1, "spe": +1},
    "victorydance":   {"atk": +1, "def": +1, "spe": +1},
    "clangoroussoul": {"atk": +1, "def": +1, "spa": +1, "spd": +1, "spe": +1},
    "filletaway":     {"atk": +2, "spa": +2, "spe": +2},
    "terablast":      {},  # 변화기 아님 — 공격기, 여기선 제외
}


def load_pokemon_names() -> set[str]:
    path = DATA_DIR / "pokemon.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return set(data.keys())
    return set()


def detect_screen(frame: np.ndarray) -> str:
    left_panel = frame[80:450, 5:210]
    avg = left_panel.mean()
    return "select" if avg < 80 else "battle"


class BattleState:

    def __init__(self):
        self.ocr = OcrEngine()
        self.poke_names = load_pokemon_names()
        self.screen = "unknown"
        self.my_pokemon = ""
        self.opp_pokemon = ""
        self.my_hp = None
        self.my_team: list[str] = []
        self.opp_team: list[str] = []
        self.observed_opp_moves: list[str] = []
        self.my_moves: list[str] = []  # 수동 입력 기술 (비어 있으면 Smogon 기준)
        self.my_stat_stages:  dict[str, int] = {s: 0 for s in ("atk","def","spa","spd","spe")}
        self.opp_stat_stages: dict[str, int] = {s: 0 for s in ("atk","def","spa","spd","spe")}
        self._frame_count = 0
        self._smogon: dict = {}
        self._move_types: dict = {}
        self._set_clf = None
        self._win_pred = None
        self._models_loaded = False
        self._name_pool: list[str] = []
        self._my_team_lookup: dict[str, dict] = {}  # ocr_alias.lower() → team entry
        self._load_my_team()
        # 캐시: 같은 포켓몬이면 재계산 안 함
        self._cache_opp_moves: tuple[str, list] = ("", [])
        self._cache_my_moves:  tuple[str, list] = ("", [])
        self._cache_item_pred: tuple[str, str, list] = ("", "", [])
        self._cache_win_prob:  tuple[str, str, float | None] = ("", "", None)

    def _load_my_team(self):
        """my_team.json 로드 → ocr_alias 기반 룩업 테이블 생성"""
        path = DATA_DIR / "my_team.json"
        if not path.exists():
            return
        for entry in json.loads(path.read_text(encoding="utf-8")):
            alias = entry.get("ocr_alias", entry["name"])
            self._my_team_lookup[alias.lower()] = entry
            self._my_team_lookup[entry["name"].lower()] = entry

    def _load_models(self):
        if self._models_loaded:
            return

        path = DATA_DIR / "smogon_sets.json"
        if path.exists():
            self._smogon = json.loads(path.read_text(encoding="utf-8"))

        mpath = DATA_DIR / "move_types.json"
        if mpath.exists():
            self._move_types = json.loads(mpath.read_text(encoding="utf-8"))

        try:
            from ml.set_classifier import SetClassifier
            self._set_clf = SetClassifier.load()
        except Exception as e:
            print(f"SetClassifier 로드 실패: {e}")

        try:
            from ml.win_predictor import WinPredictor
            self._win_pred = WinPredictor.load()
        except Exception as e:
            print(f"WinPredictor 로드 실패: {e}")

        # 퍼지 매칭용 이름 풀: smogon 키 + pokedex 키 + 내 팀 alias 합집합
        pool = set(self._smogon.keys()) | self.poke_names
        for entry in self._my_team_lookup.values():
            pool.add(entry.get("ocr_alias", entry["name"]))
        self._name_pool = list(pool)
        self._models_loaded = True

    def _resolve_name(self, raw: str) -> str:
        """OCR 오인식 이름 → 가장 가까운 포켓몬 이름으로 보정. 매칭 실패 시 빈 문자열 반환."""
        if not raw or len(raw) < 3:
            return ""
        # 숫자만 / 퍼센트 포함 / 특수문자만 → 무시
        cleaned = raw.replace("%", "").replace(" ", "").replace("/", "")
        if cleaned.isdigit():
            return ""
        self._load_models()
        if raw in self._name_pool:
            return raw
        matches = get_close_matches(raw, self._name_pool, n=1, cutoff=0.6)
        if not matches:
            return ""
        resolved = matches[0]
        if resolved != raw:
            print(f"  이름 보정: {raw!r} -> {resolved!r}")
        return resolved

    def get_opp_top_moves(self, poke_name: str) -> list[dict]:
        """smogon 채용률 top 4 기술 [{"move": str, "type": str|None}]"""
        if self._cache_opp_moves[0] == poke_name:
            return self._cache_opp_moves[1]
        self._load_models()
        data = self._smogon.get(poke_name, {})
        result = [self._move_info(m["move"]) for m in data.get("top_moves", [])[:4]]
        self._cache_opp_moves = (poke_name, result)
        return result

    def get_my_top_moves(self, poke_name: str) -> list[dict]:
        """내 포켓몬 기술 목록 반환. 수동 입력 기술이 있으면 우선 사용."""
        if self.my_moves:
            return [self._move_info(m) for m in self.my_moves]
        if self._cache_my_moves[0] == poke_name:
            return self._cache_my_moves[1]
        self._load_models()
        data = self._smogon.get(poke_name, {})
        result = [self._move_info(m["move"]) for m in data.get("top_moves", [])[:4]]
        self._cache_my_moves = (poke_name, result)
        return result

    def _move_info(self, move_id: str) -> dict:
        """move_types.json에서 기술 정보 반환 (type, bp, cat, pri)"""
        raw = self._move_types.get(move_id)
        if isinstance(raw, dict):
            return {
                "move": move_id,
                "type": raw.get("type"),
                "bp":   raw.get("bp", 0),
                "cat":  raw.get("cat", "Status"),
                "pri":  raw.get("pri", 0),
            }
        # 구 포맷(문자열) 호환
        return {"move": move_id, "type": raw, "bp": 0, "cat": "Status", "pri": 0}

    def apply_setup_effect(self, move_id: str, target: str = "opp"):
        """setup move가 사용됐을 때 랭크 변화 적용. target: 'opp' or 'my'"""
        changes = SETUP_MOVES.get(move_id, {})
        if not changes:
            return
        stages = self.opp_stat_stages if target == "opp" else self.my_stat_stages
        for stat, delta in changes.items():
            stages[stat] = max(-6, min(6, stages[stat] + delta))
        print(f"  {target} 랭크 변화: {move_id} → {dict(stages)}")

    def reset_stages(self, target: str = "all"):
        """랭크 초기화. target: 'my', 'opp', 'all'"""
        init = {s: 0 for s in ("atk","def","spa","spd","spe")}
        if target in ("opp", "all"):
            self.opp_stat_stages = dict(init)
        if target in ("my", "all"):
            self.my_stat_stages = dict(init)

    def get_lv50_stats(self, poke_name: str, entry: dict) -> dict[str, int]:
        """레벨 50 실수치 반환. 내 팀은 my_team.json EV, 상대는 Smogon 추정."""
        base = entry.get("base_stats", {})
        team_entry = self._my_team_lookup.get(poke_name.lower())
        if team_entry:
            evs    = team_entry.get("evs", {})
            nature = team_entry.get("nature", "Hardy")
        else:
            self._load_models()
            evs, nature = estimate_spread(self._smogon, poke_name)
        return calc_lv50_stats(base, evs, nature)

    def get_item_prediction(self, poke_name: str) -> list[dict]:
        """SetClassifier: 관찰 기술 → 아이템 예측 top 3"""
        obs_key = ",".join(sorted(self.observed_opp_moves))
        if self._cache_item_pred[:2] == (poke_name, obs_key):
            return self._cache_item_pred[2]
        self._load_models()
        result = []
        if self._set_clf:
            try:
                result = self._set_clf.predict(poke_name, self.observed_opp_moves)[:3]
            except Exception:
                pass
        self._cache_item_pred = (poke_name, obs_key, result)
        return result

    def get_win_prob(self) -> float | None:
        """WinPredictor: 팀 구성 → 승리 확률"""
        my_key  = ",".join(self.my_team)
        opp_key = ",".join(self.opp_team)
        if self._cache_win_prob[:2] == (my_key, opp_key):
            return self._cache_win_prob[2]
        self._load_models()
        result = None
        if self._win_pred and self.my_team and self.opp_team:
            try:
                result = self._win_pred.predict_win_prob(self.my_team, self.opp_team)
            except Exception:
                pass
        self._cache_win_prob = (my_key, opp_key, result)
        return result

    def update(self, frame: np.ndarray):
        self._frame_count += 1
        if self._frame_count % 30 != 0:
            return
        if self.screen == "battle":
            self._update_battle(frame)
        else:
            self._update_select(frame)

    def _pick_best_name(self, texts: list[str]) -> str:
        """OCR 결과 목록에서 포켓몬 이름으로 가장 적합한 것 선택"""
        # 3글자 이상 + 숫자/퍼센트만 아닌 것 우선
        candidates = [t for t in texts if len(t) >= 3 and not t.replace("%","").replace("/","").replace(" ","").isdigit()]
        if not candidates:
            return ""
        # 가장 긴 텍스트부터 시도
        for t in sorted(candidates, key=len, reverse=True):
            resolved = self._resolve_name(t)
            if resolved:
                return resolved
        return ""

    def _update_battle(self, frame):
        my_img  = crop(frame, "my_pokemon")
        opp_img = crop(frame, "opp_pokemon")

        my_texts  = self.ocr.read(my_img)
        opp_texts = self.ocr.read(opp_img)

        my_resolved = self._pick_best_name(my_texts)
        if my_resolved and my_resolved != self.my_pokemon:
            team_entry = self._my_team_lookup.get(my_resolved.lower())
            if team_entry:
                self.my_pokemon = team_entry["name"]
                self.my_moves   = list(team_entry["moves"])
                print(f"  내 포켓몬: {team_entry['name_kr']} ({team_entry['name']})")
            else:
                self.my_pokemon = my_resolved

        opp_resolved = self._pick_best_name(opp_texts)
        if opp_resolved and opp_resolved != self.opp_pokemon:
            self.opp_pokemon = opp_resolved
            self.observed_opp_moves = []        # 상대 교체 시 관찰 기술 초기화
            self.reset_stages("opp")            # 랭크도 초기화

        hp_img = crop(frame, "my_hp")
        self.my_hp = self.ocr.read_hp(hp_img)

    def _filter_team(self, texts: list[str]) -> list[str]:
        """OCR 결과에서 포켓몬 이름만 추출 (아이템명·숫자·짧은 텍스트 제거)"""
        self._load_models()
        result = []
        for t in texts:
            name = self._resolve_name(t)
            if name and name in self._name_pool and name not in result:
                result.append(name)
        return result

    def _update_select(self, frame):
        my_img  = crop(frame, "my_team")
        opp_img = crop(frame, "opp_team")
        self.my_team  = self._filter_team(self.ocr.read(my_img))[:6]
        self.opp_team = self._filter_team(self.ocr.read(opp_img))[:6]
