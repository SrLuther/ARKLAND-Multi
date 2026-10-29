"""Semantic models for independent ARK player and dino level progressions.

The models keep the values shown by the editor explicit. INI parsing and UI
widgets can adapt to these types without sharing mutable state or guessing how
the two ARK ramp keys relate to one another.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class PlayerLevel:
    level: int
    xp_required: int
    engram_points: int = 0


@dataclass
class DinoLevel:
    level: int
    xp_required: int


def _validate_rows(rows: Iterable[PlayerLevel | DinoLevel]) -> list[str]:
    errors: list[str] = []
    previous_level: int | None = None
    previous_xp: int | None = None
    seen: set[int] = set()
    for row in rows:
        if row.level < 1:
            errors.append(f"level {row.level}: level must be positive")
        if row.level in seen:
            errors.append(f"level {row.level}: duplicate level")
        seen.add(row.level)
        if row.xp_required < 0:
            errors.append(f"level {row.level}: XP must not be negative")
        if isinstance(row, PlayerLevel) and row.engram_points < 0:
            errors.append(f"level {row.level}: engram points must not be negative")
        if previous_level is not None and row.level <= previous_level:
            errors.append("levels must be in ascending order")
        if previous_xp is not None and row.xp_required < previous_xp:
            errors.append("XP thresholds must be non-decreasing")
        previous_level = row.level
        previous_xp = row.xp_required
    return errors


@dataclass
class PlayerProgression:
    """Player table values; engram totals are derived, never stored separately."""

    enabled: bool = False
    max_xp: int = 0
    levels: list[PlayerLevel] = field(default_factory=list)

    def engram_total_before(self, level: int) -> int:
        return sum(row.engram_points for row in self.levels if row.level < level)

    def validate(self) -> list[str]:
        errors = _validate_rows(self.levels)
        if self.max_xp < 0:
            errors.append("maximum XP must not be negative")
        if self.levels and self.max_xp and self.max_xp < self.levels[-1].xp_required:
            errors.append("maximum XP is below the final level threshold")
        return errors

    @classmethod
    def from_thresholds(
        cls,
        xp_thresholds: Iterable[int],
        engram_points: Iterable[int],
        *,
        first_level: int = 1,
        enabled: bool = False,
        max_xp: int = 0,
    ) -> "PlayerProgression":
        xp = list(xp_thresholds)
        points = list(engram_points)
        if len(xp) != len(points):
            raise ValueError("XP and engram progression lengths must match")
        model = cls(
            enabled=enabled,
            max_xp=max_xp,
            levels=[
                PlayerLevel(first_level + index, int(threshold), int(points[index]))
                for index, threshold in enumerate(xp)
            ],
        )
        errors = model.validate()
        if errors:
            raise ValueError("; ".join(errors))
        return model


@dataclass
class DinoProgression:
    """Dino table values, isolated from player progression and engram state."""

    enabled: bool = False
    max_xp: int = 0
    levels: list[DinoLevel] = field(default_factory=list)

    def validate(self) -> list[str]:
        errors = _validate_rows(self.levels)
        if self.max_xp < 0:
            errors.append("maximum XP must not be negative")
        if self.levels and self.max_xp and self.max_xp < self.levels[-1].xp_required:
            errors.append("maximum XP is below the final level threshold")
        return errors

    @classmethod
    def from_thresholds(
        cls,
        xp_thresholds: Iterable[int],
        *,
        first_level: int = 1,
        enabled: bool = False,
        max_xp: int = 0,
    ) -> "DinoProgression":
        model = cls(
            enabled=enabled,
            max_xp=max_xp,
            levels=[
                DinoLevel(first_level + index, int(threshold))
                for index, threshold in enumerate(xp_thresholds)
            ],
        )
        errors = model.validate()
        if errors:
            raise ValueError("; ".join(errors))
        return model
