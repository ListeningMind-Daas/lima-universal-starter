# CEP 7W 분류 · LLM 병렬 분류 방식

**이 단계는 절대 스킵 금지**. cep_grouped가 없으면 CEP뷰가 비어 보임.

## CEP (Category Entry Point) · Ehrenberg-Bass 7W 프레임워크

Byron Sharp · Jenni Romaniuk이 개발 · 소비자가 카테고리를 떠올리는 <b>진입점</b> 7가지.

| W | 의미 | 예 (전 도메인 공통) |
|---|---|---|
| WHY | 왜? · 동기·목적 | "다이어트하려고", "선물하려고", "잠 못 자서" |
| WHEN | 언제? · 시점·타이밍 | "아침에", "운동 후", "겨울에", "출근길에" |
| WHERE | 어디서? · 장소·채널 | "편의점", "약국", "온라인", "카페에서" |
| WHILE | 무엇 하면서? · 동반 활동 | "운동 중", "공부 중", "요리하며", "운전하며" |
| WHOM | 누구와/누구를 위해? · 대상 | "여성용", "아이", "노인", "초보" |
| WITH_WHAT | 무엇과 함께? · 조합·페어링 | "우유와", "커피와", "빵과", "약과" |
| HOW_FEEL | 어떤 감정으로? · 상태·감정 | "부작용 걱정", "가성비", "맛있는", "인기" |

## 왜 LLM 병렬 분류인가

**정규식 방식은 도메인 종속.** 전기자전거 시장의 `r'출퇴근'` 패턴이 · 감기약·화장품·자동차 시장에는 안 통한다. 시장마다 다시 정규식 짜는 건 확장 불가.

**LLM 병렬 분류 방식:**
 - Claude가 키워드 자체를 보고 의미로 판단
- 어떤 도메인이든 · 어떤 언어든 (KR/US/JP) 동일 절차
- 배치 100~200개씩 · 병렬 max 3
- 결과에서 자동으로 서브그룹까지 발굴 (하위 클러스터링)

## 분류 절차 (3 스텝)

### Step 1 · 배치 분할

```python
BATCH_SIZE = 150 # 한 번에 Claude가 훑을 키워드 수
batches = [all_kws[i:i+BATCH_SIZE] for i in range(0, len(all_kws), BATCH_SIZE)]
# 예: 1,119 kws → 8 batches
```

### Step 2 · Claude가 배치별로 7W 분류 (병렬 max 3)

각 배치마다 이 프롬프트 · 결과를 JSON으로 받음:

```
당신은 CEP 7W 프레임워크로 키워드를 분류하는 조사원이다.
카테고리: {CATEGORY} (예: 전기자전거)
시장: {GL} (kr/us/jp)

아래 키워드들을 7W 중 하나 이상에 분류하라. 하나도 해당 안 되면 넣지 말 것.

7W 정의 (도메인 공통):
- WHY: 동기·목적·이유. 왜 이걸 원하나. (예: 다이어트, 근성장, 선물)
- WHEN: 시점·타이밍·시즌. (예: 아침, 운동 후, 겨울)
- WHERE: 장소·채널·구매처. (예: 편의점, 온라인, 카페)
- WHILE: 동반 활동·행위 중. (예: 운동 중, 요리하며)
- WHOM: 대상·페르소나·수혜자. (예: 여성용, 아이, 초보)
- WITH_WHAT: 조합·페어링·같이 쓰는 것. (예: 우유와, 커피와)
- HOW_FEEL: 감정·상태·가치·품질. (예: 부작용, 가성비, 맛)

키워드 리스트:
{batch_kws_json}

JSON 응답 (다른 텍스트 없음):
{
 "WHY": ["kw1", "kw2", ...],
 "WHEN": [...],
 ...
}
```

Python으로 병렬 호출 (Claude API · max 3 concurrent):

```python
import asyncio, json
from anthropic import AsyncAnthropic

client = AsyncAnthropic()
sem = asyncio.Semaphore(3)

async def classify_batch(batch, category, gl):
 async with sem:
 msg = await client.messages.create(
 model="claude-opus-4-7",
 max_tokens=4000,
 messages=[{"role": "user", "content": PROMPT.format(
 CATEGORY=category, GL=gl,
 batch_kws_json=json.dumps(batch, ensure_ascii=False)
 )}]
 )
 text = msg.content[0].text.strip()
 # JSON 코드블록 제거
 if text.startswith("```"): text = text.split("```")[1].lstrip("json\n")
 return json.loads(text)

results = await asyncio.gather(*[classify_batch(b, CATEGORY, GL) for b in batches])
```

**주의**: Claude Desktop 안 스킬에서 실행할 때는 Anthropic SDK가 없을 수 있다. 대신 Claude 자신이 대화 안에서 배치별로 직접 분류 (여러 응답 턴 or 한 응답 안에 정리) · 결과를 JSON으로 저장.

### Step 3 · 병합 · 서브그룹 자동 발굴

7W별로 모든 배치 결과 병합 · 각 W 안에서 <b>서브그룹은 Claude가 다시 훑어서 생성</b>:

```python
merged = {w: [] for w in ['WHY','WHEN','WHERE','WHILE','WHOM','WITH_WHAT','HOW_FEEL']}
for result in results:
 for w, kws in result.items():
 merged[w].extend(kws)

# 중복 제거
for w in merged:
 merged[w] = list(dict.fromkeys(merged[w]))
```

이제 각 W별 서브그룹을 Claude가 발굴 · 프롬프트:

```
카테고리: {CATEGORY}
7W 중 {W_KEY} ({W_LABEL})에 분류된 키워드들을 아래에 준다.
이들을 의미가 비슷한 서브그룹 3~7개로 자동 묶어라.
각 서브그룹에 짧은 라벨 (2~5글자) 부여.

키워드:
{merged[w]}

JSON:
{
 "서브그룹 라벨 1": ["kw", ...],
 "서브그룹 라벨 2": ["kw", ...],
 ...
}
```

7W 각각 병렬 · max 3 (7개 W인데 max 3이므로 큐잉).

### Step 4 · 최종 데이터 조립

```python
cep_grouped = {}
for w_key, subgroups_dict in all_subgroups.items():
 subgroups = {}
 for sub_label, kws in subgroups_dict.items():
 kws_sorted = sorted(kws, key=lambda k: -kw2vol.get(k, 0))
 subgroups[sub_label] = {
 "keywords": [{"keyword": k, "volume": kw2vol.get(k, 0)} for k in kws_sorted],
 "count": len(kws_sorted),
 "total_volume": sum(kw2vol.get(k, 0) for k in kws_sorted)
 }
 if subgroups:
 total_kws = set()
 for sg in subgroups.values():
 for k in sg["keywords"]:
 total_kws.add(k["keyword"])
 cep_grouped[w_key] = {
 "label": W_LABELS[w_key], # 아래 표
 "subgroups": dict(sorted(subgroups.items(), key=lambda x: -x[1]["total_volume"])),
 "total_count": len(total_kws),
 "total_volume": sum(kw2vol.get(k, 0) for k in total_kws)
 }
```

W 라벨 (도메인 무관 · 항상 이 문구 사용):

```python
W_LABELS = {
 "WHY": "왜? · 동기·목적",
 "WHEN": "언제? · 시점·타이밍",
 "WHERE": "어디서? · 장소·채널",
 "WHILE": "무엇 하면서? · 동반 활동",
 "WHOM": "누구와/누구를 위해? · 대상",
 "WITH_WHAT": "무엇과 함께? · 조합·페어링",
 "HOW_FEEL": "어떤 감정으로? · 상태·감정",
}
```

## 최종 데이터 구조 (예 · 전기자전거)

```json
{
 "WHY": {
 "label": "왜? · 동기·목적",
 "subgroups": {
 "배달·라이더": {
 "keywords": [
 { "keyword": "전기자전거 배달", "volume": 10686 },
 { "keyword": "배달용 전기자전거", "volume": 4176 }
 ],
 "count": 2,
 "total_volume": 14862
 },
 "출퇴근·이동": {},
 "운동·레저": {},
 "이유·목적": {}
 },
 "total_count": 2,
 "total_volume": 14862
 }
}
```

**다른 도메인 예** (감기약):
```json
{
 "WHY": {
 "subgroups": {
 "감기·인후통": {},
 "코감기·비염": {},
 "예방·면역": {}
 }
 }
}
```

## 크레딧 · 비용

- Claude Opus 병렬 호출 · 배치당 약 2,000 tokens (input+output)
- 1,119 키워드 → 8 배치 → 약 16k tokens (분류) + 7 배치 (서브그룹) → 약 30k tokens 총
- **DaaS 크레딧과 별개** · Anthropic API 청구
- Claude Desktop 안 대화 스킬로 실행 시 · 별도 청구 없이 대화 턴으로 처리

## 자주 하는 실수

1. **정규식으로 대충 처리** · 이제 안 함 · 반드시 LLM 분류
2. **한 번에 1,000개 키워드 던짐** · Claude 컨텍스트 넘침 · 배치 150개
3. **cep_grouped 대신 cep_groups** (구버전 이름) · 반드시 `cep_grouped`
4. **완전 스킵** · CEP뷰 빈 화면
5. **서브그룹 라벨을 영어로** · 한국어 시장이면 한국어 · 영어 시장이면 영어

## 완료 조건

- [ ] 7W 모두 처리 (WHY·WHEN·WHERE·WHILE·WHOM·WITH_WHAT·HOW_FEEL)
- [ ] 각 W에 서브그룹 3~7개 (LLM 자동 발굴)
- [ ] 각 서브그룹에 keywords 리스트 + count + total_volume
- [ ] W 라벨은 W_LABELS 딕셔너리 그대로
- [ ] `CLUSTER_DATA.cep_grouped`에 주입 (이름 `cep_groups` 아님)
