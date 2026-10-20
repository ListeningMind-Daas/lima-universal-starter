// ==== 엔티티 상태 관리 (mutable) ====
const CATEGORIES = [
  { key: 'brands', icon: '🏷️', label: '브랜드', color: '#7c5ec4' },
  { key: 'ingredients', icon: '🧪', label: '성분/재료', color: '#5cb0a6' },
  { key: 'other', icon: '👤', label: '인물·기타', color: '#e8a765' },
];
const ORIGINAL_ENTITIES = CLUSTER_DATA.detected_entities
  ? JSON.parse(JSON.stringify(CLUSTER_DATA.detected_entities))
  : null;
let liveEntities = ORIGINAL_ENTITIES
  ? JSON.parse(JSON.stringify(ORIGINAL_ENTITIES))
  : null;
let actionHistory = []; // undo stack: each item = full snapshot before action
let snackTimer = null;

function findEntity(name) {
  if (!liveEntities) return null;
  for (const cat of CATEGORIES) {
    const arr = liveEntities[cat.key] || [];
    const idx = arr.findIndex(e => e.name === name);
    if (idx >= 0) return { cat: cat.key, idx, entity: arr[idx] };
  }
  return null;
}

function pushHistory() {
  actionHistory.push(JSON.parse(JSON.stringify(liveEntities)));
  if (actionHistory.length > 30) actionHistory.shift();
  updateUndoButton();
}

function updateUndoButton() {
  document.getElementById('undo-btn').disabled = actionHistory.length === 0;
}

function undo() {
  if (actionHistory.length === 0) return;
  liveEntities = actionHistory.pop();
  updateUndoButton();
  renderBrandsPanel();
  hideSnackbar();
}

function resetEntities() {
  if (!ORIGINAL_ENTITIES) return;
  pushHistory();
  liveEntities = JSON.parse(JSON.stringify(ORIGINAL_ENTITIES));
  renderBrandsPanel();
  showSnackbar('원본으로 리셋됨');
}

function showSnackbar(msg, undoable = false) {
  const bar = document.getElementById('snackbar');
  const msgEl = document.getElementById('snackbar-msg');
  const undoBtn = document.getElementById('snackbar-undo');
  msgEl.textContent = msg;
  undoBtn.style.display = undoable ? 'block' : 'none';
  bar.classList.add('show');
  if (snackTimer) clearTimeout(snackTimer);
  snackTimer = setTimeout(() => bar.classList.remove('show'), 5000);
}
function hideSnackbar() {
  const bar = document.getElementById('snackbar');
  bar.classList.remove('show');
  if (snackTimer) clearTimeout(snackTimer);
}

function removeEntity(name) {
  const found = findEntity(name);
  if (!found) return;
  pushHistory();
  liveEntities[found.cat].splice(found.idx, 1);
  renderBrandsPanel();
  showSnackbar(`"${name}" 제거됨`, true);
}

function mergeEntity(sourceName, targetName) {
  const src = findEntity(sourceName);
  const tgt = findEntity(targetName);
  if (!src || !tgt || sourceName === targetName) return;
  pushHistory();
  const source = src.entity;
  const target = tgt.entity;
  // 병합 · products 합치기 (중복 제거)
  const existingKws = new Set(target.products.map(p => p.keyword));
  source.products.forEach(p => {
    if (!existingKws.has(p.keyword)) target.products.push(p);
  });
  target.products.sort((a, b) => b.volume - a.volume);
  target.product_count = target.products.length;
  // sub_lines 추가
  if (!target.sub_lines) target.sub_lines = [];
  if (!target.sub_lines.includes(source.name)) target.sub_lines.push(source.name);
  if (source.sub_lines) {
    source.sub_lines.forEach(s => { if (!target.sub_lines.includes(s)) target.sub_lines.push(s); });
  }
  // 볼륨 합산
  target.brand_volume = (target.brand_volume || 0) + (source.brand_volume || 0);
  target.total_volume = (target.total_volume || 0) + (source.total_volume || 0);
  // 소스 제거
  liveEntities[src.cat].splice(src.idx, 1);
  // 카테고리 내 재정렬
  liveEntities[tgt.cat].sort((a, b) => b.total_volume - a.total_volume);
  renderBrandsPanel();
  showSnackbar(`"${sourceName}" → "${targetName}" 병합됨`, true);
}

function moveEntityToCategory(name, newCat) {
  const found = findEntity(name);
  if (!found || found.cat === newCat) return;
  pushHistory();
  const entity = liveEntities[found.cat].splice(found.idx, 1)[0];
  liveEntities[newCat].push(entity);
  liveEntities[newCat].sort((a, b) => b.total_volume - a.total_volume);
  renderBrandsPanel();
  const catLabel = CATEGORIES.find(c => c.key === newCat)?.label || newCat;
  showSnackbar(`"${name}" → ${catLabel}로 이동`, true);
}

// 카테고리 이동 모달 (⇢ 버튼)
function openMoveModal(sourceName) {
  const found = findEntity(sourceName);
  if (!found) return;
  const currentCat = found.cat;
  const modal = document.getElementById('merge-modal-bg');
  const list = document.getElementById('merge-list');
  const title = document.getElementById('merge-title');
  const sub = document.getElementById('merge-sub');
  title.textContent = '카테고리 이동';
  sub.textContent = `"${sourceName}" 을(를) 어느 카테고리로 옮길까요?`;
  list.innerHTML = '';
  CATEGORIES.forEach(cat => {
    if (cat.key === currentCat) return;  // 현재 카테고리는 제외
    const opt = document.createElement('div');
    opt.className = 'merge-option';
    opt.innerHTML = `
      <span class="merge-cat-tag" style="background: ${cat.color};">${cat.icon}</span>
      <span style="flex:1;">${cat.label}</span>
    `;
    opt.onclick = () => {
      moveEntityToCategory(sourceName, cat.key);
      modal.classList.remove('show');
    };
    list.appendChild(opt);
  });
  modal.classList.add('show');
}

// ==== 엔티티뷰 렌더링 · 카드 3개 (브랜드/성분/기타) · CEP 스타일 ====

// 카테고리별 아이콘 SVG (CEP 스타일)
const ENTITY_ICONS = {
  brands: `<svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>`,
  ingredients: `<svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2v7.31"/><path d="M14 9.3V2"/><path d="M8.5 2h7"/><path d="M14 9.3a6.5 6.5 0 1 1-4 0"/></svg>`,
  other: `<svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 4-6 8-6s8 2 8 6"/></svg>`
};
const ENTITY_META = {
  brands: { label: '브랜드', sub: '실제 제품·회사 브랜드', gradient: 'linear-gradient(135deg, #c9a8ee 0%, #8b5ec4 100%)', color: '#8b5ec4' },
  ingredients: { label: '성분/재료', sub: '재료·성분·규격', gradient: 'linear-gradient(135deg, #a3e0d4 0%, #5cb0a6 100%)', color: '#5cb0a6' },
  other: { label: '인물·기타', sub: '셀럽·모호·기타', gradient: 'linear-gradient(135deg, #ffd6a3 0%, #ffa870 100%)', color: '#e89f6a' }
};

function renderEntityView() {
  const grid = document.getElementById('entity-grid');
  if (!grid) return;
  grid.innerHTML = '';

  if (!liveEntities) {
    grid.innerHTML = '<div style="color:#888; font-size:13px;">엔티티 데이터 없음</div>';
    return;
  }

  const expandedItems = new Set(
    Array.from(document.querySelectorAll('.entity-item.expanded')).map(el => el.dataset.name)
  );

  CATEGORIES.forEach(cat => {
    const items = liveEntities[cat.key] || [];
    const meta = ENTITY_META[cat.key];
    if (!meta) return;

    const card = document.createElement('div');
    card.className = 'cep-card entity-cat';
    card.dataset.cat = cat.key;

    card.addEventListener('dragover', ev => { ev.preventDefault(); card.classList.add('drag-over'); });
    card.addEventListener('dragleave', () => card.classList.remove('drag-over'));
    card.addEventListener('drop', ev => {
      ev.preventDefault();
      card.classList.remove('drag-over');
      if (ev.target.closest('.entity-item')) return;
      const dragName = ev.dataTransfer.getData('text/entity-name');
      if (dragName) moveEntityToCategory(dragName, cat.key);
    });

    let entitiesHtml = '';
    items.forEach(e => {
      let productsHtml = '';
      const products = e.products || [];
      products.forEach(p => {
        // products 요소가 문자열이거나 객체 모두 대응
        const kw = typeof p === 'string' ? p : (p.keyword ?? '');
        const vol = typeof p === 'string' ? 0 : (p.volume ?? 0);
        productsHtml += `
          <div class="entity-product-item">
            <span class="kw" title="${kw}">${kw}</span>
            <span class="p-vol">${vol.toLocaleString()}</span>
          </div>`;
      });
      const subLinesText = (e.sub_lines && e.sub_lines.length > 0)
        ? ` · 하위 라인: ${e.sub_lines.join(', ')}` : '';
      const expClass = expandedItems.has(e.name) ? ' expanded' : '';
      const eVol = e.total_volume ?? e.brand_volume ?? 0;
      const productCount = e.product_count ?? products.length ?? 0;
      entitiesHtml += `
        <div class="entity-item${expClass}" data-name="${e.name}" draggable="true">
          <div class="entity-header">
            <span class="expand">▶</span>
            <span class="name" style="color: ${meta.color};">${e.name}</span>
            <span class="vol">${eVol.toLocaleString()}</span>
            <span class="entity-actions">
              <button class="ent-btn remove" title="제거">−</button>
              <button class="ent-btn move" title="다른 카테고리로 이동">⇢</button>
            </span>
          </div>
          <div class="entity-desc">${e.description ?? ''}${subLinesText}${productCount > 0 ? ' · 관련 ' + productCount + '개' : ''}</div>
          <div class="entity-products">${productsHtml || '<div style="color:#aaa; font-size:11px;">관련 키워드 없음</div>'}</div>
        </div>`;
    });

    card.innerHTML = `
      <div class="cep-header">
        <div class="cep-icon-wrap" style="background: ${meta.gradient};">
          ${ENTITY_ICONS[cat.key]}
        </div>
        <div class="label-wrap">
          <span class="label" style="color: ${meta.color};">${meta.label}</span>
          <span class="sub-label">${meta.sub}</span>
        </div>
      </div>
      <div class="cep-vol-total">
        <span>${items.length}개 엔티티 · 검색량</span>
        <span class="val">${items.reduce((s, e) => s + (e.total_volume ?? e.brand_volume ?? 0), 0).toLocaleString()}</span>
      </div>
      <div class="cep-subgroups">${entitiesHtml || '<div style="color:#aaa; font-size:12px; padding:8px; text-align:center;">여기로 drag&amp;drop하면 이 카테고리로 이동</div>'}</div>
    `;

    card.querySelectorAll('.entity-item').forEach(item => {
      const name = item.dataset.name;
      item.querySelector('.entity-header').onclick = (ev) => {
        if (ev.target.closest('.entity-actions')) return;
        item.classList.toggle('expanded');
      };
      item.querySelector('.ent-btn.remove').onclick = (ev) => { ev.stopPropagation(); removeEntity(name); };
      item.querySelector('.ent-btn.move').onclick = (ev) => { ev.stopPropagation(); openMoveModal(name); };

      item.addEventListener('dragstart', ev => {
        ev.dataTransfer.setData('text/entity-name', name);
        ev.dataTransfer.effectAllowed = 'move';
        item.classList.add('dragging');
      });
      item.addEventListener('dragend', () => item.classList.remove('dragging'));
      item.addEventListener('dragover', ev => {
        ev.preventDefault();
        ev.stopPropagation();
        if (ev.dataTransfer.types.includes('text/entity-name')) item.classList.add('drag-over');
      });
      item.addEventListener('dragleave', () => item.classList.remove('drag-over'));
      item.addEventListener('drop', ev => {
        ev.preventDefault();
        ev.stopPropagation();
        item.classList.remove('drag-over');
        const dragName = ev.dataTransfer.getData('text/entity-name');
        if (dragName && dragName !== name) mergeEntity(dragName, name);
      });
    });

    grid.appendChild(card);
  });
}

function renderBrandsPanel() { try { renderEntityView(); } catch(e) { console.error('renderEntityView failed:', e); } }
// 초기 호출은 07-sidebar-modes.js 뷰 토글 클릭 시에 수행 (TDZ 방어)
// 엔티티뷰 · 관련 키워드 클릭 위임
document.getElementById('entity-grid').addEventListener('click', (ev) => {
  const item = ev.target.closest('.entity-product-item');
  if (!item) return;
  const kwEl = item.querySelector('.kw');
  if (kwEl) { try { openKeywordDetail(kwEl.getAttribute('title')); } catch(e) { console.error(e); } }
});

document.getElementById('undo-btn').onclick = (ev) => { ev.stopPropagation(); undo(); };
document.getElementById('reset-btn').onclick = (ev) => { ev.stopPropagation(); resetEntities(); };
document.getElementById('snackbar-undo').onclick = () => undo();
document.getElementById('merge-cancel').onclick = () => document.getElementById('merge-modal-bg').classList.remove('show');
document.getElementById('merge-modal-bg').onclick = (ev) => {
  if (ev.target.id === 'merge-modal-bg') ev.currentTarget.classList.remove('show');
};
