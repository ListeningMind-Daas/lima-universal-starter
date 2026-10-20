let isolatedCid = null;  // 현재 격리된 클러스터 · null이면 전체
const chipsContainer = document.getElementById('cluster-chips');
const isolatedBadge = document.getElementById('isolated-badge');

const sortedClusters = Object.entries(clusterLabels).sort((a, b) => (a[1].letter || 'Z').localeCompare(b[1].letter || 'Z'));

function applyIsolation() {
  if (isolatedCid === null) {
    // 전체 보기
    node.style('opacity', 1);
    link.style('opacity', 0.4);
    labels.style('opacity', 1);
    isolatedBadge.style.display = 'none';
    // 시뮬레이션 원위치
    simulation.force('center', d3.forceCenter(width() / 2, height() / 2));
    simulation.alpha(0.3).restart();
    // svg zoom 리셋
    svg.transition().duration(500).call(zoomBehavior.transform, d3.zoomIdentity);
  } else {
    // 특정 클러스터만
    node.style('opacity', d => d.community === isolatedCid ? 1 : 0.05);
    link.style('opacity', d => {
      const sc = nodeIndex.get(d.source.id).community;
      const tc = nodeIndex.get(d.target.id).community;
      return (sc === isolatedCid && tc === isolatedCid) ? 0.6 : 0.02;
    });
    labels.style('opacity', d => d.community === isolatedCid ? 1 : 0.05);
    isolatedBadge.style.display = 'block';
    const info = clusterLabels[isolatedCid];
    isolatedBadge.textContent = `← ${info?.letter || ''} ${info?.name || ''} · 전체 보기`;

    // 격리 클러스터의 노드 위치 평균 · 줌 인
    const isolatedNodes = nodes.filter(n => n.community === isolatedCid);
    if (isolatedNodes.length > 0) {
      const xs = isolatedNodes.map(n => n.x || 0);
      const ys = isolatedNodes.map(n => n.y || 0);
      const cx = xs.reduce((a, b) => a + b, 0) / xs.length;
      const cy = ys.reduce((a, b) => a + b, 0) / ys.length;
      const W = width(), H = height();
      const scale = 2.2;
      const tx = W / 2 - cx * scale;
      const ty = H / 2 - cy * scale;
      svg.transition().duration(600)
        .call(zoomBehavior.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
    }
  }
  // 칩 활성/비활성 표시
  document.querySelectorAll('.cluster-chip').forEach(c => {
    if (isolatedCid === null) {
      c.classList.remove('disabled');
    } else {
      c.classList.toggle('disabled', c.dataset.cid !== isolatedCid);
    }
  });
  // 카드뷰도 반영
  try { renderCardView(); } catch(e) {}
}

sortedClusters.forEach(([cid, info]) => {
  const color = colorFor(cid);
  const chip = document.createElement('div');
  chip.className = 'cluster-chip';
  chip.dataset.cid = cid;
  chip.style.color = color;
  chip.style.borderColor = color + '80';
  chip.title = info.name;
  chip.innerHTML = `
    <span class="letter" style="color: ${color};">${info.letter}</span>
    <span class="cluster-name">${info.name}</span>
  `;
  chip.onclick = () => {
    // 같은 클러스터 클릭 or 이미 격리 상태 = 전체 복귀
    isolatedCid = (isolatedCid === cid) ? null : cid;
    applyIsolation();
  };
  chipsContainer.appendChild(chip);
});

isolatedBadge.onclick = () => { isolatedCid = null; applyIsolation(); };

// 허브 필터 토글
let hubOnly = false;
const hubToggle = document.getElementById('hub-toggle');
hubToggle.onclick = () => {
  hubOnly = !hubOnly;
  hubToggle.classList.toggle('active', hubOnly);
  applyHubFilter();
  renderKwList(document.getElementById('kw-search').value);
};

function applyHubFilter() {
  if (hubOnly) {
    // 허브만 남김 · 나머지 매우 흐리게
    node.style('opacity', d => d.isHub ? 1 : 0.03);
    link.style('opacity', d => {
      const sn = nodeIndex.get(d.source.id);
      const tn = nodeIndex.get(d.target.id);
      return (sn.isHub && tn.isHub) ? 0.5 : 0.02;
    });
    labels.style('opacity', d => d.isHub ? 1 : 0);
  } else {
    // 전체 복귀 (격리 모드가 아닐 때)
    if (isolatedCid === null) {
      node.style('opacity', 1);
      link.style('opacity', 0.4);
      labels.style('opacity', d => d.isHub ? 1 : 0);
    } else {
      applyIsolation();
    }
  }
}

// 전체 키워드 목록 + 검색 + 허브 필터 반영
const kwList = document.getElementById('kw-list');
const kwCount = document.getElementById('kw-count');
const sortedNodes = [...nodes].sort((a, b) => b.volume - a.volume);
function renderKwList(filter = '') {
  kwList.innerHTML = '';
  let pool = sortedNodes;
  if (hubOnly) pool = pool.filter(n => n.isHub);
  // 공용 필터 (볼륨·트렌드) 통과 노드만
  pool = pool.filter(n => nodePassesFilter(n.id, n.volume));
  // 사이드바가 인텐트 모드이고 · 선택된 인텐트가 있으면 · 그 인텐트의 노드만
  if (sideMode === 'intent' && intentActive.size > 0) {
    pool = pool.filter(n => {
      const dom = getDominantIntent(n.id);
      return dom && intentActive.has(dom);
    });
  }
  // 트렌드 모드이고 · 선택된 카테고리 있으면 · 그 트렌드 노드만
  if (sideMode === 'trend' && trendActive.size > 0) {
    pool = pool.filter(n => {
      const cat = getTrendCat(n.id);
      return cat && trendActive.has(cat);
    });
  }
  // SERP 모드이고 · 선택된 타입 있으면 · 그 타입에 속한 노드만
  if (sideMode === 'serp' && serpActive.size > 0) {
    pool = pool.filter(n => {
      const types = getSerpTypes(n.id) || [];
      return types.some(t => serpActive.has(t));
    });
  }
  // 유저특성 모드이고 · 선택된 세그먼트 있으면
  if (sideMode === 'user' && userActive.size > 0) {
    pool = pool.filter(n => {
      const segs = getUserSegments(n.id) || [];
      return segs.some(s => userActive.has(s));
    });
  }
  // 상업성 모드이고 · 선택된 카테고리 있으면
  if (sideMode === 'commerce' && commerceActive.size > 0) {
    pool = pool.filter(n => {
      const cat = getCommerceCat(n.id);
      return cat && commerceActive.has(cat);
    });
  }
  const filtered = pool.filter(n => n.id.toLowerCase().includes(filter.toLowerCase()));
  kwCount.textContent = filtered.length;
  filtered.slice(0, 300).forEach(n => {
    const div = document.createElement('div');
    div.className = 'kw-item' + (n.isHub ? ' hub' : '');
    div.innerHTML = `<span>${n.id}</span><span class="vol">${(n.volume ?? 0).toLocaleString()}</span>`;
    div.onclick = () => {
      node.attr('stroke', d => d.id === n.id ? '#e63946' : (d.isHub ? colorFor(d.community) : 'none'))
          .attr('stroke-width', d => d.id === n.id ? 4 : (d.isHub ? 3 : 0));
      try { openKeywordDetail(n.id); } catch(e) { console.error('openKeywordDetail failed:', e); }
    };
    kwList.appendChild(div);
  });
}
try { renderKwList(); } catch(e) { console.error('renderKwList failed:', e); }
document.getElementById('kw-search').addEventListener('input', e => renderKwList(e.target.value));

