function renderCardView() {
  _renderCardViewInner();
  try { renderSparklineWall(); } catch(e) { console.error('renderSparklineWall:', e); }
}

function _renderCardViewInner() {
  const grid = document.getElementById('card-grid');
  grid.innerHTML = '';

  if (sideMode === 'intent') {
    const filterOn = intentActive.size > 0;
    const byIntent = { i: [], n: [], c: [], t: [] };
    nodes.forEach(n => {
      if (!nodePassesFilter(n.id, n.volume)) return;
      const dom = getDominantIntent(n.id);
      if (dom) byIntent[dom].push(n);
    });
    const totals = {};
    Object.keys(byIntent).forEach(k => {
      totals[k] = byIntent[k].reduce((s, n) => s + (n.volume || 0), 0);
    });
    const sortedKeys = [...INTENT_ORDER].sort((a, b) => (totals[b] || 0) - (totals[a] || 0));

    sortedKeys.forEach(k => {
      const meta = INTENT_META[k];
      const items = [...byIntent[k]].sort((a, b) => (b.volume || 0) - (a.volume || 0));
      let kwListHtml = '';
      items.forEach(n => {
        kwListHtml += `
          <div class="card-kw-item">
            <span class="kw" title="${n.id}">${n.id}</span>
            <span class="vol">${(n.volume ?? 0).toLocaleString()}</span>
          </div>`;
      });
      const isSelected = filterOn && intentActive.has(k);
      const isDimmed = filterOn && !isSelected;
      const card = document.createElement('div');
      card.className = 'cluster-card' + (isSelected ? ' selected' : '') + (isDimmed ? ' dimmed' : '');
      card.style.borderTop = `3px solid ${meta.color}`;
      const letterStyle = isSelected
        ? `background: ${meta.color}; color: #fff; border: 1px solid ${meta.color};`
        : `background: ${meta.color}22; color: ${meta.color}; border: 1px solid ${meta.color}66;`;
      card.innerHTML = `
        <div class="card-header-fill" style="background: ${meta.color}22;"></div>
        <div class="card-header">
          <span class="card-letter" style="${letterStyle}">${meta.label}</span>${buildCardHelp(meta)}
          <span class="card-label" style="margin-left: auto;">${items.length.toLocaleString()} kws</span>
        </div>
        <div class="card-name" style="min-height: auto; margin-bottom: 6px;">${meta.desc}</div>
        <div class="card-vol-total">
          <span>검색량 합계</span>
          <span class="val">${(totals[k] || 0).toLocaleString()}</span>
        </div>
        <div class="card-kw-list">${kwListHtml || '<div style="color:#bbb; font-size:11px; padding:8px; text-align:center;">해당 인텐트 키워드 없음</div>'}</div>
      `;
      grid.appendChild(card);
    });
    return;
  }

  if (sideMode === 'trend') {
    const filterOn = trendActive.size > 0;
    const byTrend = { up: [], flat: [], down: [] };
    nodes.forEach(n => {
      if (!nodePassesFilter(n.id, n.volume)) return;
      const c = getTrendCat(n.id);
      if (c) byTrend[c].push(n);
    });
    const totals = {};
    Object.keys(byTrend).forEach(k => {
      totals[k] = byTrend[k].reduce((s, n) => s + (n.volume || 0), 0);
    });
    // 상승 → 하락 → 안정 (라이징 먼저 보이도록)
    const orderMap = { up: 0, down: 1, flat: 2 };
    const sortedKeys = [...TREND_ORDER].sort((a, b) => (orderMap[a] ?? 9) - (orderMap[b] ?? 9));

    sortedKeys.forEach(k => {
      const meta = TREND_META[k];
      const items = [...byTrend[k]].sort((a, b) => {
        if (k === 'flat') return (b.volume || 0) - (a.volume || 0);
        // 상승 · spike 스코어 우선 (급등이 위로) · 그 다음 볼륨 × 트렌드
        if (k === 'up') {
          const sa = getSpikeMetrics(a.id);
          const sb = getSpikeMetrics(b.id);
          const spA = sa ? sa.spike : 0;
          const spB = sb ? sb.spike : 0;
          if (spA !== spB) return spB - spA;
        }
        const impactA = (a.volume || 0) * Math.abs(getTrend(a.id) ?? 0);
        const impactB = (b.volume || 0) * Math.abs(getTrend(b.id) ?? 0);
        if (impactA === 0 && impactB === 0) {
          return Math.abs(getTrend(b.id) ?? 0) - Math.abs(getTrend(a.id) ?? 0);
        }
        return impactB - impactA;
      });
      let kwListHtml = '';
      items.forEach(n => {
        const t = getTrend(n.id);
        const trendStr = t !== null ? ((t >= 0 ? '+' : '') + Math.round(t * 100) + '%') : '';
        const trendColor = t >= 0 ? '#3a8f3a' : '#c94a5f';
        const volStr = (n.volume && n.volume > 0) ? n.volume.toLocaleString() : '<span style="color:#bbb;">–</span>';
        // 상승 카드는 · 급등/신규 색 도트 (키워드 앞에 붙임 · 잘림 방지)
        let dotStr = '';
        if (k === 'up') {
          const sm = getSpikeMetrics(n.id);
          if (sm && sm.kind !== 'growth') {
            const tm = SPIKE_TAG_META[sm.kind];
            dotStr = `<span class="spike-dot" style="background:${tm.color};" title="${tm.label} · ${tm.desc}"></span>`;
          }
        }
        kwListHtml += `
          <div class="card-kw-item">
            ${dotStr}<span class="kw" title="${n.id}">${n.id}</span>
            <span class="vol"><span style="color:${trendColor}; font-weight:600; margin-right:6px;">${trendStr}</span>${volStr}</span>
          </div>`;
      });
      const isSelected = filterOn && trendActive.has(k);
      const isDimmed = filterOn && !isSelected;
      const card = document.createElement('div');
      card.className = 'cluster-card' + (isSelected ? ' selected' : '') + (isDimmed ? ' dimmed' : '');
      card.style.borderTop = `3px solid ${meta.color}`;
      const letterStyle = isSelected
        ? `background: ${meta.color}; color: #fff; border: 1px solid ${meta.color};`
        : `background: ${meta.color}22; color: ${meta.color}; border: 1px solid ${meta.color}66;`;
      card.innerHTML = `
        <div class="card-header-fill" style="background: ${meta.color}22;"></div>
        <div class="card-header">
          <span class="card-letter" style="${letterStyle}">${meta.label}</span>${buildCardHelp(meta)}
          <span class="card-label" style="margin-left: auto;">${items.length.toLocaleString()} kws</span>
        </div>
        <div class="card-name" style="min-height: auto; margin-bottom: 6px;">${meta.desc}</div>
        <div class="card-vol-total">
          <span>검색량 합계</span>
          <span class="val">${(totals[k] || 0).toLocaleString()}</span>
        </div>
        <div class="card-kw-list">${kwListHtml || '<div style="color:#bbb; font-size:11px; padding:8px; text-align:center;">해당 트렌드 키워드 없음</div>'}</div>
      `;
      grid.appendChild(card);
    });
    return;
  }

  if (sideMode === 'commerce') {
    const filterOn = commerceActive.size > 0;
    const byCat = { premium: [], cheap: [], info: [], low: [] };
    nodes.forEach(n => {
      if (!nodePassesFilter(n.id, n.volume)) return;
      const cat = getCommerceCat(n.id);
      if (cat) byCat[cat].push(n);
    });
    const totals = {};
    Object.keys(byCat).forEach(k => {
      totals[k] = byCat[k].reduce((s, n) => s + (n.volume || 0), 0);
    });
    const sortedKeys = [...COMMERCE_ORDER].sort((a, b) => (totals[b] || 0) - (totals[a] || 0));

    sortedKeys.forEach(k => {
      const meta = COMMERCE_META[k];
      // 정렬 · CPC × volume 스코어 순 (premium/cheap) · info/low는 volume 순
      const items = [...byCat[k]].sort((a, b) => {
        const aInfo = (CLUSTER_DATA.keyword_info || {})[a.id] || {};
        const bInfo = (CLUSTER_DATA.keyword_info || {})[b.id] || {};
        const aCpc = Number(aInfo.ads_metrics?.cpc ?? 0);
        const bCpc = Number(bInfo.ads_metrics?.cpc ?? 0);
        if (k === 'premium' || k === 'cheap') {
          return (bCpc * (b.volume || 0)) - (aCpc * (a.volume || 0));
        }
        return (b.volume || 0) - (a.volume || 0);
      });
      let kwListHtml = '';
      items.forEach(n => {
        const kwInfo = (CLUSTER_DATA.keyword_info || {})[n.id] || {};
        const ads = kwInfo.ads_metrics || {};
        const cpc = Number(ads.cpc ?? 0);
        const cpcStr = cpc > 0 ? '$' + cpc.toFixed(2) : '–';
        const compIdx = Number(ads.competition_index ?? 0);
        const compColor = compIdx >= 70 ? '#c94a5f' : (compIdx >= 40 ? '#e89f6a' : '#3a8f3a');
        kwListHtml += `
          <div class="card-kw-item">
            <span class="kw" title="${n.id}">${n.id}</span>
            <span class="vol">
              <span style="color:${compColor}; font-weight:600; margin-right:6px;">${cpcStr}</span>${(n.volume ?? 0).toLocaleString()}
            </span>
          </div>`;
      });
      const isSelected = filterOn && commerceActive.has(k);
      const isDimmed = filterOn && !isSelected;
      const card = document.createElement('div');
      card.className = 'cluster-card' + (isSelected ? ' selected' : '') + (isDimmed ? ' dimmed' : '');
      card.style.borderTop = `3px solid ${meta.color}`;
      const letterStyle = isSelected
        ? `background: ${meta.color}; color: #fff; border: 1px solid ${meta.color};`
        : `background: ${meta.color}22; color: ${meta.color}; border: 1px solid ${meta.color}66;`;
      card.innerHTML = `
        <div class="card-header-fill" style="background: ${meta.color}22;"></div>
        <div class="card-header">
          <span class="card-letter" style="${letterStyle}">${meta.label}</span>${buildCardHelp(meta)}
          <span class="card-label" style="margin-left: auto;">${items.length.toLocaleString()} kws</span>
        </div>
        <div class="card-name" style="min-height: auto; margin-bottom: 6px;">${meta.desc}</div>
        <div class="card-vol-total">
          <span>검색량 합계</span>
          <span class="val">${(totals[k] || 0).toLocaleString()}</span>
        </div>
        <div class="card-kw-list">${kwListHtml || '<div style="color:#bbb; font-size:11px; padding:8px; text-align:center;">해당 상업성 카테고리 키워드 없음</div>'}</div>
      `;
      grid.appendChild(card);
    });
    return;
  }

  if (sideMode === 'user') {
    const filterOn = userActive.size > 0;
    const bySeg = {};
    USER_ORDER.forEach(k => { bySeg[k] = []; });
    nodes.forEach(n => {
      if (!nodePassesFilter(n.id, n.volume)) return;
      const segs = getUserSegments(n.id) || [];
      segs.forEach(s => bySeg[s].push(n));
    });
    const totals = {};
    USER_ORDER.forEach(k => {
      totals[k] = bySeg[k].reduce((s, n) => s + (n.volume || 0), 0);
    });
    const sortedKeys = [...USER_ORDER].sort((a, b) => (totals[b] || 0) - (totals[a] || 0));

    sortedKeys.forEach(k => {
      const meta = USER_META[k];
      const items = [...bySeg[k]].sort((a, b) => (b.volume || 0) - (a.volume || 0));
      let kwListHtml = '';
      items.forEach(n => {
        kwListHtml += `
          <div class="card-kw-item">
            <span class="kw" title="${n.id}">${n.id}</span>
            <span class="vol">${(n.volume ?? 0).toLocaleString()}</span>
          </div>`;
      });
      const isSelected = filterOn && userActive.has(k);
      const isDimmed = filterOn && !isSelected;
      const card = document.createElement('div');
      card.className = 'cluster-card' + (isSelected ? ' selected' : '') + (isDimmed ? ' dimmed' : '');
      card.style.borderTop = `3px solid ${meta.color}`;
      const letterStyle = isSelected
        ? `background: ${meta.color}; color: #fff; border: 1px solid ${meta.color};`
        : `background: ${meta.color}22; color: ${meta.color}; border: 1px solid ${meta.color}66;`;
      card.innerHTML = `
        <div class="card-header-fill" style="background: ${meta.color}22;"></div>
        <div class="card-header">
          <span class="card-letter" style="${letterStyle}">${meta.label}</span>${buildCardHelp(meta)}
          <span class="card-label" style="margin-left: auto;">${items.length.toLocaleString()} kws</span>
        </div>
        <div class="card-vol-total" style="margin-top: 6px;">
          <span>검색량 합계</span>
          <span class="val">${(totals[k] || 0).toLocaleString()}</span>
        </div>
        <div class="card-kw-list">${kwListHtml || '<div style="color:#bbb; font-size:11px; padding:8px; text-align:center;">해당 세그먼트 키워드 없음</div>'}</div>
      `;
      grid.appendChild(card);
    });
    return;
  }

  if (sideMode === 'serp') {
    const filterOn = serpActive.size > 0;
    // 각 SERP 카테고리에 속한 노드
    const byType = {};
    SERP_ORDER.forEach(k => { byType[k] = []; });
    nodes.forEach(n => {
      if (!nodePassesFilter(n.id, n.volume)) return;
      const types = getSerpTypes(n.id) || [];
      types.forEach(t => byType[t].push(n));
    });
    const totals = {};
    SERP_ORDER.forEach(k => {
      totals[k] = byType[k].reduce((s, n) => s + (n.volume || 0), 0);
    });
    const sortedKeys = [...SERP_ORDER].sort((a, b) => (totals[b] || 0) - (totals[a] || 0));

    sortedKeys.forEach(k => {
      const meta = SERP_META[k];
      const items = [...byType[k]].sort((a, b) => (b.volume || 0) - (a.volume || 0));
      let kwListHtml = '';
      items.forEach(n => {
        kwListHtml += `
          <div class="card-kw-item">
            <span class="kw" title="${n.id}">${n.id}</span>
            <span class="vol">${(n.volume ?? 0).toLocaleString()}</span>
          </div>`;
      });
      const isSelected = filterOn && serpActive.has(k);
      const isDimmed = filterOn && !isSelected;
      const card = document.createElement('div');
      card.className = 'cluster-card' + (isSelected ? ' selected' : '') + (isDimmed ? ' dimmed' : '');
      card.style.borderTop = `3px solid ${meta.color}`;
      const letterStyle = isSelected
        ? `background: ${meta.color}; color: #fff; border: 1px solid ${meta.color};`
        : `background: ${meta.color}22; color: ${meta.color}; border: 1px solid ${meta.color}66;`;
      card.innerHTML = `
        <div class="card-header-fill" style="background: ${meta.color}22;"></div>
        <div class="card-header">
          <span class="card-letter" style="${letterStyle}">${meta.label}</span>${buildCardHelp(meta)}
          <span class="card-label" style="margin-left: auto;">${items.length.toLocaleString()} kws</span>
        </div>
        <div class="card-vol-total" style="margin-top: 6px;">
          <span>검색량 합계</span>
          <span class="val">${(totals[k] || 0).toLocaleString()}</span>
        </div>
        <div class="card-kw-list">${kwListHtml || '<div style="color:#bbb; font-size:11px; padding:8px; text-align:center;">해당 노출타입 키워드 없음</div>'}</div>
      `;
      grid.appendChild(card);
    });
    return;
  }

  // 클러스터 모드 · 원래 클러스터별 카드
  sortedClusters.forEach(([cid, info]) => {
    const color = colorFor(cid);
    const kws = (CLUSTER_DATA.communities[cid] || []).filter(kw => {
      const nb = nodeIndex.get(kw);
      return nb && nodePassesFilter(nb.id, nb.volume);
    });
    const sortedKws = [...kws].sort((a, b) => {
      const vA = (nodeIndex.get(a) || {}).volume || 0;
      const vB = (nodeIndex.get(b) || {}).volume || 0;
      return vB - vA;
    });

    const card = document.createElement('div');
    card.className = 'cluster-card';
    card.style.borderTop = `3px solid ${color}`;

    let kwListHtml = '';
    sortedKws.forEach(kw => {
      const n = nodeIndex.get(kw);
      const vol = n ? n.volume : 0;
      kwListHtml += `
        <div class="card-kw-item">
          <span class="kw" title="${kw}">${kw}</span>
          <span class="vol">${(vol ?? 0).toLocaleString()}</span>
        </div>`;
    });

    const isSelected = isolatedCid === cid;
    const isDimmed = isolatedCid !== null && !isSelected;
    if (isSelected) card.classList.add('selected');
    if (isDimmed) card.classList.add('dimmed');
    const letterStyle = isSelected
      ? `background: ${color}; color: #fff; border: 1px solid ${color};`
      : `background: ${color}18; color: ${color}; border: 1px solid ${color}66;`;
    card.innerHTML = `
      <div class="card-header-fill" style="background: ${color}22;"></div>
      <div class="card-header">
        <span class="card-letter" style="${letterStyle}">${info.letter} 클러스터</span>
        <span class="card-label" style="margin-left: auto;">${info.size ?? 0} kws</span>
      </div>
      <div class="card-name">${info.name ?? ''}</div>
      <div class="card-vol-total">
        <span>검색량 합계</span>
        <span class="val">${(info.total_volume ?? 0).toLocaleString()}</span>
      </div>
      <div class="card-kw-list">${kwListHtml}</div>
    `;
    grid.appendChild(card);
  });
}

// Sparkline Wall · 트렌드 모드 카드뷰에서만 표시
let sparklineSort = 'impact';   // impact | spike | volume
let sparklineKind = 'all';      // all | spike | coldStart | growth
let sparklinePage = 1;
const SPARKLINE_PAGE_SIZE = 30;

function renderSparklineWall() {
  const wall = document.getElementById('sparkline-wall');
  if (!wall) return;
  if (sideMode !== 'trend') { wall.style.display = 'none'; return; }
  // 후보 · monthly_volume이 있는 노드만 · 필터 통과
  let cand = nodes
    .filter(n => nodePassesFilter(n.id, n.volume))
    .filter(n => {
      const info = (CLUSTER_DATA.keyword_info || {})[n.id];
      return info && Array.isArray(info.monthly_volume) && info.monthly_volume.length >= 6;
    });
  if (cand.length === 0) { wall.style.display = 'none'; return; }
  wall.style.display = 'block';

  // 종류 필터 · sparklineKind
  if (sparklineKind !== 'all') {
    cand = cand.filter(n => {
      const sm = getSpikeMetrics(n.id);
      return sm && sm.kind === sparklineKind;
    });
  }

  // 임팩트 스코어 · sqrt(volume) × max(0, spike)
  function impactScore(kwId, vol) {
    const sm = getSpikeMetrics(kwId);
    if (!sm) return 0;
    const s = Math.max(0, sm.spike);
    return Math.sqrt(vol || 0) * s;
  }

  // 정렬
  const sorted = cand.slice().sort((a, b) => {
    if (sparklineSort === 'impact') {
      return impactScore(b.id, b.volume) - impactScore(a.id, a.volume);
    }
    if (sparklineSort === 'spike') {
      const sa = getSpikeMetrics(a.id); const sb = getSpikeMetrics(b.id);
      return (sb ? sb.spike : -Infinity) - (sa ? sa.spike : -Infinity);
    }
    if (sparklineSort === 'volume') return (b.volume || 0) - (a.volume || 0);
    return 0;
  });

  // 페이지네이션
  const totalPages = Math.max(1, Math.ceil(sorted.length / SPARKLINE_PAGE_SIZE));
  if (sparklinePage > totalPages) sparklinePage = 1;
  const start = (sparklinePage - 1) * SPARKLINE_PAGE_SIZE;
  const top = sorted.slice(start, start + SPARKLINE_PAGE_SIZE);

  document.getElementById('sparkline-wall-count').textContent = `· ${sorted.length}개`;
  renderSparklinePagination(sparklinePage, totalPages, sorted.length);

  const gridEl = document.getElementById('sparkline-grid');
  gridEl.innerHTML = top.map(n => {
    const info = CLUSTER_DATA.keyword_info[n.id];
    const mv = info.monthly_volume;
    const vals = mv.map(m => Number(m.total || 0));
    const max = Math.max(1, ...vals);
    const spark = vals.map((v, i) => {
      const x = (i / (vals.length - 1)) * 100;
      const y = 100 - (v / max) * 100;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
    const sm = getSpikeMetrics(n.id);
    const stroke = sm && sm.kind === 'spike' ? '#e63946' : (sm && sm.kind === 'coldStart' ? '#7c5ec4' : '#3a8f3a');
    let tag = '';
    if (sm && sm.kind !== 'growth') {
      const tm = SPIKE_TAG_META[sm.kind];
      tag = `<span class="sc-tag" style="background:${tm.color}22; color:${tm.color};">${tm.label}</span>`;
    }
    const spikeStr = sm ? ((sm.spike >= 0 ? '+' : '') + Math.round(sm.spike * 100) + '%') : '-';
    return `
      <div class="sparkline-cell" data-kw="${n.id.replace(/"/g, '&quot;')}">
        <div class="sc-header">
          <span class="sc-kw" title="${n.id}">${n.id}</span>
          ${tag}
        </div>
        <svg class="sc-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
          <polyline fill="none" stroke="${stroke}" stroke-width="2" vector-effect="non-scaling-stroke" points="${spark}"/>
        </svg>
        <div class="sc-meta">
          <span>vol ${(n.volume || 0).toLocaleString()}</span>
          <span class="sc-spike" style="color:${stroke};">${spikeStr}</span>
        </div>
      </div>
    `;
  }).join('');
  // 셀 클릭 → drawer
  gridEl.querySelectorAll('.sparkline-cell').forEach(el => {
    el.addEventListener('click', () => {
      const kw = el.dataset.kw;
      try { openKeywordDetail(kw); } catch(e) { console.error(e); }
    });
  });
}

// 정렬 버튼
document.querySelectorAll('#sparkline-wall-sort button').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('#sparkline-wall-sort button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    sparklineSort = btn.dataset.sort;
    sparklinePage = 1;
    renderSparklineWall();
  });
});

// 종류 필터 chip
document.querySelectorAll('#sparkline-wall-filters .wall-chip').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('#sparkline-wall-filters .wall-chip').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    sparklineKind = btn.dataset.kind;
    sparklinePage = 1;
    renderSparklineWall();
  });
});

// 페이지네이션 렌더
function renderSparklinePagination(current, total, itemCount) {
  const el = document.getElementById('sparkline-pagination');
  if (!el) return;
  if (total <= 1) { el.innerHTML = ''; return; }

  // 최대 7개 페이지 버튼 · 앞뒤 · 첫·끝 포함
  const pages = new Set([1, total, current, current - 1, current + 1]);
  // 여유 있으면 앞뒤 하나 더
  if (total <= 9) for (let i = 1; i <= total; i++) pages.add(i);
  else {
    pages.add(current - 2); pages.add(current + 2);
  }
  const sorted = [...pages].filter(p => p >= 1 && p <= total).sort((a, b) => a - b);

  let html = `<button ${current === 1 ? 'disabled' : ''} data-page="${current - 1}">‹</button>`;
  let last = 0;
  sorted.forEach(p => {
    if (last && p - last > 1) html += `<span class="page-info">…</span>`;
    html += `<button class="${p === current ? 'active' : ''}" data-page="${p}">${p}</button>`;
    last = p;
  });
  html += `<button ${current === total ? 'disabled' : ''} data-page="${current + 1}">›</button>`;
  html += `<span class="page-info">${itemCount}개 · ${current}/${total}p</span>`;
  el.innerHTML = html;
  el.querySelectorAll('button[data-page]').forEach(btn => {
    btn.addEventListener('click', () => {
      const p = parseInt(btn.dataset.page, 10);
      if (!isNaN(p)) { sparklinePage = p; renderSparklineWall(); }
    });
  });
}

// 카드뷰 · 키워드 아이템 클릭 위임 · 클러스터/인텐트/트렌드 모드 다 커버
document.getElementById('card-grid').addEventListener('click', (ev) => {
  const item = ev.target.closest('.card-kw-item');
  if (!item) return;
  const kw = item.querySelector('.kw');
  if (kw) { try { openKeywordDetail(kw.getAttribute('title')); } catch(e) { console.error(e); } }
});
// 초기 호출은 07-sidebar-modes.js 뷰 토글 클릭 시에 수행 (TDZ 방어)

