"""Testes de layout dos widgets TEK (índices de grid sem colisão)."""
from src.ui.server_field_widgets import (
    _logical_row_controls_grid,
    _logical_row_to_grid,
)


def test_logical_row_float_then_bool_no_grid_overlap():
    """Float em row N e bool em row N+1 não compartilham linha do grid."""
    float_row = 5
    bool_row = 6
    assert _logical_row_controls_grid(float_row) < _logical_row_to_grid(bool_row)


def test_logical_row_bool_then_float_no_grid_overlap():
    bool_row = 9
    float_row = 10
    assert _logical_row_to_grid(bool_row) < _logical_row_to_grid(float_row)


def test_logical_row_adjacent_floats_stack():
    """Dois floats consecutivos empilham rótulo+controle sem sobrepor."""
    a, b = 3, 4
    assert _logical_row_controls_grid(a) < _logical_row_to_grid(b)


def test_bool_grid_pair_shares_logical_row():
    """Dois bools no mesmo índice lógico (grade 2 colunas) usam a mesma linha."""
    logical = 2
    assert _logical_row_to_grid(logical) == _logical_row_to_grid(logical)
