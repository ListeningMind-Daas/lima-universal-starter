// ===== CEP 상태 관리 (엔티티와 별개 undo 지원) =====
const ORIGINAL_CEP = CLUSTER_DATA.cep_grouped
  ? JSON.parse(JSON.stringify(CLUSTER_DATA.cep_grouped))
  : null;
let liveCep = ORIGINAL_CEP ? JSON.parse(JSON.stringify(ORIGINAL_CEP)) : null;

function findCepSubgroup(wKey, subLabel) {
  if (!liveCep || !liveCep[wKey]) return null;
  return liveCep[wKey].subgroups[subLabel] || null;
}

function pushCepHistory() {
  actionHistory.push({ type: 'cep', snapshot: JSON.parse(JSON.stringify(liveCep)) });
  if (actionHistory.length > 30) actionHistory.shift();
  updateUndoButton();
}

function removeCepSubgroup(wKey, subLabel) {
  if (!liveCep[wKey] || !liveCep[wKey].subgroups[subLabel]) return;
  pushCepHistory();
  const removed = liveCep[wKey].subgroups[subLabel];
  delete liveCep[wKey].subgroups[subLabel];
  // 상위 W 통계 재계산
  recalcCepW(wKey);
  renderCepView();
  showSnackbar(`"${subLabel}" 제거됨`, true);
}

function moveCepSubgroup(fromW, subLabel, toW) {
  if (!liveCep[fromW] || !liveCep[fromW].subgroups[subLabel]) return;
  if (fromW === toW) return;
  if (!liveCep[toW]) return;
  pushCepHistory();
  const sg = liveCep[fromW].subgroups[subLabel];
  delete liveCep[fromW].subgroups[subLabel];
  // 대상 W에 이미 같은 이름 있으면 합침
  if (liveCep[toW].subgroups[subLabel]) {
    const existingKws = new Set(liveCep[toW].subgroups[subLabel].keywords.map(k => k.keyword));
    sg.keywords.forEach(k => { if (!existingKws.has(k.keyword)) liveCep[toW].subgroups[subLabel].keywords.push(k); });
    liveCep[toW].subgroups[subLabel].keywords.sort((a, b) => b.volume - a.volume);
    liveCep[toW].subgroups[subLabel].count = liveCep[toW].subgroups[subLabel].keywords.length;
    liveCep[toW].subgroups[subLabel].total_volume = liveCep[toW].subgroups[subLabel].keywords.reduce((s, k) => s + k.volume, 0);
  } else {
    liveCep[toW].subgroups[subLabel] = sg;
  }
  recalcCepW(fromW);
  recalcCepW(toW);
  renderCepView();
  const toLabel = CEP_META[toW]?.label || toW;
  showSnackbar(`"${subLabel}" → ${toLabel}로 이동`, true);
}

function recalcCepW(wKey) {
  if (!liveCep[wKey]) return;
  const subs = liveCep[wKey].subgroups;
  const totalKws = new Set();
  for (const sg of Object.values(subs)) {
    sg.keywords.forEach(k => totalKws.add(k.keyword));
  }
  liveCep[wKey].total_count = totalKws.size;
  liveCep[wKey].total_volume = Object.values(subs).reduce((s, sg) => s + sg.total_volume, 0);
}

// CEP W 이동 모달
function openCepMoveModal(fromW, subLabel) {
  const modal = document.getElementById('merge-modal-bg');
  const list = document.getElementById('merge-list');
  const title = document.getElementById('merge-title');
  const sub = document.getElementById('merge-sub');
  title.textContent = 'CEP 카테고리 이동';
  sub.textContent = `"${subLabel}" 을(를) 어느 W로 옮길까요?`;
  list.innerHTML = '';
  Object.keys(liveCep).forEach(wKey => {
    if (wKey === fromW) return;
    const meta = CEP_META[wKey];
    if (!meta) return;
    const opt = document.createElement('div');
    opt.className = 'merge-option';
    opt.innerHTML = `
      <span class="merge-cat-tag" style="background: ${meta.color};">${meta.label.split(' · ')[0]}</span>
      <span style="flex:1;">${meta.sub}</span>
    `;
    opt.onclick = () => { moveCepSubgroup(fromW, subLabel, wKey); modal.classList.remove('show'); };
    list.appendChild(opt);
  });
  modal.classList.add('show');
}

// undo 함수 확장 · CEP도 스택에서 pop
const originalUndo = undo;
undo = function() {
  if (actionHistory.length === 0) return;
  const last = actionHistory.pop();
  updateUndoButton();
  // 엔티티 vs CEP 판별 (스냅샷 형식)
  if (last && last.type === 'cep') {
    liveCep = last.snapshot;
    renderCepView();
  } else {
    // 이전 방식 · 엔티티 스냅샷 (직접 객체)
    liveEntities = last.snapshot || last;
    renderEntityView();
  }
  hideSnackbar();
};

// reset · CEP도 초기화
const originalReset = resetEntities;
resetEntities = function() {
  if (ORIGINAL_ENTITIES) {
    pushHistory();
    liveEntities = JSON.parse(JSON.stringify(ORIGINAL_ENTITIES));
    renderEntityView();
  }
  if (ORIGINAL_CEP) {
    pushCepHistory();
    liveCep = JSON.parse(JSON.stringify(ORIGINAL_CEP));
    renderCepView();
  }
  showSnackbar('원본으로 리셋됨');
};

// pushHistory 확장 · 엔티티 액션도 type 붙임
const originalPushHistory = pushHistory;
pushHistory = function() {
  actionHistory.push({ type: 'entity', snapshot: JSON.parse(JSON.stringify(liveEntities)) });
  if (actionHistory.length > 30) actionHistory.shift();
  updateUndoButton();
};

// ===== CEP뷰 · 7W + 2단계 트리 + 글라스모피즘 =====

// 7W 메타 · 커스텀 SVG 아이콘 (선형 · 심플 · 파스텔과 조화)
const CEP_META = {
  WHY: {
    label: 'WHY · 왜?', sub: '동기·목적',
    gradient: 'linear-gradient(135deg, #ffb88c 0%, #ff8f6b 100%)',  // 살구·코랄
    color: '#e8785a',
    svg: `<svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`
  },
  WHEN: {
    label: 'WHEN · 언제?', sub: '시점·타이밍',
    gradient: 'linear-gradient(135deg, #a3c9ff 0%, #6a9eff 100%)',  // 하늘·인디고
    color: '#5b8ec4',
    svg: `<svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15 14"/></svg>`
  },
  WHERE: {
    label: 'WHERE · 어디서?', sub: '장소·채널',
    gradient: 'linear-gradient(135deg, #a3e0d4 0%, #5cb0a6 100%)',  // 민트
    color: '#5cb0a6',
    svg: `<svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>`
  },
  WHILE: {
    label: 'WHILE · 하면서?', sub: '동반 활동',
    gradient: 'linear-gradient(135deg, #b8e0a8 0%, #7cb56d 100%)',  // 연두·그린
    color: '#7cb56d',
    svg: `<svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="5" r="2"/><path d="M8 10h4l3 4 2 5"/><path d="M9 21l3-7"/><path d="M5 14l3-4"/></svg>`
  },
  WHOM: {
    label: 'WHOM · 누구를?', sub: '대상·페르소나',
    gradient: 'linear-gradient(135deg, #f5b3d1 0%, #d47a94 100%)',  // 핑크·로즈
    color: '#d47a94',
    svg: `<svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`
  },
  WITH_WHAT: {
    label: 'WITH · 무엇과?', sub: '조합·페어링',
    gradient: 'linear-gradient(135deg, #c9a8ee 0%, #8b5ec4 100%)',  // 라벤더·보라
    color: '#8b5ec4',
    svg: `<svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>`
  },
  HOW_FEEL: {
    label: 'HOW · 어떻게?', sub: '감정·상태',
    gradient: 'linear-gradient(135deg, #ffd6a3 0%, #ffa870 100%)',  // 파스텔 오렌지
    color: '#e89f6a',
    svg: `<svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg>`
  }
};

function renderCepView() {
  const grid = document.getElementById('cep-grid');
  if (!grid) return;
  grid.innerHTML = '';
  const cepGrouped = liveCep || {};
  if (Object.keys(cepGrouped).length === 0) {
    grid.innerHTML = '<div style="color:#888; font-size:13px;">CEP 데이터 없음</div>';
    return;
  }

  // 확장 상태 보존
  const expandedSubs = new Set(
    Array.from(document.querySelectorAll('.cep-subgroup.expanded')).map(el => el.dataset.key)
  );

  const sortedCeps = Object.entries(cepGrouped).sort((a, b) => b[1].total_volume - a[1].total_volume);

  sortedCeps.forEach(([wKey, info]) => {
    const meta = CEP_META[wKey];
    if (!meta) return;

    const card = document.createElement('div');
    card.className = 'cep-card cep-w';
    card.dataset.w = wKey;

    // W 카드 자체 drop (빈 영역 = 서브그룹 이동)
    card.addEventListener('dragover', ev => {
      ev.preventDefault();
      if (ev.dataTransfer.types.includes('text/cep-subgroup')) card.classList.add('drag-over');
    });
    card.addEventListener('dragleave', () => card.classList.remove('drag-over'));
    card.addEventListener('drop', ev => {
      ev.preventDefault();
      card.classList.remove('drag-over');
      const payload = ev.dataTransfer.getData('text/cep-subgroup');
      if (!payload) return;
      const [fromW, subLabel] = payload.split('||');
      if (fromW !== wKey) moveCepSubgroup(fromW, subLabel, wKey);
    });

    let subgroupsHtml = '';
    const subgroupsObj = info.subgroups || {};
    const sortedSubs = Object.entries(subgroupsObj).sort((a, b) => (b[1].total_volume ?? 0) - (a[1].total_volume ?? 0));
    sortedSubs.forEach(([subLabel, sg]) => {
      let kwHtml = '';
      const kws = sg.keywords || [];
      kws.forEach(k => {
        kwHtml += `\n          <div class="cep-kw-item">\n            <span class="kw" title="${k.keyword}">${k.keyword}</span>\n            <span class="vol">${(k.volume ?? 0).toLocaleString()}</span>\n          </div>`;
      });
      const sgKey = `${wKey}||${subLabel}`;
      const expClass = expandedSubs.has(sgKey) ? ' expanded' : '';
      subgroupsHtml += `\n        <div class="cep-subgroup${expClass}" data-key="${sgKey}" data-w="${wKey}" data-sub="${subLabel}" draggable="true">\n          <div class="cep-subgroup-header">\n            <span class="sub-chev" style="color: ${meta.color};">▶</span>\n            <span class="sub-name" style="color: ${meta.color};">${subLabel}</span>\n            <span class="sub-meta">${sg.count ?? kws.length} · ${(sg.total_volume ?? 0).toLocaleString()}</span>\n            <span class="sg-actions">\n              <button class="sg-btn remove" title="제거">−</button>\n              <button class="sg-btn move" title="다른 W로 이동">⇢</button>\n            </span>\n          </div>\n          <div class="cep-subgroup-body">${kwHtml}</div>\n        </div>`;
    });

    card.innerHTML = `
      <div class="cep-header">
        <div class="cep-icon-wrap" style="background: ${meta.gradient};">
          ${meta.svg}
        </div>
        <div class="label-wrap">
          <span class="label" style="color: ${meta.color};">${meta.label}</span>
          <span class="sub-label">${meta.sub}</span>
        </div>
      </div>
      <div class="cep-vol-total">
        <span>${sortedSubs.length}개 서브그룹 · ${info.total_count ?? 0}개 키워드 · 검색량</span>
        <span class="val">${(info.total_volume ?? 0).toLocaleString()}</span>
      </div>
      <div class="cep-subgroups">${subgroupsHtml || '<div style="color:#aaa; font-size:12px; padding:8px; text-align:center;">여기로 drag&amp;drop</div>'}</div>
    `;

    // 서브그룹 이벤트 바인딩
    card.querySelectorAll('.cep-subgroup').forEach(sg => {
      const fromW = sg.dataset.w;
      const subLabel = sg.dataset.sub;

      sg.querySelector('.cep-subgroup-header').onclick = (ev) => {
        if (ev.target.closest('.sg-actions')) return;
        sg.classList.toggle('expanded');
      };
      sg.querySelector('.sg-btn.remove').onclick = (ev) => { ev.stopPropagation(); removeCepSubgroup(fromW, subLabel); };
      sg.querySelector('.sg-btn.move').onclick = (ev) => { ev.stopPropagation(); openCepMoveModal(fromW, subLabel); };

      // 드래그
      sg.addEventListener('dragstart', ev => {
        ev.dataTransfer.setData('text/cep-subgroup', `${fromW}||${subLabel}`);
        ev.dataTransfer.effectAllowed = 'move';
        sg.classList.add('dragging');
      });
      sg.addEventListener('dragend', () => sg.classList.remove('dragging'));
    });

    grid.appendChild(card);
  });
}
// 초기 호출은 07-sidebar-modes.js 뷰 토글 클릭 시에 수행 (TDZ 방어)
// CEP뷰 · 서브그룹 안 키워드 클릭 위임
document.getElementById('cep-grid').addEventListener('click', (ev) => {
  const item = ev.target.closest('.cep-kw-item');
  if (!item) return;
  const kwEl = item.querySelector('.kw');
  if (kwEl) { try { openKeywordDetail(kwEl.getAttribute('title')); } catch(e) { console.error(e); } }
});

