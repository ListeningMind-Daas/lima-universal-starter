#!/usr/bin/env python3
"""배포 패키지 자가 점검 — 0크레딧 · ADK·GCP 없이 돈다 (배포 전에 먼저 실행한다).

도구 모듈이 동봉 스킬만으로 import 되는지, 견적·규칙 문서 읽기가 되는지, 키 없이 유료 도구가 막히는지 본다.
"""
import asyncio, importlib.util, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.pop("LM_API_KEY", None)
os.environ["XDG_CONFIG_HOME"] = str(ROOT / ".selfcheck-no-config")
spec = importlib.util.spec_from_file_location("lima_tools", ROOT / "lima_agent/tools.py")
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)


async def main() -> int:
    assert T.SKILLS == ROOT / "lima_agent/skills", f"동봉 스킬이 아닌 곳을 본다: {T.SKILLS}"
    assert len(T.TOOLS) == 12, len(T.TOOLS)
    est = await T.estimate_credits([{"tool": "keyword_info", "keywords": 10, "data_type": "all"}])
    assert est["total_max"] == 100, est
    refs = await T.list_references()
    assert "references/jobs.md" in refs["listeningmind-universal"], refs
    doc = await T.read_reference("listeningmind-universal", "SKILL.md")
    assert doc["status"] == "ok" and doc["text"], doc.get("message")
    bad = await T.read_reference("lima-agents", "../../agent.py")
    assert bad["status"] == "error"
    r = await T.keyword_info(["테스트"], data_type="ads_metrics")           # 키 없음 → 호출하지 않고 오류
    assert r["status"] == "error" and "키" in r["message"], r
    print(f"자가 점검 통과 · 도구 {len(T.TOOLS)}개 · 규칙 문서 {sum(map(len, refs.values()))}개")
    return 0


sys.exit(asyncio.run(main()))
