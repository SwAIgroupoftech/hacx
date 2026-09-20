"""k alternate routes that avoid a blocked / congested segment.

Graph: nodes = road segments. An edge A→B exists when B starts where A ends,
the pair is not a U-turn, and turn_restrictions.csv does not forbid it.
Travel time uses the current speed (floored) so diversions prefer moving roads.
"""
from __future__ import annotations

import networkx as nx
import pandas as pd


def segment_graph(net: pd.DataFrame, turns: pd.DataFrame | None) -> nx.DiGraph:
    g = nx.DiGraph()
    net = net.copy()
    net["segment_id"] = net["segment_id"].astype(str)
    src = dict(zip(net["segment_id"], net["source_node"].astype(str)))
    tgt = dict(zip(net["segment_id"], net["target_node"].astype(str)))
    banned = set()
    if turns is not None and len(turns):
        for r in turns.itertuples():
            banned.add((str(r.from_segment), str(r.to_segment)))

    for s in net["segment_id"]:
        g.add_node(s, source=src[s], target=tgt[s])
    by_src: dict[str, list[str]] = {}
    for s in net["segment_id"]:
        by_src.setdefault(src[s], []).append(s)
    for a in net["segment_id"]:
        for b in by_src.get(tgt[a], []):
            if src[b] == tgt[a] and tgt[b] == src[a]:
                continue  # U-turn / reverse carriageway
            if (a, b) in banned:
                continue
            g.add_edge(a, b)
    return g


def travel_times(net: pd.DataFrame, speed: pd.Series, floor_kmh: float = 5.0) -> pd.Series:
    netx = net.set_index("segment_id")
    spd = speed.reindex(netx.index).fillna(netx["free_flow_speed_kmh"]).clip(lower=floor_kmh)
    return (netx["length_km"] / spd) * 60.0  # minutes


def alternate_routes(g: nx.DiGraph, blocked: str, times: pd.Series,
                     k: int = 3, max_util: float = 0.85, vc: pd.Series | None = None,
                     cap_gain_min: float = 3.0) -> list[dict]:
    """Paths from the blocked road's upstream feeders to its downstream successors,
    never using the blocked segment itself."""
    if blocked not in g:
        return []
    preds = list(g.predecessors(blocked))
    succs = list(g.successors(blocked))
    if not preds or not succs:
        # fall back: any path between the two node ends via other segments
        return []
    avoid = {blocked}
    if vc is not None:
        avoid |= set(vc[vc >= max_util].index.astype(str))
        avoid.discard(blocked)

    sub = g.copy()
    sub.remove_nodes_from([n for n in avoid if n in sub and n != blocked])
    if blocked in sub:
        sub.remove_node(blocked)
    for u, v in sub.edges():
        sub[u][v]["weight"] = float(times.get(v, 1.0))

    found: list[list[str]] = []
    for a in preds[:4]:
        for b in succs[:4]:
            if a not in sub or b not in sub:
                continue
            try:
                gen = nx.shortest_simple_paths(sub, a, b, weight="weight")
                for path in gen:
                    if path not in found:
                        found.append(path)
                    if len(found) >= k:
                        break
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue
            if len(found) >= k:
                break
        if len(found) >= k:
            break

    blocked_tt = float(times.get(blocked, 0.0))
    out = []
    for path in found[:k]:
        tt = float(sum(times.get(s, 0.0) for s in path))
        saving = blocked_tt - tt
        out.append({
            "via": path,
            "travel_min": round(tt, 2),
            "blocked_travel_min": round(blocked_tt, 2),
            "expected_saving_min": round(saving, 2),
            "usable": saving >= cap_gain_min or tt < blocked_tt,
        })
    return out
