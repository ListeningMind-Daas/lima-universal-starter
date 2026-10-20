// ===== 사이드바 모드 · 클러스터 vs 검색인텐트 =====
// 인텐트 4종 · 마케팅팀 표준 한글 라벨
const INTENT_META = {
  i: { label: '정보형', desc: 'Informational · 정보 탐색', color: '#f4a6b8',
       condition: '사용자가 답·설명·방법을 찾는 검색 (예: "전기자전거 면허")',
       usage: 'SEO 블로그·매거진·백서 등 콘텐츠 마케팅 대상 · 인지 단계 유입' },
  n: { label: '이동형', desc: 'Navigational · 특정 사이트·브랜드', color: '#e6c473',
       condition: '특정 브랜드·사이트·앱을 목표로 하는 검색 (예: "삼천리자전거")',
       usage: '브랜드 인지도 지표 · 자사 브랜드 검색량 방어 · 경쟁 브랜드 방어 광고' },
  c: { label: '상업형', desc: 'Commercial · 비교·검토', color: '#8bb8e8',
       condition: '구매 전 비교·리뷰·추천을 찾는 검색 (예: "전기자전거 추천")',
       usage: '비교 콘텐츠·리뷰·인플루언서 마케팅 · 구매 직전 단계 리마인딩' },
  t: { label: '거래형', desc: 'Transactional · 구매 임박', color: '#a8d99b',
       condition: '즉시 구매 의도가 있는 검색 (예: "전기자전거 최저가")',
       usage: '검색 광고 최우선 · 랜딩 페이지 최적화 · CRO(전환 최적화) 핵심' },
};
const INTENT_ORDER = ['i', 'n', 'c', 't'];

function getDominantIntent(kwId) {
  const info = (CLUSTER_DATA.keyword_info || {})[kwId];
  if (!info || !info.intents) return null;
  const it = info.intents;
  const arr = INTENT_ORDER
    .map(k => ({ k, v: Number(it[k] ?? 0) }))
    .filter(x => x.v > 0);
  if (!arr.length) return null;
  arr.sort((a, b) => b.v - a.v);
  return arr[0].k;
}

// 사이드바 모드 상태 · 'cluster' | 'intent' | 'trend'
let sideMode = 'cluster';
// 인텐트 필터 상태 · 초기 = 아무것도 선택 안 됨
const intentActive = new Set();

// ===== 검색노출타입 (SERP features) =====
// features 필드 → 노출타입 카테고리 매핑 · 각 카테고리 = features 하나 or 여러 개 OR
// 노드는 여러 SERP 타입에 속할 수 있음 (multi-membership)
const SERP_META = {
  ai_overview:  { label: 'AI 개요', color: '#a8d99b', fields: ['f_ai_overview'],
                  condition: 'SERP에 AI Overview 요약이 노출',
                  usage: 'CTR 감소 위험 · 답 요약에 자사 정보가 잡히게 하려면 구조화 데이터·권위 확보 필요' },
  ads:          { label: '광고', color: '#e89f6a', fields: ['f_ads_top', 'f_ads_bottom'],
                  condition: 'SERP 상단 또는 하단에 검색 광고 노출',
                  usage: '광고 슬롯 있는 곳 = 상업성 있는 검색 · 광고 진입 검토 · 자연 검색 CTR 감소 감안' },
  snippet:      { label: '추천스니펫', color: '#f4a6b8', fields: ['f_featured_snippet'],
                  condition: 'SERP에 Featured Snippet(강조 스니펫) 노출',
                  usage: '"Position 0" 확보 시 CTR 크게 상승 · 명확한 답변 구조·리스트·표 콘텐츠 유리' },
  images:       { label: '이미지 블록', color: '#8bb8e8', fields: ['f_images'],
                  condition: 'SERP에 이미지 결과 블록 노출',
                  usage: '이미지 SEO · alt·파일명·구조화 데이터 최적화 · 비주얼 콘텐츠 확보' },
  video:        { label: '동영상 블록', color: '#b5a3e0', fields: ['f_video_results', 'f_video_carousels'],
                  condition: 'SERP에 동영상 결과 or 카루셀 노출',
                  usage: 'YouTube SEO 우선 · 튜토리얼·리뷰 영상 제작 · 짧은 폼 콘텐츠 검토' },
  knowledge:    { label: '지식패널', color: '#e6c473', fields: ['f_knowledge_panel'],
                  condition: 'SERP에 지식패널(위키·엔티티 정보) 노출',
                  usage: '브랜드·엔티티 검색 신호 · Wikipedia·구조화 데이터로 자사 지식패널 확보 목표' },
  local:        { label: 'Map pack', color: '#8fd4c8', fields: ['f_local_results'],
                  condition: 'SERP에 지도·로컬 결과 노출 (로컬 검색 의도)',
                  usage: '오프라인 매장 있으면 Google Business Profile 최적화 · 로컬 리뷰 확보' },
  app:          { label: '모바일앱', color: '#c99fdd', fields: ['f_app_results', 'f_google_play'],
                  condition: 'SERP에 앱 결과 or Google Play 링크 노출',
                  usage: '앱 다운로드 유도 검색 · ASO(앱스토어 최적화) 대상 · 앱 링크 광고 검토' },
  rating:       { label: '평점스키마', color: '#f0a8c9', fields: ['f_organic_results_rating'],
                  condition: '자연 검색 결과에 평점·리뷰 별점 노출',
                  usage: '리뷰 스키마 구조화 데이터 필수 · 별점 있으면 CTR 상승 · 리뷰 수집 캠페인' },
  paa:          { label: '관련 질문(PAA)', color: '#9dabe8', fields: ['f_people_also_ask_for'],
                  condition: 'SERP에 "People Also Ask" 관련 질문 박스 노출',
                  usage: '관련 질문 답변 콘텐츠 확장 · Q&A 형식 최적화 · long-tail 유입 확대' },
};
const SERP_ORDER = ['ai_overview','ads','snippet','images','video','knowledge','local','app','rating','paa'];
const serpActive = new Set();

function getSerpTypes(kwId) {
  // 노드가 속한 SERP 타입들 반환 · features 필드 값 > 0이면 그 카테고리에 속함
  const info = (CLUSTER_DATA.keyword_info || {})[kwId];
  const feats = info && info.features;
  if (!feats) return null;
  const result = [];
  SERP_ORDER.forEach(k => {
    const meta = SERP_META[k];
    const has = meta.fields.some(f => Number(feats[f] ?? 0) > 0);
    if (has) result.push(k);
  });
  return result.length ? result : [];
}

// ===== 상업성 (CPC · competition · intent.t) =====
const COMMERCE_META = {
  premium:  { label: '프리미엄 광고',   color: '#e89f6a', desc: 'CPC 상위·경쟁도 HIGH · SEM 최우선',
              condition: 'CPC가 상위 30% 이상이고 경쟁도 HIGH 또는 경쟁 인덱스 70+',
              usage: 'SEM 예산 최우선 배정 · 구매 직결 검색이라 광고 ROI 큼 · 자사 브랜드 없으면 반드시 진입' },
  cheap:    { label: '저비용 고효율',   color: '#a8d99b', desc: 'CPC 낮음·경쟁도 낮음·볼륨 있음 · 진입 기회',
              condition: '볼륨 중위값 이상이고 CPC 낮으며 경쟁도 LOW/MEDIUM',
              usage: '광고 진입 기회 · ROAS 높을 것 · 브랜드 인지도 확보용 · 신규 광고 그룹 우선순위' },
  info:     { label: '비상업 (정보성)', color: '#7ab8f5', desc: '정보 인텐트 우세 · 콘텐츠·SEO 대상',
              condition: '검색 의도가 정보형 50%+ 이고 CPC 낮음',
              usage: 'SEO 블로그·매거진 콘텐츠 대상 · 인지 단계 유입 · 광고보다 자연 검색 최적화' },
  low:      { label: '저가치',          color: '#c9c9d5', desc: 'CPC·볼륨 모두 낮음 · 우선순위 낮음',
              condition: '위 3가지 조건 어디에도 안 맞음 · CPC·볼륨·인텐트 모두 약함',
              usage: '즉시 액션 우선순위 낮음 · 시장 확장 시 롱테일 후보로 검토' },
};
const COMMERCE_ORDER = ['premium', 'cheap', 'info', 'low'];
const commerceActive = new Set();

// CPC 상위/하위 분위수 (전체 노드 기준 · 한번 계산)
const cpcValues = nodes
  .map(n => Number(((CLUSTER_DATA.keyword_info || {})[n.id] || {}).ads_metrics?.cpc ?? 0))
  .filter(v => v > 0)
  .sort((a, b) => a - b);
const CPC_HIGH_THRESHOLD = cpcValues.length > 10 ? cpcValues[Math.floor(cpcValues.length * 0.7)] : 1.0;
const VOL_MID_THRESHOLD = (() => {
  const vols = nodes.map(n => n.volume || 0).filter(v => v > 0).sort((a, b) => a - b);
  return vols.length > 10 ? vols[Math.floor(vols.length * 0.5)] : 100;
})();

function getCommerceCat(kwId) {
  const info = (CLUSTER_DATA.keyword_info || {})[kwId];
  const ads = info && info.ads_metrics;
  if (!ads) return null;
  const cpc = Number(ads.cpc ?? 0);
  const comp = String(ads.competition || '').toUpperCase();
  const compIdx = Number(ads.competition_index ?? 0);
  const nb = nodeIndex.get(kwId);
  const vol = nb ? (nb.volume || 0) : 0;
  const it = info.intents || {};
  const iScore = Number(it.i ?? 0);
  const tScore = Number(it.t ?? 0);

  // 프리미엄 · CPC 상위 + (HIGH 경쟁 or 경쟁 인덱스 70+)
  if (cpc >= CPC_HIGH_THRESHOLD && (comp === 'HIGH' || compIdx >= 70)) return 'premium';
  // 저비용 고효율 · 볼륨 중위 이상 + CPC 낮음(임계 미만) + LOW/MEDIUM
  if (vol >= VOL_MID_THRESHOLD && cpc < CPC_HIGH_THRESHOLD && (comp === 'LOW' || comp === 'MEDIUM' || compIdx < 70)) {
    // 근데 정보성 인텐트가 압도적이면 info로
    if (iScore > 0.6 && tScore < 0.2) return 'info';
    return 'cheap';
  }
  // 비상업 (정보성) · intents.i 우세하고 CPC 낮음
  if (iScore >= 0.5 && cpc < CPC_HIGH_THRESHOLD) return 'info';
  // 나머지 · 저가치
  return 'low';
}

// ===== 유저특성 (demography) =====
// 노드는 여러 세그먼트에 속할 수 있음 (성별·연령대 각각 · multi-membership)
// flagField · 사내 태깅 1/0 필드 (m_ prefix · marker) · 우선
// ratioField · 실제 비율 · flag 없을 때 폴백
const USER_META = {
  female:  { label: '여성', color: '#f4a6b8', kind: 'gender', flagField: 'm_f_gender_ratio', ratioField: 'f_gender_ratio',
             condition: '이 키워드를 여성이 유의미하게 검색하는 것으로 분류된 경우',
             usage: '여성 타겟 크리에이티브 · 인플루언서 매칭 · 라이프스타일 매체 노출' },
  male:    { label: '남성', color: '#7ab8f5', kind: 'gender', flagField: 'm_m_gender_ratio', ratioField: 'm_gender_ratio',
             condition: '이 키워드를 남성이 유의미하게 검색하는 것으로 분류된 경우',
             usage: '남성 타겟 크리에이티브 · 기능·성능 소구 · 유튜브·헬스 매체' },
  a13:     { label: '10대', color: '#c0d67c', kind: 'age', flagField: 'm_a13', ratioField: 'a13_ratio',
             condition: '이 키워드를 10대가 유의미하게 검색하는 것으로 분류된 경우',
             usage: '10대 대상 톤·시각 크리에이티브 · 틱톡·인스타 릴스 · 학교·트렌드 문맥' },
  a20:     { label: '20대', color: '#a8d99b', kind: 'age', flagField: 'm_a20', ratioField: 'a20_ratio',
             condition: '이 키워드를 20대가 유의미하게 검색하는 것으로 분류된 경우',
             usage: '20대 라이프스타일·SNS 유통 · 인플루언서·크리에이터 캠페인' },
  a25:     { label: '25~', color: '#8fd4c8', kind: 'age', flagField: 'm_a25', ratioField: 'a25_ratio',
             condition: '이 키워드를 25~29세가 유의미하게 검색하는 것으로 분류된 경우',
             usage: '초기 직장인·독립 세대 · 실용·가성비 소구' },
  a30:     { label: '30대', color: '#b5a3e0', kind: 'age', flagField: 'm_a30', ratioField: 'a30_ratio',
             condition: '이 키워드를 30대가 유의미하게 검색하는 것으로 분류된 경우',
             usage: '가족·건강·재테크 문맥 · 유튜브·검색 광고 강함' },
  a40:     { label: '40대', color: '#c99fdd', kind: 'age', flagField: 'm_a40', ratioField: 'a40_ratio',
             condition: '이 키워드를 40대가 유의미하게 검색하는 것으로 분류된 경우',
             usage: '건강·자산·자녀 관련 · TV+디지털 크로스 채널 · 신뢰 소구' },
  a50:     { label: '50대+', color: '#e0b088', kind: 'age', flagField: 'm_a50', ratioField: 'a50_ratio',
             condition: '이 키워드를 50대 이상이 유의미하게 검색하는 것으로 분류된 경우',
             usage: '시니어 세그먼트 · 큰 폰트·명확한 UX · 카카오·검색 우세' },
};
const USER_ORDER = ['female','male','a13','a20','a25','a30','a40','a50'];
const userActive = new Set();
const USER_RATIO_FALLBACK = { gender: 55, age: 25 };

function getUserSegments(kwId) {
  const info = (CLUSTER_DATA.keyword_info || {})[kwId];
  const demo = info && info.demography;
  if (!demo) return null;
  const result = [];
  USER_ORDER.forEach(k => {
    const meta = USER_META[k];
    // 1) flag 우선 (사내 태깅)
    const flagVal = demo[meta.flagField];
    if (flagVal !== undefined && flagVal !== null && Number(flagVal) > 0) {
      result.push(k);
      return;
    }
    // 2) ratio 폴백
    const ratio = Number(demo[meta.ratioField] ?? 0);
    if (ratio >= USER_RATIO_FALLBACK[meta.kind]) result.push(k);
  });
  return result;
}

// ===== 트렌드 =====
// 3카테고리 · 상승(+15%↑) · 안정 · 하락(-15%↓)
const TREND_META = {
  up:    { label: '상승', desc: '3개월 +15%↑ · 라이징',   color: '#a8d99b', threshold: 0.15,
           condition: '최근 3개월 검색량이 이전 3개월 대비 +15% 이상 증가',
           usage: '초기 진입 기회 · 신규 캠페인·콘텐츠 우선 · 트렌드 리딩 브랜드 포지셔닝' },
  flat:  { label: '안정', desc: '±15% 이내 · 안정 수요',   color: '#c9c9d5',
           condition: '최근 3개월 검색량이 이전 대비 ±15% 이내 · 안정적 수요',
           usage: '지속 예산 배분 · 유입 안정성 확보 · 시즌·이벤트 캠페인 base' },
  down:  { label: '하락', desc: '3개월 -15%↓ · 감소',     color: '#f4a6b8', threshold: -0.15,
           condition: '최근 3개월 검색량이 이전 대비 -15% 이상 감소',
           usage: '시장 위축 신호 · 카테고리 이동·대체 카테고리 조사 필요 · 예산 재배분 검토' },
};
const TREND_ORDER = ['up', 'flat', 'down'];
const trendActive = new Set();

function getTrend(kwId) {
  const info = (CLUSTER_DATA.keyword_info || {})[kwId];
  const t = info && info.ads_metrics && info.ads_metrics.volume_trend;
  if (t === null || t === undefined) return null;
  return Number(t);
}
function getTrendCat(kwId) {
  const t = getTrend(kwId);
  if (t === null) return null;
  // 검색량 0인 노드는 트렌드 신뢰 낮음 (Google Ads가 낮은 볼륨을 0으로 반올림)
  const nb = nodeIndex.get(kwId);
  const vol = nb ? (nb.volume || 0) : 0;
  if (vol === 0) return 'flat';
  if (t >= TREND_META.up.threshold) return 'up';
  if (t <= TREND_META.down.threshold) return 'down';
  return 'flat';
}

// ===== 급등 스코어 =====
// monthly_volume 기반 · 최근 3개월 평균 vs 12개월 이동평균 비교
// 반환 · { spike, coldStart, kind, recent3, ma12, priorMA }
function getSpikeMetrics(kwId) {
  const info = (CLUSTER_DATA.keyword_info || {})[kwId];
  const mv = info && info.monthly_volume;
  if (!Array.isArray(mv) || mv.length < 6) return null;
  const vals = mv.map(m => Number(m.total ?? 0));
  const n = vals.length;
  // 최근 3개월
  const recent3 = vals.slice(-3).reduce((a, b) => a + b, 0) / 3;
  // 12개월 이동평균 (최근 12개월)
  const window = Math.min(12, n);
  const ma12 = vals.slice(-window).reduce((a, b) => a + b, 0) / window;
  // 이전 기간 평균 (최근 6개월 제외한 나머지) · cold start 판정용
  const priorSlice = vals.slice(0, Math.max(0, n - 6));
  const priorMA = priorSlice.length ? priorSlice.reduce((a, b) => a + b, 0) / priorSlice.length : 0;
  // 최근 6개월
  const recent6 = vals.slice(-6).reduce((a, b) => a + b, 0) / 6;

  // Spike Score · 최근 3개월이 12개월 평균의 몇 배 (- 1로 percentage-like)
  const spike = ma12 > 0 ? (recent3 / ma12 - 1) : (recent3 > 0 ? 5 : 0);
  // Cold Start Score · 과거는 거의 0인데 최근에 등장
  //   priorMA < 5 이고 recent6 >= 10 이상 → cold start 후보
  const isColdStart = priorMA < 5 && recent6 >= 10;
  // 분류 kind
  let kind = 'growth';  // 완만 상승
  if (isColdStart) kind = 'coldStart';
  else if (spike >= 1.0) kind = 'spike';  // 이동평균의 2배 이상
  return { spike, coldStart: isColdStart ? recent6 / Math.max(1, priorMA) : 0, kind, recent3, ma12, priorMA, recent6 };
}

// 상승 카드 안 재분류 태그 정의
const SPIKE_TAG_META = {
  spike:     { label: '급등', color: '#e63946', desc: '최근 3개월이 12개월 평균의 2배 이상 · 진짜 튀는 것' },
  coldStart: { label: '신규', color: '#7c5ec4', desc: '오래 검색이 없다가 최근 6개월에 갑자기 나타남' },
  growth:    { label: '완만', color: '#3a8f3a', desc: '이동평균과 비슷하게 꾸준히 상승' },
};

function renderIntentFilter() {
  const listEl = document.getElementById('intent-filter-list');
  const emptyEl = document.getElementById('intent-empty-msg');
  const hasData = nodes.some(n => getDominantIntent(n.id) !== null);
  if (!hasData) {
    listEl.innerHTML = '';
    emptyEl.style.display = 'block';
    return;
  }
  emptyEl.style.display = 'none';

  // 각 인텐트별 노드 카운트
  const counts = { i: 0, n: 0, c: 0, t: 0, none: 0 };
  nodes.forEach(n => {
    const d = getDominantIntent(n.id);
    if (d) counts[d]++; else counts.none++;
  });

  listEl.innerHTML = INTENT_ORDER.map(k => {
    const meta = INTENT_META[k];
    const active = intentActive.has(k);
    const swatchStyle = active ? `background: ${meta.color};` : '';
    return `
      <div class="intent-filter-item ${active ? 'active' : ''}" data-intent="${k}">
        <span class="swatch" style="${swatchStyle}"></span>
        <span class="label">${meta.label}</span>
        <span class="count">${(counts[k] || 0).toLocaleString()}</span>
      </div>
    `;
  }).join('');

  listEl.querySelectorAll('.intent-filter-item').forEach(el => {
    el.addEventListener('click', () => {
      const k = el.dataset.intent;
      if (intentActive.has(k)) intentActive.delete(k);
      else intentActive.add(k);
      const active = intentActive.has(k);
      el.classList.toggle('active', active);
      const swatch = el.querySelector('.swatch');
      swatch.style.background = active ? INTENT_META[k].color : '';
      applyNodeColors();
      try { renderCardView(); } catch(e) { console.error('renderCardView failed:', e); }
      try { renderKwList(document.getElementById('kw-search').value || ''); } catch(e) { console.error('renderKwList failed:', e); }
    });
  });
}

function renderTrendFilter() {
  const listEl = document.getElementById('trend-filter-list');
  const emptyEl = document.getElementById('trend-empty-msg');
  const hasData = nodes.some(n => getTrend(n.id) !== null);
  if (!hasData) {
    listEl.innerHTML = '';
    emptyEl.style.display = 'block';
    return;
  }
  emptyEl.style.display = 'none';

  const counts = { up: 0, flat: 0, down: 0 };
  nodes.forEach(n => {
    const c = getTrendCat(n.id);
    if (c) counts[c]++;
  });

  listEl.innerHTML = TREND_ORDER.map(k => {
    const meta = TREND_META[k];
    const active = trendActive.has(k);
    const swatchStyle = active ? `background: ${meta.color};` : '';
    return `
      <div class="intent-filter-item ${active ? 'active' : ''}" data-trend="${k}">
        <span class="swatch" style="${swatchStyle}"></span>
        <span class="label">${meta.label}</span>
        <span class="count">${(counts[k] || 0).toLocaleString()}</span>
      </div>
    `;
  }).join('');

  listEl.querySelectorAll('.intent-filter-item').forEach(el => {
    el.addEventListener('click', () => {
      const k = el.dataset.trend;
      if (trendActive.has(k)) trendActive.delete(k);
      else trendActive.add(k);
      const active = trendActive.has(k);
      el.classList.toggle('active', active);
      const swatch = el.querySelector('.swatch');
      swatch.style.background = active ? TREND_META[k].color : '';
      applyNodeColors();
      try { renderCardView(); } catch(e) { console.error('renderCardView failed:', e); }
      try { renderKwList(document.getElementById('kw-search').value || ''); } catch(e) { console.error('renderKwList failed:', e); }
    });
  });
}

function renderSerpFilter() {
  const listEl = document.getElementById('serp-filter-list');
  const emptyEl = document.getElementById('serp-empty-msg');
  const hasData = nodes.some(n => {
    const types = getSerpTypes(n.id);
    return types && types.length > 0;
  });
  if (!hasData) {
    listEl.innerHTML = '';
    emptyEl.style.display = 'block';
    return;
  }
  emptyEl.style.display = 'none';

  // 각 SERP 타입 볼륨 합계 (해당 타입에 속한 노드의 볼륨 합)
  const totals = {};
  SERP_ORDER.forEach(k => { totals[k] = 0; });
  nodes.forEach(n => {
    const types = getSerpTypes(n.id) || [];
    types.forEach(k => { totals[k] += (n.volume || 0); });
  });
  // 볼륨 순 정렬
  const sortedKeys = [...SERP_ORDER].sort((a, b) => (totals[b] || 0) - (totals[a] || 0));

  listEl.innerHTML = sortedKeys.map(k => {
    const meta = SERP_META[k];
    const active = serpActive.has(k);
    const swatchStyle = active ? `background: ${meta.color};` : '';
    return `
      <div class="intent-filter-item ${active ? 'active' : ''}" data-serp="${k}">
        <span class="swatch" style="${swatchStyle}"></span>
        <span class="label">${meta.label}</span>
        <span class="count">${(totals[k] || 0).toLocaleString()}</span>
      </div>
    `;
  }).join('');

  listEl.querySelectorAll('.intent-filter-item').forEach(el => {
    el.addEventListener('click', () => {
      const k = el.dataset.serp;
      if (serpActive.has(k)) serpActive.delete(k);
      else serpActive.add(k);
      const active = serpActive.has(k);
      el.classList.toggle('active', active);
      const swatch = el.querySelector('.swatch');
      swatch.style.background = active ? SERP_META[k].color : '';
      applyNodeColors();
      try { renderCardView(); } catch(e) { console.error(e); }
      try { renderKwList(document.getElementById('kw-search').value || ''); } catch(e) { console.error(e); }
    });
  });
}

function renderUserFilter() {
  const listEl = document.getElementById('user-filter-list');
  const emptyEl = document.getElementById('user-empty-msg');
  const hasData = nodes.some(n => {
    const segs = getUserSegments(n.id);
    return segs && segs.length > 0;
  });
  if (!hasData) {
    listEl.innerHTML = '';
    emptyEl.style.display = 'block';
    return;
  }
  emptyEl.style.display = 'none';

  // 각 세그먼트 볼륨 합계
  const totals = {};
  USER_ORDER.forEach(k => { totals[k] = 0; });
  nodes.forEach(n => {
    const segs = getUserSegments(n.id) || [];
    segs.forEach(k => { totals[k] += (n.volume || 0); });
  });

  // gender 먼저 · 그다음 age 순서 (원본 순)
  listEl.innerHTML = USER_ORDER.map(k => {
    const meta = USER_META[k];
    const active = userActive.has(k);
    const swatchStyle = active ? `background: ${meta.color};` : '';
    return `
      <div class="intent-filter-item ${active ? 'active' : ''}" data-user="${k}">
        <span class="swatch" style="${swatchStyle}"></span>
        <span class="label">${meta.label}</span>
        <span class="count">${(totals[k] || 0).toLocaleString()}</span>
      </div>
    `;
  }).join('');

  listEl.querySelectorAll('.intent-filter-item').forEach(el => {
    el.addEventListener('click', () => {
      const k = el.dataset.user;
      if (userActive.has(k)) userActive.delete(k);
      else userActive.add(k);
      const active = userActive.has(k);
      el.classList.toggle('active', active);
      const swatch = el.querySelector('.swatch');
      swatch.style.background = active ? USER_META[k].color : '';
      applyNodeColors();
      try { renderCardView(); } catch(e) { console.error(e); }
      try { renderKwList(document.getElementById('kw-search').value || ''); } catch(e) { console.error(e); }
    });
  });
}

function renderCommerceFilter() {
  const listEl = document.getElementById('commerce-filter-list');
  const emptyEl = document.getElementById('commerce-empty-msg');
  const hasData = nodes.some(n => getCommerceCat(n.id) !== null);
  if (!hasData) {
    listEl.innerHTML = '';
    emptyEl.style.display = 'block';
    return;
  }
  emptyEl.style.display = 'none';

  const counts = { premium: 0, cheap: 0, info: 0, low: 0 };
  const totals = { premium: 0, cheap: 0, info: 0, low: 0 };
  nodes.forEach(n => {
    const cat = getCommerceCat(n.id);
    if (cat) {
      counts[cat]++;
      totals[cat] += (n.volume || 0);
    }
  });

  listEl.innerHTML = COMMERCE_ORDER.map(k => {
    const meta = COMMERCE_META[k];
    const active = commerceActive.has(k);
    const swatchStyle = active ? `background: ${meta.color};` : '';
    return `
      <div class="intent-filter-item ${active ? 'active' : ''}" data-commerce="${k}">
        <span class="swatch" style="${swatchStyle}"></span>
        <span class="label">${meta.label}</span>
        <span class="count">${(counts[k] || 0).toLocaleString()}</span>
      </div>
    `;
  }).join('');

  listEl.querySelectorAll('.intent-filter-item').forEach(el => {
    el.addEventListener('click', () => {
      const k = el.dataset.commerce;
      if (commerceActive.has(k)) commerceActive.delete(k);
      else commerceActive.add(k);
      const active = commerceActive.has(k);
      el.classList.toggle('active', active);
      const swatch = el.querySelector('.swatch');
      swatch.style.background = active ? COMMERCE_META[k].color : '';
      applyNodeColors();
      try { renderCardView(); } catch(e) { console.error(e); }
      try { renderKwList(document.getElementById('kw-search').value || ''); } catch(e) { console.error(e); }
    });
  });
}

function applyNodeColors() {
  if (sideMode === 'cluster') {
    // 클러스터 모드 · 원래 클러스터 색상
    node.attr('fill', d => d.isHub ? '#fff' : colorFor(d.community))
        .attr('stroke', d => d.isHub ? colorFor(d.community) : 'none')
        .attr('fill-opacity', 1);
  } else if (sideMode === 'intent') {
    const filterOn = intentActive.size > 0;
    node.attr('fill', d => {
      const dom = getDominantIntent(d.id);
      if (!dom) return '#d5d5d5';
      if (!filterOn) return INTENT_META[dom].color;
      return intentActive.has(dom) ? INTENT_META[dom].color : '#d5d5d5';
    })
    .attr('stroke', 'none')
    .attr('fill-opacity', d => {
      const dom = getDominantIntent(d.id);
      if (!dom) return 0.35;
      if (!filterOn) return 0.85;
      return intentActive.has(dom) ? 0.9 : 0.3;
    });
  } else if (sideMode === 'trend') {
    const filterOn = trendActive.size > 0;
    node.attr('fill', d => {
      const cat = getTrendCat(d.id);
      if (!cat) return '#d5d5d5';
      if (!filterOn) return TREND_META[cat].color;
      return trendActive.has(cat) ? TREND_META[cat].color : '#d5d5d5';
    })
    .attr('stroke', 'none')
    .attr('fill-opacity', d => {
      const cat = getTrendCat(d.id);
      if (!cat) return 0.35;
      if (!filterOn) return 0.85;
      return trendActive.has(cat) ? 0.9 : 0.3;
    });
  } else if (sideMode === 'serp') {
    const filterOn = serpActive.size > 0;
    node.attr('fill', d => {
      const types = getSerpTypes(d.id) || [];
      if (!types.length) return '#d5d5d5';
      if (!filterOn) return SERP_META[types[0]].color;
      const hit = types.find(t => serpActive.has(t));
      return hit ? SERP_META[hit].color : '#d5d5d5';
    })
    .attr('stroke', 'none')
    .attr('fill-opacity', d => {
      const types = getSerpTypes(d.id) || [];
      if (!types.length) return 0.35;
      if (!filterOn) return 0.85;
      return types.some(t => serpActive.has(t)) ? 0.9 : 0.3;
    });
  } else if (sideMode === 'user') {
    const filterOn = userActive.size > 0;
    node.attr('fill', d => {
      const segs = getUserSegments(d.id) || [];
      if (!segs.length) return '#d5d5d5';
      if (!filterOn) return USER_META[segs[0]].color;
      const hit = segs.find(s => userActive.has(s));
      return hit ? USER_META[hit].color : '#d5d5d5';
    })
    .attr('stroke', 'none')
    .attr('fill-opacity', d => {
      const segs = getUserSegments(d.id) || [];
      if (!segs.length) return 0.35;
      if (!filterOn) return 0.85;
      return segs.some(s => userActive.has(s)) ? 0.9 : 0.3;
    });
  } else if (sideMode === 'commerce') {
    const filterOn = commerceActive.size > 0;
    node.attr('fill', d => {
      const cat = getCommerceCat(d.id);
      if (!cat) return '#d5d5d5';
      if (!filterOn) return COMMERCE_META[cat].color;
      return commerceActive.has(cat) ? COMMERCE_META[cat].color : '#d5d5d5';
    })
    .attr('stroke', 'none')
    .attr('fill-opacity', d => {
      const cat = getCommerceCat(d.id);
      if (!cat) return 0.35;
      if (!filterOn) return 0.85;
      return commerceActive.has(cat) ? 0.9 : 0.3;
    });
  }
}

// 사이드바 모드 스위처
document.querySelectorAll('.side-mode-tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.side-mode-tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    sideMode = btn.dataset.mode;
    document.getElementById('side-panel-cluster').classList.toggle('active', sideMode === 'cluster');
    document.getElementById('side-panel-intent').classList.toggle('active', sideMode === 'intent');
    document.getElementById('side-panel-trend').classList.toggle('active', sideMode === 'trend');
    document.getElementById('side-panel-serp').classList.toggle('active', sideMode === 'serp');
    document.getElementById('side-panel-user').classList.toggle('active', sideMode === 'user');
    document.getElementById('side-panel-commerce').classList.toggle('active', sideMode === 'commerce');
    if (sideMode === 'intent') renderIntentFilter();
    if (sideMode === 'trend') renderTrendFilter();
    if (sideMode === 'serp') renderSerpFilter();
    if (sideMode === 'user') renderUserFilter();
    if (sideMode === 'commerce') renderCommerceFilter();
    applyNodeColors();
    applyViewToggleForMode();
    try { renderCardView(); } catch(e) { console.error('renderCardView failed:', e); }
    try { renderKwList(document.getElementById('kw-search').value || ''); } catch(e) { console.error('renderKwList failed:', e); }
  });
});

// 사이드바 모드에 따라 뷰 토글 · 클러스터 모드만 4뷰 · 다른 모드는 그래프·카드만
function applyViewToggleForMode() {
  const showAll = sideMode === 'cluster';
  document.querySelectorAll('.view-btn').forEach(b => {
    const v = b.dataset.view;
    const visible = showAll || v === 'graph' || v === 'card';
    b.style.display = visible ? '' : 'none';
  });
  if (!showAll) {
    const active = document.querySelector('.view-btn.active');
    if (active && (active.dataset.view === 'cep' || active.dataset.view === 'entity')) {
      document.querySelector('.view-btn[data-view="graph"]').click();
    }
  }
}

// 뷰 토글 · 4뷰 (그래프/카드/CEP/엔티티)
// 클릭 시점에 재렌더 · 초기 로드 시 TDZ (다른 모듈의 let/const 아직 선언 전) 방어
document.querySelectorAll('.view-btn').forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const view = btn.dataset.view;
    document.getElementById('graph-view').classList.toggle('active', view === 'graph');
    document.getElementById('card-view').classList.toggle('active', view === 'card');
    document.getElementById('cep-view').classList.toggle('active', view === 'cep');
    document.getElementById('entity-view').classList.toggle('active', view === 'entity');
    // 재렌더 · 클릭 시점엔 모든 변수 초기화 완료
    if (view === 'card') { try { renderCardView(); } catch(e) { console.error('renderCardView failed:', e); } }
    if (view === 'cep') { try { renderCepView(); } catch(e) { console.error('renderCepView failed:', e); } }
    if (view === 'entity') { try { renderEntityView(); } catch(e) { console.error('renderEntityView failed:', e); } }
  };
});

// 햄버거 · 사이드바 토글
const sidebarEl = document.getElementById('sidebar');
const hamburgerBtn = document.getElementById('sidebar-toggle');
if (hamburgerBtn && sidebarEl) {
  hamburgerBtn.addEventListener('click', () => {
    sidebarEl.classList.toggle('collapsed');
    window.dispatchEvent(new Event('resize'));
  });
}
