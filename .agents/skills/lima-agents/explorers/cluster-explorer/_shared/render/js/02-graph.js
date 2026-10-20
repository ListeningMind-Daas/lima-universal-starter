const links = CLUSTER_DATA.rels
  .filter(r => nodeIndex.has(r[0]) && nodeIndex.has(r[1]))
  .map(r => ({ source: r[0], target: r[1] }));

// force simulation · 클러스터끼리 오밀조밀 뭉치고 · 클러스터 간 잘 분리되도록
const W = width(), H = height();

// 각 클러스터별 중심 좌표 · 클러스터 크기 반영해서 큰 클러스터는 가장자리 배치 (겹침 방지)
const clusterIds = Object.keys(CLUSTER_DATA.communities);
const clusterCenters = {};

// 크기 순 정렬 · 큰 클러스터부터 배치
const sortedByClusterSize = clusterIds
  .map(cid => ({ cid, size: (CLUSTER_DATA.communities[cid] || []).length }))
  .sort((a, b) => b.size - a.size);

const ringRadius = Math.min(W, H) * 0.42;  // 반경 확대 · 클러스터 간 분리
sortedByClusterSize.forEach((item, i) => {
  const angle = (i / clusterIds.length) * 2 * Math.PI - Math.PI / 2;
  clusterCenters[item.cid] = {
    x: W / 2 + Math.cos(angle) * ringRadius,
    y: H / 2 + Math.sin(angle) * ringRadius
  };
});

const simulation = d3.forceSimulation(nodes)
  .force('link', d3.forceLink(links).id(d => d.id).distance(18).strength(0.5))
  .force('charge', d3.forceManyBody().strength(-8))
  .force('collide', d3.forceCollide().radius(d => d.radius + 1.5).strength(0.9))
  // 클러스터 중력 · 강도 대폭 상승 · 각 클러스터가 자기 자리에 강하게 뭉침
  .force('clusterX', d3.forceX(d => (clusterCenters[d.community] || {x: W/2}).x).strength(0.35))
  .force('clusterY', d3.forceY(d => (clusterCenters[d.community] || {y: H/2}).y).strength(0.35));

const g = svg.append('g');

const link = g.append('g')
  .attr('class', 'links')
  .selectAll('line')
  .data(links)
  .join('line')
  .attr('class', 'link');

const node = g.append('g')
  .attr('class', 'nodes')
  .selectAll('circle')
  .data(nodes)
  .join('circle')
  .attr('class', 'node')
  .attr('r', d => d.radius)
  .attr('fill', d => d.isHub ? '#fff' : colorFor(d.community))
  .attr('stroke', d => d.isHub ? colorFor(d.community) : 'none')
  .attr('stroke-width', d => d.isHub ? 3 : 0)
  .on('mouseover', (event, d) => {
    tooltip
      .style('opacity', 1)
      .html(buildNodeTooltip(d))
      .style('left', (event.clientX + 12) + 'px')
      .style('top', (event.clientY + 12) + 'px');
  })
  .on('mousemove', (event) => {
    tooltip
      .style('left', (event.clientX + 12) + 'px')
      .style('top', (event.clientY + 12) + 'px');
  })
  .on('mouseout', () => tooltip.style('opacity', 0))
  .on('click', (event, d) => {
    event.stopPropagation();
    try { openKeywordDetail(d.id); } catch(e) { console.error('openKeywordDetail failed:', e); }
  })
  .call(d3.drag()
    .on('start', (event, d) => { if (!event.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
    .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
    .on('end', (event, d) => { if (!event.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; })
  );

// 모든 노드에 대해 라벨 미리 생성 · 초기엔 허브만 보이고 · 줌 배율에 따라 확장
const labels = g.append('g')
  .attr('class', 'labels')
  .selectAll('text')
  .data(nodes)
  .join('text')
  .attr('class', d => 'node-label' + (d.isHub ? ' hub' : ''))
  .text(d => d.id)
  .attr('text-anchor', 'start')          // 왼쪽 정렬 (노드 오른쪽 시작)
  .attr('dominant-baseline', 'middle')   // 세로 중앙
  .attr('dx', d => d.radius + 4)         // 노드 오른쪽 · 반경 + 4px
  .attr('dy', 0)                          // 정중앙
  .style('opacity', d => d.isHub ? 1 : 0);

simulation.on('tick', () => {
  link.attr('x1', d => d.source.x).attr('y1', d => d.source.y).attr('x2', d => d.target.x).attr('y2', d => d.target.y);
  node.attr('cx', d => d.x).attr('cy', d => d.y);
  labels.attr('x', d => d.x).attr('y', d => d.y);
});

// 줌 배율에 따라 라벨 표시 부드럽게 확장 · 볼륨 순위 기반 선형 컷오프
// 전체 노드를 볼륨 내림차순으로 정렬 · 각 노드의 순위 저장
const nodesByVolume = [...nodes].sort((a, b) => b.volume - a.volume);
const totalNodes = nodesByVolume.length;
const rankByKw = new Map(nodesByVolume.map((n, i) => [n.id, i]));

const zoomBehavior = d3.zoom().on('zoom', event => {
  g.attr('transform', event.transform);
  const k = event.transform.k;

  // 배율(k)에 따라 몇 %의 노드까지 라벨 노출할지 · 부드러운 곡선
  let showPercent;
  if (k <= 1) showPercent = 0.05;
  else if (k <= 5) showPercent = 0.05 + (k - 1) * 0.24;
  else showPercent = 1.0;
  const cutoffRank = Math.floor(totalNodes * showPercent);

  labels.style('opacity', d => {
    if (d.isHub) return 1;
    const rank = rankByKw.get(d.id) ?? totalNodes;
    if (rank >= cutoffRank) return 0;
    const fadeStart = cutoffRank * 0.8;
    if (rank < fadeStart) return 1;
    return 1 - (rank - fadeStart) / (cutoffRank - fadeStart);
  });

  // 라벨 크기 화면 기준 고정 · SVG scale k에 반비례로 font-size 축소
  const baseFont = 11;
  const hubFont = 12;
  labels.style('font-size', d => `${(d.isHub ? hubFont : baseFont) / k}px`);

  // 엣지도 화면상 얇게 유지 · stroke-width 역보정
  link.attr('stroke-width', 0.4 / k);
});
svg.call(zoomBehavior);

// 클러스터 칩 사이드바 · 알파벳 순 · 클릭 = 격리 모드
