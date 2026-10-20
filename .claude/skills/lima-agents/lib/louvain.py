"""Pure-Python Louvain community detection (standard library only).

Implements the Louvain method for modularity maximization on undirected,
unweighted (or weighted) graphs. Returns {node_id: community_label}.

Reference: Blondel et al. 2008. "Fast unfolding of communities in large networks."

Why pure Python: Claude Desktop runs user-machine bash with default python3,
no pip access. NetworkX/python-louvain aren't available without install.

Performance: handles ~5k nodes / ~30k edges in a few seconds. For the
cluster-finder use case (1~2k nodes typically) this is plenty.

API:
    louvain(edges, weights=None, resolution=1.0, seed=42) -> dict[node, comm_id]

    edges: list of (u, v) tuples. Undirected. Self-loops allowed.
    weights: optional list of float weights, same length as edges. Default = 1.
    resolution: γ in modularity (>1 → more communities, <1 → fewer).
    seed: random seed for deterministic node iteration order.
"""

from __future__ import annotations

import random
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


def _build_adj(edges: Sequence[Tuple], weights: Optional[Sequence[float]] = None):
    """Build adjacency dict: {node: {neighbor: total_weight}}.
    Parallel edges between same node pair are summed.
    """
    if weights is None:
        weights = [1.0] * len(edges)
    adj: Dict[object, Dict[object, float]] = defaultdict(lambda: defaultdict(float))
    for (u, v), w in zip(edges, weights):
        if u == v:
            # self-loop: add to its own weight twice (standard Louvain treats
            # self-loops as contributing 2*w to node's degree)
            adj[u][u] += 2.0 * w
        else:
            adj[u][v] += w
            adj[v][u] += w
    # Convert inner defaultdict to plain dict for stable iteration
    return {n: dict(nbrs) for n, nbrs in adj.items()}


def _node_degree(adj: Dict[object, Dict[object, float]]) -> Dict[object, float]:
    return {n: sum(w for w in nbrs.values()) for n, nbrs in adj.items()}


def _modularity(adj, partition, two_m, resolution):
    """Compute modularity Q of a partition.
    Q = (1/2m) Σ_ij [A_ij - γ * k_i*k_j / 2m] * δ(c_i, c_j)
    """
    if two_m == 0:
        return 0.0
    deg = _node_degree(adj)
    # group by community
    comm_nodes: Dict[object, List[object]] = defaultdict(list)
    for n, c in partition.items():
        comm_nodes[c].append(n)
    q = 0.0
    for c, nodes in comm_nodes.items():
        node_set = set(nodes)
        # sum of edge weights inside community (each undirected edge counted twice)
        in_w = 0.0
        for n in nodes:
            for nb, w in adj[n].items():
                if nb in node_set:
                    in_w += w
        # in_w currently double-counts each internal edge (and self-loops counted twice already)
        # The modularity formula's first term is in_w / 2m (using directed sum convention).
        # Sum of degrees of community
        sum_deg = sum(deg[n] for n in nodes)
        q += (in_w / two_m) - resolution * (sum_deg / two_m) ** 2
    return q


def _one_level(adj, partition, two_m, resolution, rng):
    """Local-moving phase. Repeatedly move nodes to neighboring community
    that yields the highest modularity gain, until no improvement.
    Returns True if at least one node moved.
    """
    deg = _node_degree(adj)
    # sum of degrees per community
    sum_deg_comm: Dict[object, float] = defaultdict(float)
    for n, c in partition.items():
        sum_deg_comm[c] += deg[n]

    nodes = list(adj.keys())
    rng.shuffle(nodes)
    moved_any = False
    changed = True
    while changed:
        changed = False
        for n in nodes:
            cur_comm = partition[n]
            n_deg = deg[n]
            # weight from n to each neighboring community
            comm_w: Dict[object, float] = defaultdict(float)
            for nb, w in adj[n].items():
                if nb == n:
                    continue
                comm_w[partition[nb]] += w
            # remove n from its current community for gain calculation
            sum_deg_comm[cur_comm] -= n_deg
            # current "contribution" baseline = 0 (we just compute Δ for moving n to candidate)
            # gain of moving n to community c:
            #   Δ = (k_{n,c} / m) - γ * Σ_tot[c] * k_n / (2m^2)
            # where k_{n,c} = total weight from n to nodes in c (NOT including n)
            #       Σ_tot[c] = sum of degrees of nodes in c (after removing n)
            best_comm = cur_comm
            best_gain = 0.0  # must beat staying put (which is 0 since we removed n)
            # consider staying baseline (going back to cur_comm), and each neighbor's comm
            candidate_comms = set(comm_w.keys())
            candidate_comms.add(cur_comm)
            two_m_sq = two_m  # used as denominator below as (2m)
            for c in candidate_comms:
                k_nc = comm_w.get(c, 0.0)
                gain = (k_nc / two_m_sq) - resolution * (sum_deg_comm[c] * n_deg) / (two_m_sq * two_m_sq)
                if gain > best_gain + 1e-12:
                    best_gain = gain
                    best_comm = c
            # apply
            sum_deg_comm[best_comm] += n_deg
            if best_comm != cur_comm:
                partition[n] = best_comm
                changed = True
                moved_any = True
    return moved_any


def _aggregate(adj, partition):
    """Build induced (super-)graph where each node is a community.
    Returns (new_adj, mapping_from_old_node_to_super_node)
    Internal edges sum to a self-loop on the super-node.
    """
    super_adj: Dict[object, Dict[object, float]] = defaultdict(lambda: defaultdict(float))
    for u, nbrs in adj.items():
        cu = partition[u]
        for v, w in nbrs.items():
            cv = partition[v]
            # we will end up summing each undirected edge twice (u->v and v->u),
            # so halve here? Actually adj[u][v] == adj[v][u] (we built symmetric),
            # so when we iterate both directions, we double the edge weight.
            # → divide by 2 to compensate, but self-loops in original (u==v) already
            # represent 2*w, halving still works.
            super_adj[cu][cv] += w / 2.0 if cu != cv else w / 2.0
    # Above is symmetric-equivalent; both cases /2. Actually self-loops in original
    # adj[u][u] = 2*w (per build_adj); aggregated they should remain 2*w_total.
    # The /2 above halves that to w_total which is wrong for self-loops. Fix:
    # rebuild correctly using explicit edge list pass instead.
    # → Use a cleaner direct approach below; reset and rebuild.
    super_adj = defaultdict(lambda: defaultdict(float))
    seen_pairs = set()
    for u, nbrs in adj.items():
        cu = partition[u]
        for v, w in nbrs.items():
            cv = partition[v]
            if u == v:
                # original self-loop with weight = 2*orig_w → keep as is
                super_adj[cu][cu] += w
            else:
                # add each undirected pair once
                key = (id(u) if id(u) < id(v) else id(v), id(v) if id(u) < id(v) else id(u))
                # safer: use sorted by their hash
                pair = tuple(sorted([repr(u), repr(v)]))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                if cu == cv:
                    super_adj[cu][cu] += 2.0 * w  # contribute as self-loop with 2w
                else:
                    super_adj[cu][cv] += w
                    super_adj[cv][cu] += w
    return {n: dict(nbrs) for n, nbrs in super_adj.items()}


def louvain(
    edges: Sequence[Tuple],
    weights: Optional[Sequence[float]] = None,
    resolution: float = 1.0,
    seed: int = 42,
    max_levels: int = 20,
    min_modularity_gain: float = 1e-6,
) -> Dict[object, int]:
    """Run Louvain community detection.

    Returns {original_node: integer_community_label_0..k-1}.
    Community labels are arbitrary positive ints.
    """
    rng = random.Random(seed)

    if not edges:
        return {}

    adj = _build_adj(edges, weights)
    # initial partition: each node in its own community
    partition = {n: n for n in adj.keys()}
    # total weight (2m)
    two_m = sum(d for nbrs in adj.values() for d in nbrs.values())
    if two_m == 0:
        return {n: 0 for n in adj}

    # Map each original node to a label that gets refined level-by-level
    original_to_label: Dict[object, object] = {n: n for n in adj}

    q_prev = _modularity(adj, partition, two_m, resolution)

    for _level in range(max_levels):
        moved = _one_level(adj, partition, two_m, resolution, rng)
        if not moved:
            break
        # update original_to_label: each original node's label = partition[its current label]
        original_to_label = {
            orig: partition[lab] for orig, lab in original_to_label.items()
        }
        # aggregate
        new_adj = _aggregate(adj, partition)
        adj = new_adj
        # new partition: each super-node in its own community
        partition = {n: n for n in adj.keys()}
        new_two_m = sum(d for nbrs in adj.values() for d in nbrs.values())
        if new_two_m == 0:
            break
        two_m = new_two_m
        q_new = _modularity(adj, partition, two_m, resolution)
        if q_new - q_prev < min_modularity_gain:
            break
        q_prev = q_new

    # Normalize labels to 0..k-1
    unique = {}
    out: Dict[object, int] = {}
    for orig, lab in original_to_label.items():
        if lab not in unique:
            unique[lab] = len(unique)
        out[orig] = unique[lab]
    return out


# ─────────────────────────────────────────
# CLI helper for quick test
# ─────────────────────────────────────────

if __name__ == "__main__":
    import json
    import sys

    # Read edges JSON from stdin (list of [u, v])
    edges_raw = json.load(sys.stdin)
    edges = [tuple(e) for e in edges_raw]
    parts = louvain(edges)
    n_comm = len(set(parts.values()))
    print(f"nodes: {len(parts)}, communities: {n_comm}", file=sys.stderr)
    print(json.dumps(parts, ensure_ascii=False))
