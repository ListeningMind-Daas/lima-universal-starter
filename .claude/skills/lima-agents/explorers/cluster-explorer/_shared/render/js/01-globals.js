// 산뜻한 파스텔 팔레트 · 채도 낮추고 명도 올림 · 밝고 청량한 톤
const PASTEL_COLORS = [
  '#8bb8e8',  // 산뜻한 하늘
  '#f4a6b8',  // 부드러운 로즈
  '#a8d99b',  // 산뜻한 연두
  '#b5a3e0',  // 라이트 라벤더
  '#f4c58f',  // 살구
  '#8fd4c8',  // 민트
  '#f0a8c9',  // 페일 핑크
  '#c0d67c',  // 라이트 라임
  '#9dabe8',  // 스카이 인디고
  '#e0b088',  // 밀크티
  '#c99fdd',  // 페일 퍼플
  '#8dcda8',  // 페일 세이지
  '#e6c473',  // 페일 골드
  '#e39ecb',  // 라이트 마젠타
  '#87c9bd',  // 페일 티얼
  '#c4d073',  // 페일 올리브
  '#e8a599',  // 페일 코랄
  '#a3cee0',  // 페일 스카이
  '#cadb8c',  // 페일 옐로우그린
  '#e0b0cf',  // 라이트 로즈핑크
  '#96b9dd',  // 페일 블루
  '#c7dd8a'   // 페일 애플그린
];

// 데이터 준비
const svg = d3.select('#graph');
const graphView = document.getElementById('graph-view');
const width = () => graphView.clientWidth || 900;
const height = () => graphView.clientHeight || 700;
const tooltip = d3.select('#tooltip');

const seedSet = new Set(CLUSTER_DATA.seeds);
const bridgeSet = new Set(CLUSTER_DATA.bridge_kws || []);
const hubSet = new Set(CLUSTER_DATA.hub_keywords || []);
const clusterLabels = CLUSTER_DATA.cluster_labels || {};

// 노드 · 크기 상한 축소 (max 14 · min 2.5)
const MAX_RADIUS = 14;
const MIN_RADIUS = 2.5;
const nodes = CLUSTER_DATA.nodes.map(n => ({
  id: n.keyword,
  volume: n.volume || 0,
  community: n.community,
  radius: Math.min(MAX_RADIUS, Math.max(MIN_RADIUS, Math.sqrt(n.volume || 100) * 0.18)),
  isSeed: seedSet.has(n.keyword),
  isHub: hubSet.has(n.keyword),
  isBridge: bridgeSet.has(n.keyword)
}));

const nodeIndex = new Map(nodes.map(n => [n.id, n]));

// community → letter mapping (색상 안정성)
const communityToColorIdx = {};
Object.entries(clusterLabels)
  .sort((a, b) => (a[1].letter || 'Z').charCodeAt(0) - (b[1].letter || 'Z').charCodeAt(0))
  .forEach(([cid, info], idx) => {
    communityToColorIdx[cid] = idx;
  });

function colorFor(community) {
  // 문자열/숫자 모두 대응 · lookup 실패해도 팔레트 안 색상 보장
  const key = String(community ?? '');
  let idx = communityToColorIdx[key];
  if (idx === undefined) {
    const parsed = parseInt(key, 10);
    idx = Number.isFinite(parsed) ? parsed : 0;
  }
  return PASTEL_COLORS[Math.abs(idx) % PASTEL_COLORS.length];
}

// 카드 ? 아이콘 · hover 시 조건·활용 설명 툴팁 (전역 tooltip으로 표시 · 위치 자동 계산)
function buildCardHelp(meta) {
  if (!meta || (!meta.condition && !meta.usage)) return '';
  const escAttr = s => String(s ?? '').replace(/"/g, '&quot;');
  const cond = meta.condition ? escAttr(meta.condition) : '';
  const use = meta.usage ? escAttr(meta.usage) : '';
  return `<span class="card-help" data-help-cond="${cond}" data-help-use="${use}">?</span>`;
}

// SVG 스파크라인 생성 · 툴팁에서 쓰는 미니 (라벨 없음)
// monthly_volume은 API 응답 기준 과거 → 최신 순
function buildSparkline(monthlyVolume, w, h) {
  if (!Array.isArray(monthlyVolume) || monthlyVolume.length < 2) return '';
  const arr = monthlyVolume;
  const vals = arr.map(m => Number(m.total || 0));
  const max = Math.max(1, ...vals);
  const step = w / (vals.length - 1);
  const points = vals.map((v, i) => {
    const x = i * step;
    const y = h - (v / max) * (h - 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  const first = vals[0], last = vals[vals.length - 1];
  const strokeColor = last >= first ? '#3a8f3a' : '#c94a5f';
  return `<svg width="${w}" height="${h}" style="display:block; margin-top:4px;">
    <polyline fill="none" stroke="${strokeColor}" stroke-width="1.2" points="${points}"/>
  </svg>`;
}

// 상세 Drawer용 · 축·hover 툴팁 있는 큰 트렌드 차트
function buildTrendChart(monthlyVolume, w, h) {
  if (!Array.isArray(monthlyVolume) || monthlyVolume.length < 2) return '';
  const arr = monthlyVolume;  // 이미 과거 → 최신 순
  const vals = arr.map(m => Number(m.total || 0));
  const months = arr.map(m => String(m.month || ''));
  const max = Math.max(1, ...vals);
  // 오른쪽·아래 여백 넉넉하게 · 마지막 X 라벨·툴팁 잘림 방지
  const padL = 42, padR = 32, padT = 6, padB = 24;
  const chartW = w - padL - padR;
  const chartH = h - padT - padB;
  const step = vals.length > 1 ? chartW / (vals.length - 1) : 0;
  const pts = vals.map((v, i) => [padL + i * step, padT + chartH - (v / max) * chartH]);
  const line = pts.map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
  const first = vals[0], last = vals[vals.length - 1];
  const stroke = last >= first ? '#3a8f3a' : '#c94a5f';
  // Y축 눈금 4개
  const yTicks = [0, max / 3, (2 * max) / 3, max];
  const yTickHtml = yTicks.map(v => {
    const y = padT + chartH - (v / max) * chartH;
    return `
      <line x1="${padL}" y1="${y}" x2="${padL + chartW}" y2="${y}" stroke="#eee" stroke-width="0.6"/>
      <text x="${padL - 6}" y="${y + 3}" text-anchor="end" font-size="9" fill="#999">${v >= 1000 ? (v/1000).toFixed(1) + 'K' : Math.round(v)}</text>
    `;
  }).join('');
  // X축 라벨 3개 (첫·중간·마지막) · 마지막은 오른쪽으로 넉넉히
  const xLabelIdx = [0, Math.floor(vals.length / 2), vals.length - 1];
  const xLabelHtml = xLabelIdx.map(i => {
    const x = padL + i * step;
    return `<text x="${x}" y="${h - 6}" text-anchor="${i === 0 ? 'start' : (i === vals.length - 1 ? 'end' : 'middle')}" font-size="9" fill="#999">${months[i]}</text>`;
  }).join('');
  // 점 hover 영역
  const dots = vals.map((v, i) => {
    const [x, y] = pts[i];
    return `<circle cx="${x}" cy="${y}" r="7" fill="transparent" data-idx="${i}" data-month="${months[i]}" data-val="${v}"/>`;
  }).join('');
  return `
    <div style="position:relative; overflow:visible;" data-chart-w="${w}">
      <svg class="trend-chart" width="${w}" height="${h}" style="display:block; overflow:visible;">
        ${yTickHtml}
        <polyline fill="none" stroke="${stroke}" stroke-width="1.6" points="${line}" />
        <line class="trend-cursor" x1="0" y1="${padT}" x2="0" y2="${padT + chartH}" stroke="#7c5ec4" stroke-width="1" stroke-dasharray="3,3" style="display:none;"/>
        <circle class="trend-marker" r="3.5" fill="${stroke}" stroke="#fff" stroke-width="1.5" style="display:none;"/>
        ${dots}
        ${xLabelHtml}
      </svg>
      <div class="trend-tip" style="display:none; position:absolute; background:rgba(50,50,50,0.95); color:#fff; padding:5px 8px; border-radius:5px; font-size:11px; pointer-events:none; white-space:nowrap; z-index:5;"></div>
    </div>
  `;
}

// 차트에 hover 이벤트 바인딩 · 툴팁 위치 자동 (오른쪽 반이면 왼쪽으로)
function bindTrendChartHover(rootEl) {
  const wrap = rootEl.querySelector('div[data-chart-w]');
  const svg = rootEl.querySelector('svg.trend-chart');
  if (!svg || !wrap) return;
  const chartW = Number(wrap.getAttribute('data-chart-w') || 340);
  const tip = rootEl.querySelector('.trend-tip');
  const cursor = svg.querySelector('.trend-cursor');
  const marker = svg.querySelector('.trend-marker');
  const dots = svg.querySelectorAll('circle[data-idx]');
  dots.forEach(dot => {
    dot.addEventListener('mouseenter', () => {
      const cx = parseFloat(dot.getAttribute('cx'));
      const cy = parseFloat(dot.getAttribute('cy'));
      const month = dot.getAttribute('data-month');
      const val = parseFloat(dot.getAttribute('data-val'));
      cursor.setAttribute('x1', cx);
      cursor.setAttribute('x2', cx);
      cursor.style.display = 'block';
      marker.setAttribute('cx', cx);
      marker.setAttribute('cy', cy);
      marker.style.display = 'block';
      tip.textContent = `${month} · ${val.toLocaleString()}`;
      tip.style.display = 'block';
      // 툴팁 크기 측정 후 · 오른쪽 벗어나면 왼쪽으로
      const tipW = tip.offsetWidth || 90;
      const rightPos = cx + 8;
      const overflow = rightPos + tipW - chartW;
      tip.style.left = (overflow > 0 ? cx - tipW - 8 : rightPos) + 'px';
      tip.style.top = (cy - 12) + 'px';
    });
    dot.addEventListener('mouseleave', () => {
      cursor.style.display = 'none';
      marker.style.display = 'none';
      tip.style.display = 'none';
    });
  });
}

function buildNodeTooltip(d) {
  const info = clusterLabels[d.community];
  const clusterName = info ? `${info.letter} · ${info.name}` : `Cluster ${d.community}`;
  const kwInfo = (CLUSTER_DATA.keyword_info || {})[d.id] || {};
  const trend = kwInfo.ads_metrics && kwInfo.ads_metrics.volume_trend;
  const intents = kwInfo.intents;
  let extra = '';
  if (trend !== null && trend !== undefined) {
    const pct = (trend >= 0 ? '+' : '') + Math.round(trend * 100) + '%';
    const color = trend >= 0 ? '#7dd58b' : '#f8a4b6';
    extra += `<div class="tt-meta" style="margin-top:4px;">3개월 트렌드 · <span style="color:${color}; font-weight:700;">${pct}</span></div>`;
  }
  if (Array.isArray(kwInfo.monthly_volume) && kwInfo.monthly_volume.length > 1) {
    extra += buildSparkline(kwInfo.monthly_volume, 160, 32);
  }
  if (intents) {
    extra += `<div class="tt-meta" style="margin-top:4px;">I:${(intents.i ?? 0)} · N:${(intents.n ?? 0)} · C:${(intents.c ?? 0)} · T:${(intents.t ?? 0)}</div>`;
  }
  return `
    <div class="tt-title">${d.id}</div>
    <div class="tt-meta">Volume: ${(d.volume ?? 0).toLocaleString()}</div>
    <div class="tt-meta">${clusterName}</div>
    ${extra}
  `;
}
