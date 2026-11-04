"""다리 — 차트 정본은 `.claude/skills/lm-chart/lib/palette_check.py` 로 옮겼다(2026-10-25 · 공개 독립 스킬).
lima-agents 안의 `from lib import palette_check` 이 그대로 동작하도록 같은 이름을 다시 내보낸다. 여기에 코드를 더하지 않는다."""
import importlib.util as _iu
from pathlib import Path as _P

_src = _P(__file__).resolve().parents[2] / "lm-chart/lib/palette_check.py"
if not _src.is_file():
    raise ImportError(f"차트 정본이 없다: {_src} — lm-chart 스킬이 lima-agents 와 나란히 있어야 한다")
_spec = _iu.spec_from_file_location("lm_chart_palette_check", _src)
_mod = _iu.module_from_spec(_spec)
import sys as _sys
_sys.modules[_spec.name] = _mod          # dataclass 가 모듈을 sys.modules 에서 찾는다
_spec.loader.exec_module(_mod)
globals().update({k: v for k, v in vars(_mod).items() if not k.startswith("__")})
