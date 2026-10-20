// ===== 공용 필터 · 볼륨·트렌드 =====
// 필터 상태 · 노드가 필터에 걸리면 회색·투명 처리 · 카드뷰·키워드 리스트에서도 제외
const rangeFilter = {
  volMin: 0,
  volMax: (() => {
    let m = 0;
    nodes.forEach(n => { if ((n.volume || 0) > m) m = n.volume || 0; });
    return m;
  })(),
  trendDownOn: false, trendDownMin: -1.0, trendDownMax: -0.01,
  trendUpOn:   false, trendUpMin:    0.01, trendUpMax:   5.0,
};

function nodePassesFilter(nId, nVol) {
  const v = nVol ?? 0;
  if (v < rangeFilter.volMin || v > rangeFilter.volMax) return false;
  const anyTrendOn = rangeFilter.trendDownOn || rangeFilter.trendUpOn;
  if (!anyTrendOn) return true;
  const t = getTrend(nId);
  if (t === null) return false;  // 트렌드 필터 켜져있으면 트렌드 데이터 없는 노드 제외
  const inDown = rangeFilter.trendDownOn && t >= rangeFilter.trendDownMin && t <= rangeFilter.trendDownMax;
  const inUp   = rangeFilter.trendUpOn   && t >= rangeFilter.trendUpMin   && t <= rangeFilter.trendUpMax;
  return inDown || inUp;
}

function setupDualSlider(sliderEl, onChange, opts = {}) {
  const inputs = sliderEl.querySelectorAll('input[type="range"]');
  const fill = sliderEl.querySelector('.track-fill');
  const minI = inputs[0], maxI = inputs[1];
  function refresh() {
    let a = Number(minI.value), b = Number(maxI.value);
    if (a > b) { [a, b] = [b, a]; }
    const lo = Number(minI.min), hi = Number(minI.max);
    const range = hi - lo || 1;
    const lPct = ((a - lo) / range) * 100;
    const rPct = ((b - lo) / range) * 100;
    fill.style.left = lPct + '%';
    fill.style.width = (rPct - lPct) + '%';
    onChange(a, b);
  }
  minI.addEventListener('input', refresh);
  maxI.addEventListener('input', refresh);
  return { refresh, setValues: (a, b) => { minI.value = a; maxI.value = b; refresh(); } };
}

// 볼륨 슬라이더 초기화
(function initVolSlider() {
  const wrap = document.querySelector('.dual-slider[data-key="vol"]');
  const inputs = wrap.querySelectorAll('input[type="range"]');
  const maxVol = rangeFilter.volMax;
  inputs[0].max = maxVol; inputs[1].max = maxVol;
  inputs[0].value = 0; inputs[1].value = maxVol;
  const minInput = document.getElementById('vol-min');
  const maxInput = document.getElementById('vol-max');
  maxInput.value = maxVol;
  const ctrl = setupDualSlider(wrap, (a, b) => {
    rangeFilter.volMin = a; rangeFilter.volMax = b;
    minInput.value = a; maxInput.value = b;
    applyAllFilters();
  });
  minInput.addEventListener('change', () => {
    rangeFilter.volMin = Math.max(0, Math.min(Number(minInput.value) || 0, rangeFilter.volMax));
    ctrl.setValues(rangeFilter.volMin, rangeFilter.volMax);
  });
  maxInput.addEventListener('change', () => {
    rangeFilter.volMax = Math.max(rangeFilter.volMin, Number(maxInput.value) || 0);
    ctrl.setValues(rangeFilter.volMin, rangeFilter.volMax);
  });
})();

// 트렌드 슬라이더 · 하락/상승 각각
function initTrendSlider(kind) {
  const chkId = kind === 'down' ? 'trend-down-chk' : 'trend-up-chk';
  const blockId = kind === 'down' ? 'trend-down-block' : 'trend-up-block';
  const minInputId = kind === 'down' ? 'trend-down-min' : 'trend-up-min';
  const maxInputId = kind === 'down' ? 'trend-down-max' : 'trend-up-max';
  const chk = document.getElementById(chkId);
  const block = document.getElementById(blockId);
  const minInput = document.getElementById(minInputId);
  const maxInput = document.getElementById(maxInputId);
  const wrap = document.querySelector(`.dual-slider[data-key="trend-${kind}"]`);
  const inputs = wrap.querySelectorAll('input[type="range"]');

  const ctrl = setupDualSlider(wrap, (a, b) => {
    if (kind === 'down') {
      rangeFilter.trendDownMin = a / 100;
      rangeFilter.trendDownMax = b / 100;
    } else {
      rangeFilter.trendUpMin = a / 100;
      rangeFilter.trendUpMax = b / 100;
    }
    minInput.value = a; maxInput.value = b;
    if (chk.checked) applyAllFilters();
  });
  chk.addEventListener('change', () => {
    block.classList.toggle('disabled', !chk.checked);
    if (kind === 'down') rangeFilter.trendDownOn = chk.checked;
    else rangeFilter.trendUpOn = chk.checked;
    applyAllFilters();
  });
  minInput.addEventListener('change', () => {
    const v = Number(minInput.value) || 0;
    ctrl.setValues(v, Number(maxInput.value) || 0);
  });
  maxInput.addEventListener('change', () => {
    const v = Number(maxInput.value) || 0;
    ctrl.setValues(Number(minInput.value) || 0, v);
  });
  // 초기 트랙 fill 표시
  ctrl.setValues(Number(inputs[0].value), Number(inputs[1].value));
}
initTrendSlider('down');
initTrendSlider('up');

function applyAllFilters() {
  // 그래프 노드 opacity · 필터 통과 안 하면 회색 · 낮은 opacity
  node.attr('display', d => nodePassesFilter(d.id, d.volume) ? null : 'none');
  // labels 도 함께 숨김
  labels.attr('display', d => nodePassesFilter(d.id, d.volume) ? null : 'none');
  // 링크 · 양 끝 노드 모두 통과해야 표시
  link.attr('display', d => {
    const s = typeof d.source === 'object' ? d.source : nodeIndex.get(d.source);
    const t = typeof d.target === 'object' ? d.target : nodeIndex.get(d.target);
    if (!s || !t) return 'none';
    return (nodePassesFilter(s.id, s.volume) && nodePassesFilter(t.id, t.volume)) ? null : 'none';
  });
  try { renderKwList(document.getElementById('kw-search').value || ''); } catch(e) {}
  try { renderCardView(); } catch(e) {}
}

// ===== 카드 ? 아이콘 · 전역 위치 자동 툴팁 =====
(function() {
  const tipEl = document.getElementById('card-help-tip');
  if (!tipEl) return;
  const escHt = s => String(s ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  document.body.addEventListener('mouseover', (ev) => {
    const el = ev.target.closest('.card-help');
    if (!el) return;
    const cond = el.getAttribute('data-help-cond') || '';
    const use = el.getAttribute('data-help-use') || '';
    let html = '';
    if (cond) html += `<span class="tip-heading">조건</span>${escHt(cond)}`;
    if (use) html += `<span class="tip-heading">마케팅 활용</span>${escHt(use)}`;
    if (!html) return;
    tipEl.innerHTML = html;
    tipEl.style.display = 'block';
    // 위치 계산 · 아이콘 기준 아래 · 화면 밖 벗어나면 반대편
    const r = el.getBoundingClientRect();
    const tw = tipEl.offsetWidth;
    const th = tipEl.offsetHeight;
    const vw = window.innerWidth, vh = window.innerHeight;
    // 기본 · 아이콘 아래 · 중앙 정렬
    let top = r.bottom + 6;
    let left = r.left + r.width / 2 - tw / 2;
    // 아래 부족 → 위로
    if (top + th > vh - 8) top = r.top - th - 6;
    // 왼쪽 초과 → 오른쪽 정렬
    if (left < 8) left = 8;
    // 오른쪽 초과 → 왼쪽 정렬
    if (left + tw > vw - 8) left = vw - tw - 8;
    tipEl.style.top = top + 'px';
    tipEl.style.left = left + 'px';
  });
  document.body.addEventListener('mouseout', (ev) => {
    const el = ev.target.closest('.card-help');
    if (!el) return;
    tipEl.style.display = 'none';
  });
})();

// ===== 상세 Drawer =====
const drawerEl = document.getElementById('detail-drawer');
document.getElementById('detail-close').addEventListener('click', () => drawerEl.classList.remove('open'));

function escHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
function fmtNum(v) {
  return (v === null || v === undefined) ? '<span style="color:#bbb;">–</span>' : Number(v).toLocaleString();
}
function fmtPct(v) {
  if (v === null || v === undefined) return '<span style="color:#bbb;">–</span>';
  const pct = Math.round(v * 100);
  return (pct >= 0 ? '+' : '') + pct + '%';
}

function openKeywordDetail(kwId) {
  const n = nodeIndex.get(kwId);
  if (!n) return;
  const kwInfo = (CLUSTER_DATA.keyword_info || {})[kwId] || {};
  const ads = kwInfo.ads_metrics || {};
  const intents = kwInfo.intents;
  const demo = kwInfo.demography;
  const feats = kwInfo.features;
  const monthly = kwInfo.monthly_volume;
  const cLabel = clusterLabels[n.community];

  // 헤더
  document.getElementById('detail-title').textContent = kwId;

  // 메타 칩 · 클러스터·인텐트·트렌드
  const chips = [];
  if (cLabel) chips.push(`<span class="chip" style="background:${colorFor(n.community)}22; color:${colorFor(n.community)};">${escHtml(cLabel.letter)} · ${escHtml(cLabel.name)}</span>`);
  const dom = getDominantIntent(kwId);
  if (dom) chips.push(`<span class="chip" style="background:${INTENT_META[dom].color}22; color:${INTENT_META[dom].color};">${INTENT_META[dom].label}</span>`);
  const tCat = getTrendCat(kwId);
  if (tCat) chips.push(`<span class="chip" style="background:${TREND_META[tCat].color}22; color:${TREND_META[tCat].color};">${TREND_META[tCat].label}</span>`);
  if (n.isHub) chips.push('<span class="chip" style="background:#333; color:#fff;">허브</span>');
  document.getElementById('detail-meta').innerHTML = chips.join('');

  // 본문 · 섹션들
  const sections = [];

  // 1. 검색량
  const volTrend = ads.volume_trend;
  const trendClass = volTrend > 0 ? 'up' : (volTrend < 0 ? 'down' : '');
  sections.push(`
    <div class="detail-section">
      <h4>검색량</h4>
      <div class="detail-metric-row"><span class="label">월평균 검색량</span><span class="value">${fmtNum(ads.volume_avg ?? n.volume)}</span></div>
      <div class="detail-metric-row"><span class="label">연간 총 검색량</span><span class="value">${fmtNum(ads.volume_total)}</span></div>
      <div class="detail-metric-row"><span class="label">3개월 트렌드</span><span class="value ${trendClass}">${fmtPct(volTrend)}</span></div>
      ${Array.isArray(monthly) && monthly.length > 1 ? `<div class="detail-spark">${buildTrendChart(monthly, 340, 130)}</div>` : ''}
    </div>
  `);

  // 2. 채널 (네이버 vs 구글)
  if (ads.gg_volume_avg !== undefined || ads.nv_volume_avg !== undefined) {
    const gg = Number(ads.gg_volume_avg || 0);
    const nv = Number(ads.nv_volume_avg || 0);
    const total = gg + nv || 1;
    sections.push(`
      <div class="detail-section">
        <h4>채널 분포 (월평균)</h4>
        <div class="detail-bar-row">
          <span class="bar-label">네이버</span>
          <div class="bar-track"><div class="bar-fill" style="width:${(nv/total*100).toFixed(1)}%; background:#a3d982;"></div></div>
          <span class="bar-val">${nv.toLocaleString()}</span>
        </div>
        <div class="detail-bar-row">
          <span class="bar-label">구글</span>
          <div class="bar-track"><div class="bar-fill" style="width:${(gg/total*100).toFixed(1)}%; background:#7ab8f5;"></div></div>
          <span class="bar-val">${gg.toLocaleString()}</span>
        </div>
      </div>
    `);
  }

  // 3. 인텐트
  if (intents) {
    const rows = INTENT_ORDER.map(k => {
      const v = Number(intents[k] ?? 0);
      return `
        <div class="detail-bar-row">
          <span class="bar-label">${INTENT_META[k].label}</span>
          <div class="bar-track"><div class="bar-fill" style="width:${(v*100).toFixed(1)}%; background:${INTENT_META[k].color};"></div></div>
          <span class="bar-val">${Math.round(v*100)}%</span>
        </div>`;
    }).join('');
    sections.push(`<div class="detail-section"><h4>검색 인텐트</h4>${rows}</div>`);
  }

  // 4. 페르소나
  if (demo) {
    const mR = Number(demo.m_gender_ratio ?? 0), fR = Number(demo.f_gender_ratio ?? 0);
    let genderRow = '';
    if (mR || fR) {
      genderRow = `
        <div class="detail-bar-row">
          <span class="bar-label">여성</span>
          <div class="bar-track"><div class="bar-fill" style="width:${fR.toFixed(1)}%; background:#f4a6b8;"></div></div>
          <span class="bar-val">${fR.toFixed(0)}%</span>
        </div>
        <div class="detail-bar-row">
          <span class="bar-label">남성</span>
          <div class="bar-track"><div class="bar-fill" style="width:${mR.toFixed(1)}%; background:#7ab8f5;"></div></div>
          <span class="bar-val">${mR.toFixed(0)}%</span>
        </div>`;
    }
    const ageKeys = [['a0','아동'],['a13','10대'],['a20','20대'],['a25','25~'],['a30','30대'],['a40','40대'],['a50','50대+']];
    const ageRows = ageKeys.map(([k,label]) => {
      const r = Number(demo[k+'_ratio'] ?? 0);
      if (!r) return '';
      return `
        <div class="detail-bar-row">
          <span class="bar-label">${label}</span>
          <div class="bar-track"><div class="bar-fill" style="width:${r.toFixed(1)}%; background:#b5a3e0;"></div></div>
          <span class="bar-val">${r.toFixed(0)}%</span>
        </div>`;
    }).filter(Boolean).join('');
    if (genderRow || ageRows) {
      sections.push(`<div class="detail-section"><h4>유저 특성</h4>${genderRow}${ageRows || '<div class="detail-empty-line">연령대 데이터 없음</div>'}</div>`);
    }
  }

  // 5. SERP features · 존재 flag(0/1)와 개수 필드를 동일한 방식으로 표시
  if (feats) {
    const rowList = [
      ['AI Overview', feats.f_ai_overview, true],
      ['추천스니펫', feats.f_featured_snippet, true],
      ['지식패널', feats.f_knowledge_panel, true],
      ['일반 결과', feats.f_organic_results, false],
      ['광고 상단', feats.f_ads_top, false],
      ['광고 하단', feats.f_ads_bottom, false],
      ['이미지', feats.f_images, false],
      ['동영상', feats.f_video_results, false],
      ['PAA', feats.f_people_also_ask_for, false],
      ['관련 검색', feats.f_related_searches, false],
      ['SNS', feats.f_sns, false],
    ].filter(([, v]) => v !== undefined && v !== null);
    let rowHtml = rowList.map(([k, v, isFlag]) => {
      const display = isFlag ? (Number(v) > 0 ? '있음' : '없음') : String(v);
      return `<div class="fkey">${k}</div><div class="fval">${display}</div>`;
    }).join('');
    sections.push(`
      <div class="detail-section">
        <h4>SERP 화면</h4>
        <div class="detail-feature-grid">${rowHtml || '<div class="detail-empty-line">SERP 데이터 없음</div>'}</div>
      </div>
    `);
  }

  // 6. 광고 지표
  if (ads.cpc !== undefined || ads.competition !== undefined) {
    sections.push(`
      <div class="detail-section">
        <h4>광고 지표</h4>
        <div class="detail-metric-row"><span class="label">경쟁도</span><span class="value">${escHtml(ads.competition ?? '–')} ${ads.competition_index !== undefined ? '('+ads.competition_index+')' : ''}</span></div>
        <div class="detail-metric-row"><span class="label">CPC (USD)</span><span class="value">${ads.cpc !== undefined ? '$' + Number(ads.cpc).toFixed(2) : '–'}</span></div>
      </div>
    `);
  }

  // 7. 이웃 키워드 (rels 기반)
  const neighbors = new Set();
  (CLUSTER_DATA.rels || []).forEach(([a, b]) => {
    if (a === kwId) neighbors.add(b);
    else if (b === kwId) neighbors.add(a);
  });
  const neighborsArr = [...neighbors]
    .map(id => nodeIndex.get(id))
    .filter(Boolean)
    .sort((a, b) => (b.volume || 0) - (a.volume || 0))
    .slice(0, 20);
  if (neighborsArr.length) {
    sections.push(`
      <div class="detail-section">
        <h4>이웃 키워드 · ${neighborsArr.length}개</h4>
        <div>${neighborsArr.map(nb => `
          <div class="detail-neighbor" data-kw="${escHtml(nb.id)}">
            <span class="n-kw">${escHtml(nb.id)}</span>
            <span class="n-vol">${(nb.volume ?? 0).toLocaleString()}</span>
          </div>`).join('')}
        </div>
      </div>
    `);
  }

  const body = document.getElementById('detail-body');
  body.innerHTML = sections.join('');
  // 이웃 클릭 · 재귀 열기
  body.querySelectorAll('.detail-neighbor').forEach(el => {
    el.addEventListener('click', () => openKeywordDetail(el.dataset.kw));
  });
  // 트렌드 차트 hover 바인딩
  try { bindTrendChartHover(body); } catch(e) { console.error('bindTrendChartHover:', e); }
  drawerEl.classList.add('open');
}

