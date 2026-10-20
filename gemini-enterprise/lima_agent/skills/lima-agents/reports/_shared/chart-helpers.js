// 차트 공통 도우미 · lima-agents 리포트
// 차트는 외부 라이브러리·CDN 없이 inline SVG로 그린다 (listeningmind-universal _shared-core.md §7).
// 좌표는 데이터에서 결정론으로 계산하고, 값 안내는 SVG <title>(마우스오버)로 붙인다.
(function () {
  const PALETTE = {
    rose: '#c85b7f',
    teal: '#2f8f8b',
    gold: '#c99a3a',
    violet: '#6d5aa8',
    blue: '#3b7fbf',
    ink: '#2b2440',
    muted: '#7d7793',
    line: '#e7e2ec',
  };
  window.LIMA_PALETTE = PALETTE;
  window.LIMA_SERIES = [
    PALETTE.rose,
    PALETTE.teal,
    PALETTE.gold,
    PALETTE.violet,
    PALETTE.blue,
    '#e89f6a',
    '#8fd4c8',
  ];

  // 유틸 · 숫자 포맷 (1.2K · 340K · 1.5M)
  window.limaFmtNum = function (v) {
    if (v == null || isNaN(v)) return '-';
    const n = Number(v);
    if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(1) + 'M';
    if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1) + 'K';
    return String(Math.round(n));
  };

  window.limaFmtPct = function (v, decimals = 0) {
    if (v == null || isNaN(v)) return '-';
    return (Number(v) * 100).toFixed(decimals) + '%';
  };

  // ===== inline SVG 차트 =====
  const FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif";
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const r1 = (v) => Math.round(v * 10) / 10;

  // 0부터 시작하는 눈금 — 최대값을 1·2·5 단위로 올림
  function niceTicks(max, count = 4) {
    if (!(max > 0)) return [0, 1];
    const raw = max / count;
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 5, 10].map((m) => m * mag).find((s) => s >= raw);
    const ticks = [];
    for (let t = 0; t <= max + step * 0.001; t += step) ticks.push(t);
    if (ticks[ticks.length - 1] < max) ticks.push(ticks[ticks.length - 1] + step);
    return ticks;
  }

  function svgOpen(w, h, label) {
    return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" role="img" aria-label="${esc(label || '차트')}" style="font-family:${FONT};display:block">`;
  }

  function legendHtml(items) {
    return `<div class="lima-legend" style="display:flex;flex-wrap:wrap;gap:6px 14px;font-size:12px;color:${PALETTE.muted};margin-bottom:6px">` +
      items.map((it) => `<span style="display:inline-flex;align-items:center;gap:5px"><i style="width:10px;height:10px;border-radius:2px;background:${it.color};display:inline-block"></i>${esc(it.label)}</span>`).join('') +
      '</div>';
  }

  // 도넛 — 조각 면적 ∝ 값. 범례에 비중(%)을 함께 적는다.
  window.limaDonut = function (el, labels, values, colors, opts = {}) {
    const total = values.reduce((a, b) => a + b, 0);
    if (!total) { el.innerHTML = '<div class="muted" style="padding:12px 0;font-size:12px;">데이터 없음</div>'; return; }
    const W = 360, H = 220, cx = 110, cy = 110, R = 100, r = R * 0.55;
    let a0 = -Math.PI / 2, paths = '';
    values.forEach((v, i) => {
      if (!v) return;
      const frac = v / total, color = colors[i % colors.length];
      const tip = `<title>${esc(labels[i])} · ${limaFmtNum(v)} (${(frac * 100).toFixed(1)}%)</title>`;
      if (frac >= 0.9999) {
        paths += `<circle cx="${cx}" cy="${cy}" r="${(R + r) / 2}" fill="none" stroke="${color}" stroke-width="${R - r}">${tip}</circle>`;
        return;
      }
      const a1 = a0 + frac * 2 * Math.PI, big = frac > 0.5 ? 1 : 0;
      const p = (rad, ang) => `${r1(cx + rad * Math.cos(ang))},${r1(cy + rad * Math.sin(ang))}`;
      paths += `<path d="M${p(R, a0)} A${R},${R} 0 ${big} 1 ${p(R, a1)} L${p(r, a1)} A${r},${r} 0 ${big} 0 ${p(r, a0)} Z" fill="${color}" stroke="#fff" stroke-width="1.5">${tip}</path>`;
      a0 = a1;
    });
    let leg = '', ly = Math.max(14, cy - (labels.length * 22) / 2 + 8);
    labels.forEach((l, i) => {
      const pct = ((values[i] / total) * 100).toFixed(1);
      leg += `<rect x="236" y="${ly - 9}" width="10" height="10" rx="2" fill="${colors[i % colors.length]}"/>` +
        `<text x="252" y="${ly}" font-size="12" fill="${PALETTE.ink}">${esc(l)} ${pct}%</text>`;
      ly += 22;
    });
    el.innerHTML = svgOpen(W, H, opts.label) + paths + leg + '</svg>';
  };

  // 가로 막대 — 계열 1개 이상(묶음 막대). 축은 0 기준, 정규화는 전 계열 최대값 기준.
  // datasets: [{label, data:[…], color}]
  window.limaHBar = function (el, labels, datasets, opts = {}) {
    if (!labels.length) { el.innerHTML = '<div class="muted" style="padding:12px 0;font-size:12px;">데이터 없음</div>'; return; }
    const n = datasets.length, barH = n > 1 ? 8 : 15, gap = n > 1 ? 6 : 8;
    const rowH = barH * n + gap, labW = opts.labelWidth || 124, W = 400, padT = 4, axisH = 20;
    const plotW = W - labW - 12, H = padT + rowH * labels.length + axisH;
    const max = Math.max(1, ...datasets.flatMap((d) => d.data));
    const ticks = niceTicks(max), top = ticks[ticks.length - 1];
    const x = (v) => labW + (v / top) * plotW;
    let s = '';
    ticks.forEach((t) => {
      s += `<line x1="${r1(x(t))}" y1="${padT}" x2="${r1(x(t))}" y2="${H - axisH}" stroke="${PALETTE.line}"/>` +
        `<text x="${r1(x(t))}" y="${H - 6}" font-size="10" fill="${PALETTE.muted}" text-anchor="middle">${limaFmtNum(t)}</text>`;
    });
    labels.forEach((l, i) => {
      const y0 = padT + i * rowH + gap / 2;
      const short = l.length > 14 ? l.slice(0, 13) + '…' : l;
      s += `<text x="${labW - 6}" y="${r1(y0 + (barH * n) / 2 + 4)}" font-size="11" fill="${PALETTE.ink}" text-anchor="end"><title>${esc(l)}</title>${esc(short)}</text>`;
      datasets.forEach((d, j) => {
        const v = d.data[i] || 0, w = Math.max(0, x(v) - labW);
        s += `<rect x="${labW}" y="${r1(y0 + j * barH)}" width="${r1(w)}" height="${barH - 1}" rx="2" fill="${d.color}"><title>${esc(l)}${n > 1 ? ' · ' + esc(d.label) : ''} · ${opts.unit || '검색량'} ${limaFmtNum(v)}</title></rect>`;
      });
    });
    s += `<line x1="${labW}" y1="${padT}" x2="${labW}" y2="${H - axisH}" stroke="${PALETTE.muted}"/>`;
    el.style.height = 'auto';
    el.innerHTML = (n > 1 ? legendHtml(datasets) : '') + svgOpen(W, H, opts.label) + s + '</svg>';
  };

  // 세로 묶음 막대 — y축 0 기준, 정규화는 전 계열 최대값 기준.
  window.limaVBar = function (el, labels, datasets, opts = {}) {
    if (!labels.length) { el.innerHTML = '<div class="muted" style="padding:12px 0;font-size:12px;">데이터 없음</div>'; return; }
    const W = 760, H = 340, padL = 48, padR = 10, padT = 10, padB = 56;
    const plotW = W - padL - padR, plotH = H - padT - padB;
    const max = Math.max(1, ...datasets.flatMap((d) => d.data));
    const ticks = niceTicks(max), top = ticks[ticks.length - 1];
    const y = (v) => padT + plotH - (v / top) * plotH;
    const slot = plotW / labels.length, n = datasets.length;
    const bw = Math.max(2, Math.min(18, (slot * 0.8) / n));
    let s = '';
    ticks.forEach((t) => {
      s += `<line x1="${padL}" y1="${r1(y(t))}" x2="${W - padR}" y2="${r1(y(t))}" stroke="${PALETTE.line}"/>` +
        `<text x="${padL - 6}" y="${r1(y(t) + 3)}" font-size="10" fill="${PALETTE.muted}" text-anchor="end">${limaFmtNum(t)}</text>`;
    });
    labels.forEach((l, i) => {
      const gx = padL + i * slot + (slot - bw * n) / 2;
      datasets.forEach((d, j) => {
        const v = d.data[i] || 0;
        s += `<rect x="${r1(gx + j * bw)}" y="${r1(y(v))}" width="${r1(bw - 1)}" height="${r1(padT + plotH - y(v))}" fill="${d.color}"><title>${esc(l)} · ${esc(d.label)} · ${opts.unit || '검색량'} ${limaFmtNum(v)}</title></rect>`;
      });
      const short = l.length > 8 ? l.slice(0, 7) + '…' : l;
      const lx = r1(padL + i * slot + slot / 2), lyy = padT + plotH + 14;
      s += `<text x="${lx}" y="${lyy}" font-size="11" fill="${PALETTE.ink}" text-anchor="end" transform="rotate(-30 ${lx} ${lyy})"><title>${esc(l)}</title>${esc(short)}</text>`;
    });
    s += `<line x1="${padL}" y1="${padT + plotH}" x2="${W - padR}" y2="${padT + plotH}" stroke="${PALETTE.muted}"/>`;
    el.innerHTML = legendHtml(datasets) + svgOpen(W, H, opts.label) + s + '</svg>';
  };

  // 탭 전환 · 페이지 로드 시 .tabs > .tab 자동 wiring
  window.limaWireTabs = function () {
    const tabs = document.querySelectorAll('.tabs .tab');
    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        const key = tab.dataset.view;
        tabs.forEach(t => t.classList.toggle('active', t === tab));
        document.querySelectorAll('section.view').forEach(sec => {
          sec.classList.toggle('active', sec.dataset.view === key);
        });
      });
    });
  };
})();
