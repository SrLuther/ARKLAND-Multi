"""RNG e algoritmo de sorteio / divisão de prêmio — spec v1.5/v1.6 MVP."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime, timezone
from typing import Any

ALGORITHM_VERSION = "arkland-mvp-v1"
NUMBER_MIN = 100
NUMBER_MAX = 999


def compute_prize_split(
    prize_amber_total: int,
    matched_count: int,
) -> dict[str, Any]:
    """Divisão do prêmio conforme §3.6.1 — divisor = matched_count, nunca W."""
    total = max(0, int(prize_amber_total))
    mc = max(0, int(matched_count))
    if mc == 0:
        rollover_out = (total * 125) // 100
        return {
            "share_per_match": 0,
            "prize_amber_paid": 0,
            "prize_amber_subsidy": 0,
            "rollover_out": rollover_out,
            "prize_pool_fully_distributed": False,
        }
    share = (total + mc - 1) // mc  # ceil(total / mc)
    paid = share * mc
    subsidy = paid - total
    return {
        "share_per_match": share,
        "prize_amber_paid": paid,
        "prize_amber_subsidy": subsidy,
        "rollover_out": 0,
        "prize_pool_fully_distributed": True,
    }


def draw_winning_numbers(
    winning_count: int,
    *,
    campaign_id: int,
    draw_at_iso: str,
    participant_count: int,
    numbers_issued_count: int,
) -> tuple[list[int], dict[str, Any]]:
    """
    MVP: secrets.SystemRandom.sample — audit blob com entropy snapshot.
    Fase 2 migrará para arkland-v1 commit-reveal (§12.1).
    """
    w = max(1, min(5, int(winning_count)))
    pool = list(range(NUMBER_MIN, NUMBER_MAX + 1))
    rng = secrets.SystemRandom()
    drawn = sorted(rng.sample(pool, w))
    entropy = os.urandom(32).hex()
    seed_material = (
        f"{campaign_id}|{draw_at_iso}|{participant_count}|"
        f"{numbers_issued_count}|{entropy}"
    )
    seed_hash = hashlib.sha256(seed_material.encode()).hexdigest()
    audit_blob: dict[str, Any] = {
        "algorithm_version": ALGORITHM_VERSION,
        "seed_hash": seed_hash,
        "entropy_snapshot": entropy,
        "winning_numbers_count": w,
        "drawn_at": datetime.now(timezone.utc).isoformat(),
        "method": "SystemRandom.sample",
    }
    return drawn, audit_blob


def audit_blob_json(audit_blob: dict[str, Any]) -> str:
    return json.dumps(audit_blob, ensure_ascii=False, separators=(",", ":"))
