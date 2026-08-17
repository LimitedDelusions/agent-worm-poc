from __future__ import annotations
from itertools import permutations
from .types import ROLES


def unique_placements(model_slots: list[str]) -> list[dict[str,str]]:
    """All 24 full four-role permutations (retained for future full-study expansion)."""
    if len(model_slots)!=4 or len(set(model_slots))!=4:
        raise ValueError("Need exactly four unique models")
    return [dict(zip(ROLES,p,strict=True)) for p in permutations(model_slots)]


def ordered_pair_assignments(model_slots: list[str]) -> list[dict[str,str]]:
    """Complete 4x4 intake->relay transmission matrix.

    Planner and executor mirror the tested pair because the POC terminates at relay.
    This avoids duplicate primary conditions disguised as unused downstream placements.
    """
    if len(model_slots)!=4 or len(set(model_slots))!=4:
        raise ValueError("Need exactly four unique models")
    return [
        {"intake":src,"relay":dst,"planner":src,"executor":dst}
        for src in model_slots for dst in model_slots
    ]


def homogeneous_placements(model_slots: list[str]) -> list[dict[str,str]]:
    return [{role:slot for role in ROLES} for slot in model_slots]


def placement_id(mapping: dict[str,str]) -> str:
    return "__".join(f"{role}-{mapping[role]}" for role in ROLES)


def pair_id(mapping: dict[str,str]) -> str:
    return f"intake-{mapping['intake']}__relay-{mapping['relay']}"


def balanced_shakedown(placements: list[dict[str,str]], count: int = 8) -> list[dict[str,str]]:
    """Legacy helper for future reduced shakedowns; current v0.8.7 uses all 16 pairs."""
    chosen=[];remaining=list(placements)
    role_counts={(r,m):0 for r in ROLES for m in {v for p in placements for v in p.values()}}
    pair_counts={}
    while remaining and len(chosen)<count:
        def score(p):
            imbalance=sum(role_counts[(r,p[r])] for r in ROLES)
            pair=(p['intake'],p['relay'])
            return (imbalance+2*pair_counts.get(pair,0),placement_id(p))
        best=min(remaining,key=score);chosen.append(best);remaining.remove(best)
        for r in ROLES:role_counts[(r,best[r])]+=1
        pair=(best['intake'],best['relay']);pair_counts[pair]=pair_counts.get(pair,0)+1
    return chosen
