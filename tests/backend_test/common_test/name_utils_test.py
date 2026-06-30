"""Unit tests for partner display-name resolution."""

from backend.common.name_utils import partner_display_name


def test_prefers_preferred_name_when_present():
    """When a preferred name is set, it is used verbatim."""
    assert (
        partner_display_name(
            first_name="Alice", last_name="Anderson", preferred_name="Ali"
        )
        == "Ali"
    )


def test_falls_back_to_full_name_when_preferred_name_is_none():
    """With no preferred name, the full 'first last' name is returned."""
    assert (
        partner_display_name(
            first_name="Alice", last_name="Anderson", preferred_name=None
        )
        == "Alice Anderson"
    )


def test_falls_back_to_full_name_when_preferred_name_is_empty():
    """An empty or whitespace preferred name is treated as absent."""
    assert (
        partner_display_name(
            first_name="Alice", last_name="Anderson", preferred_name="   "
        )
        == "Alice Anderson"
    )


def test_strips_surrounding_whitespace():
    """Returned names are trimmed of surrounding whitespace."""
    assert (
        partner_display_name(first_name="Alice", last_name=None, preferred_name=None)
        == "Alice"
    )
