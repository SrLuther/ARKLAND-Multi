"""Testes — galeria visual Encomenda de Dino."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dino_order_showcase_service import (
    MAX_SHOWCASES_PER_SPECIES,
    configure_dino_order_showcase,
    count_showcases_for_species,
    create_showcase,
    delete_showcase,
    is_species_orderable,
    list_showcases,
    update_showcase,
)


@pytest.fixture
def showcase_store(tmp_path):
    configure_dino_order_showcase(
        showcases_file=tmp_path / "showcases.json",
        uploads_dir=tmp_path / "uploads",
    )
    yield tmp_path


def _entry(species_key="rex", color_name="Vermelho", **kwargs):
    body = {
        "species_key": species_key,
        "color_name": color_name,
        "colors": [14, 14, 14, 0, 0, 0],
        "description": "Rex vermelho teste",
        "regions_label": "Corpo",
        "image_url": "https://example.com/rex.jpg",
        "active": True,
    }
    body.update(kwargs)
    return body


def test_create_and_list_showcases(showcase_store):
    created = create_showcase(_entry())
    assert created["id"].startswith("sc_")
    items = list_showcases(species_key="rex")
    assert len(items) == 1
    assert items[0]["color_name"] == "Vermelho"
    assert is_species_orderable("rex") is True
    assert is_species_orderable("giga") is False


def test_max_ten_per_species(showcase_store):
    for i in range(MAX_SHOWCASES_PER_SPECIES):
        create_showcase(_entry(color_name=f"Cor {i}"))
    assert count_showcases_for_species("rex") == MAX_SHOWCASES_PER_SPECIES
    with pytest.raises(ValueError, match="showcase_limit_reached"):
        create_showcase(_entry(color_name="Extra"))


def test_inactive_not_orderable(showcase_store):
    entry = create_showcase(_entry(active=False))
    assert is_species_orderable("rex") is False
    update_showcase(entry["id"], {"active": True})
    assert is_species_orderable("rex") is True


def test_delete_showcase(showcase_store):
    entry = create_showcase(_entry())
    delete_showcase(entry["id"])
    assert list_showcases(species_key="rex") == []
    assert is_species_orderable("rex") is False
