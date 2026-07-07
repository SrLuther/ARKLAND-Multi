"""Testes do contexto de banco na aba SQL do DB Manager."""
from __future__ import annotations

from src.pages.db_manager_panel import (
    _effective_sql_database,
    _resolve_sql_target_database,
    _sql_looks_like_read,
)


def test_effective_sql_database_prefers_selected_table_db():
    assert _effective_sql_database("ark_permission", "arkland_shop", "arkland_shop") == "ark_permission"


def test_effective_sql_database_falls_back_to_connection_field():
    assert _effective_sql_database("", "arkland_shop", "") == "arkland_shop"


def test_effective_sql_database_falls_back_to_state_database():
    assert _effective_sql_database("", "", "arkland_shop") == "arkland_shop"


def test_effective_sql_database_default():
    assert _effective_sql_database("", "", "") == "arkland_shop"


def test_sql_looks_like_read():
    assert _sql_looks_like_read("SELECT 1")
    assert _sql_looks_like_read("  show tables")
    assert _sql_looks_like_read("WITH x AS (SELECT 1) SELECT * FROM x")
    assert not _sql_looks_like_read("UPDATE orders SET status='PENDENTE'")


def test_resolve_sql_target_database_orders_force_shop_db():
    sql = (
        "UPDATE orders SET status='PENDENTE', last_error='Reset manual' "
        "WHERE order_id='cd_461234484528';"
    )
    assert _resolve_sql_target_database(
        sql, "ark_permission", "ark_permission", "ark_permission",
    ) == "arkland_shop"


def test_resolve_sql_target_database_keeps_explicit_qualifier():
    sql = "SELECT * FROM ark_permission.players LIMIT 5;"
    assert _resolve_sql_target_database(
        sql, "arkland_shop", "arkland_shop", "arkland_shop",
    ) == "arkland_shop"
