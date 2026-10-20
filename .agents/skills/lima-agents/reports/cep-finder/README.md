# CEP Finder · 결정 리포트 (decision_report.html)

엔진 `scripts/run_cep_finder.py`의 run 폴더를 받아 정의서 v2.3 §12의 `decision_report.html`을 만든다.


> **라벨 숫자 대조** — labels.json 문구의 숫자를 run 원자료·core 계산값과 대조한다. 게이트 기록(gates.json)이 있는 run은 미통과 시 렌더 중단, 기록 이전 run은 산출물에 '숫자 대조 미통과' 배너. 초안: `--allow-unverified-numbers` · 점검만: `--check`.
> **어휘 검사** — 렌더 직전에 분석 작업 용어를 업무 용어로 바꾸고, 문장을 다시 써야 하는 용어가 남으면 멈춘다(`references/lexicon-gate.md` §6). 초안: `--allow-jargon`.

## 답하는 질문
"이 카테고리는 어떤 **상황**에서 찾기 시작하는가 — 허브는 몇 개이고, 각 허브의 7W 슬롯·근거 등급·여정·브랜드 연결은 어떠하며, 무엇부터 공략하는가."

## 분업 (정의서 §4.4)
| 누가 | 무엇 | 파일 |
|---|---|---|
| 엔진 | 캔버스·시즌·여정·허브 조립·게이트·원장 | `core/hub_graph.json` · `out/run_manifest.json` · `raw/*` |
| render.py | YoY·시즌 지수·허브 합·성연령 가중·경로 태그·브랜드 도달·분면·차트·치환 | `out/decision_report.html` |
| 사람/LLM | 허브 라벨·서사·슬롯 텍스트·결정구조 6층·여정 단계 서술·백로그·준비도 | `core/labels.json` (계약: `schema.json`) |

라벨 파일이 없으면 수치만 채우고 서사 자리는 `[labels.json 미작성: …]`으로 남긴다 — 빈 칸을 지어내지 않는다.

## 사용
```bash
# 1) 엔진 run (크레딧 소모) → 90_Output/{YYYYMMDD}-{category}-{gl}-cepfinder/
# 2) (선택) 보강 실측 — keyword_info all(결합쿼리 성연령·인텐트·AIO) · path_finder(허브 자체 여정)
#    raw/*kwinfo_all*.json · raw/paths_{anchor}.json · out/topup_manifest.json 으로 저장하면 렌더러가 자동 인식
# 3) core/labels.json 작성 (schema.json) — llm_tasks.json의 hub_label·family_split 결과를 여기에 적는다
# 4) 렌더 (0크레딧)
python3 .agents/skills/lima-agents/reports/cep-finder/render.py 90_Output/<run 폴더> \
  --copy-to 90_Output/<품목>-CEP-결정리포트-<날짜>.html
```

## 섹션 스파인 (template.html · v2 컨설팅 스토리라인, 2026-08-22)
Executive Summary(답부터 — labels.exec_headline · key_messages[{headline, evidence, implication}] · recommendations) → 준비도 → KPI →
01 진입점 지도(허브 레지스트리: 패밀리·상속·가설 전 판정 + 최근접 자카드) → 02 수요 맥락 → 03 허브 상세(패밀리 카드 + 가설 후보·승격 카드) →
04 결정구조 6층 → 05 여정·경쟁(관문·이탈·브랜드 매트릭스·스위칭·Context 매트릭스·Feature Association) → 06 기회 백로그 →
부록 B 진단(extra_sections) → 부록 A1 증거·코퍼스 / A2 가설 전수표·자카드 / A3 게이트·크레딧·재현.
각 섹션 헤드라인은 labels.section_titles{registry,demand,hubs,decision,journey,backlog}(so-what 한 문장), 승격 매핑은 labels.promoted{B04:{id,status}}.
v1 스파인은 template_v1.html에 보존.
- **어휘 사전(2026-08-22)**: `render.py`의 `GLOSSARY`가 최종 HTML의 텍스트 노드에만(태그·script 제외) 비즈니스 어휘를 적용 —
  허브→진입점 · 결합쿼리→상황+품목 검색어 · 헤드텀→대표 검색어 · 롱테일→세부 검색어 · 언어층→표현 근거(검색량 미보고) · 자카드→중복도 ·
  co_path→동반 경로 · 슬롯→상황 요소 · 전이형→브랜드 경유형 · 스위칭→브랜드 전환 · AIO/PAA→AI 검색 요약/연관 질문 ·
  candidate/confirmed/deferred/demoted/unsupported→후보/확정/보류/재분류/기각 · MEASURED/DERIVED→실측/산출. `labels.friendly=false`로 끌 수 있음.
- 진입점 목록(01)은 기본적으로 재분류·기각을 숨기고 부록 A2 전수표로 보낸다(`labels.registry_hide_rejected=false`로 표시).

## 섹션 스파인 (v1, 참고)
마스트헤드(워터마크 run_id·엔진·정의서·어댑터) → 준비도 배너 → KPI 4 → 01 상황 캔버스(패밀리별 허브/희박/패싯) →
02 수요·시즌(헤드텀 24개월 + 허브별 시즌 지수) → 03 허브 카드(결합쿼리 bar·성연령·7W 슬롯·등급) →
04 결정구조 6층 → 05 상황측 여정 → 06 브랜드×허브 매트릭스(경로 도달) → 07 기회 4분면·백로그 → 푸터(크레딧·게이트·등급·가드레일)

## 규율
- 테마: 라이트 기본 + OS 다크 + `data-theme` 스탬프 3상태. 색은 토큰으로만.
- 차트는 inline SVG(외부 CDN 금지). 렌더는 `render.py`로만 — sed/f-string 주입 금지.
- 미측정과 0을 구분한다: 여정 없는 허브는 회색(점선)·"여정 미실측", 4분면에서도 점선 버블.
- 브랜드 도달은 경로 수 기준 근사 — "SoV"라 부르지 않는다. 단독 기업명 노드(○○전자 등)는 도달로 세지 않는다.
- 브랜드 별칭 정본은 버티컬 `references/brand-map.md`(×/○ 계약)를 파싱한다 (`--brand-map`으로 교체 가능).
- 허브 YoY·성연령·인텐트·AIO는 `keyword_info(all)` 보강 실측이 있을 때만 채운다 — 없으면 "미측정".

## 제품 앵커 run (엔진 v0.2 `--anchor-level product`)
`hub_graph.json`에 `anchor_level·alias_groups·probe·transition·inherited_hubs`가 추가된다. 렌더러는 labels.hubs가 없으면
`inherited_hubs`를 회색 상속 카드로 자동 생성하고, 캔버스에 별칭군 카드를, 매트릭스에 경쟁 동반·자사 라인 분기 행을 넣는다.
sense-file에 `category`(품목) · `alias_groups` · `own_brand` · `own_lines`를 적고 `--inherit-from <품목 run>`을 준다.

### v0.3 추가 (제품 모드)
`hub_graph.switching`(B7 — 자사↔경쟁 순서·이탈/유입 트리거, 세션 인접 집계) · `hub_graph.context_matrix`(B9 — 컨텍스트×브랜드 결합쿼리
볼륨, 겹침 지수·무브랜드 여지·자사 비중)를 06 섹션 `{{COMPETITION_EXTRA}}` 블록으로 자동 렌더. sense-file에 `competitors`(필수) ·
`contexts`/`brand_set`(선택)을 준다. labels `switching_note` · `context_matrix_note`로 판독 문장을 덮어쓴다.

### v0.4 추가 — 기능 앵커 (`--anchor-level feature`, B8)
기능은 CEP가 아니라 Need와 Product 사이에 개입하는 엔티티다. sense-file에 `feature_variants`·`understanding_terms`·`competing_features`
(브랜드·기능·note — 등급 assumption)·`layer_lexicon`(선택)을 주면 `hub_graph.feature`(변형×이해형 캔버스·변형쌍 차이/vs·경쟁 기능 볼륨)와
`hub_graph.association`(층별 경로 수·앞/뒤·상대 위치·사슬 순서 — 층: 상황·KBF/컨텍스트·기능 변형·자사 라인·자사/경쟁 브랜드·경쟁 기능·
평가·구매·**모델 코드**)이 생기고 05 섹션 `{{FEATURE_BLOCK}}`으로 렌더된다. `core/ontology_delta.jsonl`에 Technology 후보·
`competes_with(assumption)`·`attaches_to(derived)` 엣지를 append-only로 제안한다(승인 전 온톨로지 직접 수정 없음).
Context×브랜드 매트릭스는 기능 모드에서 기본 생략(`--with-context-matrix`).

### v0.5 추가 — S2 증거 · S3 롱테일 · S5 가설 선행
- **S2** `serp`(시드당 30) — 품목 + 별칭군 헤드 + 성립 브리지 + `sense.evidence_seeds`(상한 `--serp-max` 12). AIO·PAA·연관검색·자연결과를 인용 원문·수집시각과 함께 `raw/serp_*.json`에 보존(grade extracted). 01 섹션 `{{EVIDENCE_BLOCK}}`.
- **S3** `intent_finder vt=0`(시드당 30+2N) — 품목 + `sense.longtail_seeds` + 공간 시드(`sense.space_seeds`, 기본 어댑터 spaces×3) → `ads_info` 1/kw. **0볼륨은 언어층으로 보존**(규모 합산 금지), 노이즈는 개수·볼륨 양 기준 플래그만. `hub_graph.longtail`.
- **S5** 가설 파일이 없으면 `core/hypothesis_tasks.json`을 발주(증거·코퍼스·7W 템플릿) → 세션 LLM이 `core/hypotheses.json`을 쓰고 `--hypotheses`로 재실행(0크레딧). 코퍼스 봉인 매칭 → supported/unsupported 보존 · 성립 요건(pre·W1·W2|W3·3슬롯) + HUB_FLOOR 통과만 허브 후보(`CEP-{cat}-Hnn`) · **기각률 0% = G14 편향 경고**. 03 섹션 `{{HYPOTHESIS_BLOCK}}`.
- 편향 통제 규칙: `--blind`로 발주(코퍼스·여정 노드 제외)하고 가설은 증거만 보고 쓴다. keywords_expected는 예측이며 안 맞으면 unsupported로 남는다. 확증은 `--match strict`(완전/접두·접미 일치) 권장.
  같은 세션이 코퍼스를 본 적 있으면 완전 블라인드가 아니므로 고지.
- 승격 규칙: `candidate` = 성립 요건 ✓ + strong(매칭 ≥3 · 볼륨합 ≥ HUB_FLOOR). 매칭 1~2개는 볼륨이 커도 `deferred`. unsupported는 "언어 부재 또는 시드 범위 밖"으로 표기 — 해당 어휘 시드로 S3 재수확 후 재판정.

### v0.5 S6 — 구별성·병합 판정 (정의서 §4.3)
`--hub-splits labels.json`으로 패밀리 허브의 세분(labels.hubs)을 비교 단위로 쓰고, 가설 후보(candidate)와 전 쌍 자카드를 낸다.
비교 집합은 **렉심 집합**(키워드에서 품목 제거)과 토큰 집합 + 짧은 슬롯 값(≤10자) — 긴 슬롯 서술문은 제외(섞으면 자카드가 희석돼 판정이 무력화됨, 2026-08-22 실측).
판정: J≥0.7 병합 제안 · 0.6~0.7 사람 판단 · 포함도≥0.8 & J≥0.3 흡수(하위 허브) 제안 · J≥0.3 또는 공유 렉심 ≥2 연관(교차참조) · 그 외 유지. `hub_graph.merge` → 03 섹션 `{{MERGE_BLOCK}}`(매트릭스·통합 제안). 최종 병합·분리는 승인 세션.

## 엔진 v0.6 (2026-08-22) — B13·B14·B15 + 증거 사슬·지표 근거
- **B14 기능 사전** — 버티컬 기능 사전(adapter `A4.feature_lexicon`): 기능 고유명 → 편익 → 소비자 일반어 → 경쟁 대응(extracted) → `not_this_feature`(같은 라인의 다른 수요). feature 모드 S0에서 sense에 병합(sense 우선), S1c가 일반어 볼륨 실측(일반어/고유명 비율), 일반어·편익 키워드는 S3·S2 시드에 자동 합류.
- **S0b 일반어 동음이의 검증(B14 보강, 2026-08-22)** — consumer_terms마다 path_finder(`--sense-paths` 100)로 경로를 받아 앵커 외 노드를 사전 `sense_rules.homonym`(먼저)·`sense_rules.feature`(다음)로 분류 → 기능 의미 비중. `confirmed ≥0.6 / ambiguous 0.3~0.6 / homonym <0.3`. homonym 어휘는 S1c 볼륨을 환산값으로, S3c 기능 연결 어휘에서 제외(일반어는 어순 그대로 매칭). 볼륨 없는 어휘는 미측정. `--no-sense-check`. **일반어는 AI 요약이 아니라 여정으로 검증**한다(AI 요약은 기능으로 해석해도 여정은 다른 문맥일 수 있다).
- **B13 편익 7W 분해(S3c)** — 분해 사전 `decomposition_lexicon[품목]`(who/when/what/while/where × 시드 템플릿 `{c}`·`{f}` × `narrative_terms`)로 셀을 만들고 셀별 시드를 자동 수확(intent_finder vt=0 → ads_info). 셀 판정 사다리: `search_target`(볼륨 검색어 ≥3 & 합 ≥500) → `weak_signal` → `language_only`(0볼륨 표현) → **`narrative_only`(검색어 없음·기사/AI 요약에 존재 = 대두 맥락 후보)** → `no_evidence`. `feature_linked_n` = 셀 쿼리 중 기능·일반어·편익 어휘 포함 건수 — 0이면 "품목 수요(기능 연결 미확인)"로 역할 문구에 명기. 수확 쿼리는 코퍼스에 합류해 S5 매칭 대상이 되고, 가설은 `cell` 필드로 셀과 연결된다. **셀당 `seeds[]` 2~3개 필수**(1개면 경고 — 근거 없음이 시드 실패인지 부재인지 구분 불가) · `seed_results`로 시드별 연관어 수 기록 · `--no-benefit` · `--benefit-seeds-max`(시드 총수 상한, 기본 64 · 초과 시 셀당 뒤 시드부터 제외).
- **서사 전용 시드(`narrative_seeds`)** — 품목 결합 쿼리가 전혀 없는 셀용. 반드시 실제 쿼리여야 하며(serp는 인덱스 쿼리에만 데이터 — 지어낸 문장은 0건) 엔진이 ads_metrics로 존재를 확인한 뒤 볼륨 있는 시드만 serp 조회, 결과 중 품목·기능 어휘가 함께 나오는 항목만 `narrative_seed_hits`로 인정(셀 `serp_hits`에 합산 → narrative_only/C 승격 가능). 품목·기능은 없지만 `benefit_lexemes`(꺼내·보관·문 열…)만 일치하는 항목은 `benefit_narrative_hits`로 분리 집계 → verdict `benefit_narrative` · 단계 **C2**(C 아래·D 위).
- **B15 스펙 경계** — `not_this_feature` → `off_feature` 플래그(S3·S3c·S5). S5 볼륨합에서 제외(`backing.off_feature_excluded`).
- **증거 사슬** — S5 가설마다 `evidence_chain`: ① serp 발췌(시드·수집시각·raw 파일·원문 확인 여부) ② 검색어(수확 시드·실측 커넥터·raw 파일·사후 여부) ③ 여정 동반 경로 예시(path_finder raw) ④ 관계망(cluster_finder) 사용 여부. 렌더러 부록 A2 가설표 아래 행으로 표시.
- **지표 산출 근거표** — 부록 A3 `{{PROVENANCE_BLOCK}}`: 모든 지표의 커넥터·필드·계산 규칙·raw 파일. `labels.provenance_note`·`labels.benefit_note`로 각주 덮어쓰기.
- **셀 정렬(2026-08-22 확정)** — A 검색 타겟·기능 연결 → B 약한 신호·기능 연결 → C 서사 맥락(기능 연결 검색어 없음 + 기사/AI 요약 존재 — narrative_only·미연결 약한 신호·표현만) → D 품목 수요(검색량 있으나 기능 연결 0·서사 없음) → E 표현만 → F 근거 없음 → G 미수집 · 단계 내 볼륨합↓ 서사 건수↓ 기능 연결↓ 사전순. `cells[].tier/rank` 로 기록, 렌더 표는 단계 구분행.

## 파생 산출물
- **CEP 카드 덱** — `listeningmind-universal/scripts/render_cep_deck.py`(deck.json → 카드 덱 HTML). run 결과를
  카드·NI/KBF·매트릭스·부재 판정·크로스 패턴으로 요약할 때 사용(샘플: `examples/cep-deck-sample.json`).

## 한계 (v0.1)
- 여정 노드 태그 어휘는 내구재 기본값 — 카테고리에 맞게 `labels.tag_lexicon`으로 덮어쓴다.
- Opportunity Score 산식(§10.2)은 허브 수가 적을 때 순위 백분위가 거칠어 점수 대신 분면·drivers·tier로 표기한다.
- W6·W7(AIO·PAA 발췌) 원천은 엔진 v0.1이 수집하지 않으므로 슬롯은 대개 공백으로 남는다.
