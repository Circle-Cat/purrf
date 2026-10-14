"""Unit tests for user display-name resolution."""

from unittest import TestCase, main

from backend.common.name_utils import (
    display_name_of,
    display_name_or_id,
    user_display_name,
)


class UserDisplayNameTest(TestCase):
    def test_prefers_preferred_name_when_present(self):
        """When a preferred name is set, it is used verbatim."""
        assert (
            user_display_name(
                first_name="Alice", last_name="Anderson", preferred_name="Ali"
            )
            == "Ali"
        )

    def test_falls_back_to_full_name_when_preferred_name_is_none(self):
        """With no preferred name, the full 'first last' name is returned."""
        assert (
            user_display_name(
                first_name="Alice", last_name="Anderson", preferred_name=None
            )
            == "Alice Anderson"
        )

    def test_falls_back_to_full_name_when_preferred_name_is_empty(self):
        """An empty or whitespace preferred name is treated as absent."""
        assert (
            user_display_name(
                first_name="Alice", last_name="Anderson", preferred_name="   "
            )
            == "Alice Anderson"
        )

    def test_strips_surrounding_whitespace(self):
        """Returned names are trimmed of surrounding whitespace."""
        assert (
            user_display_name(first_name="Alice", last_name=None, preferred_name=None)
            == "Alice"
        )


class DisplayNameOfTest(TestCase):
    class _Row:
        def __init__(self, first_name, last_name, preferred_name):
            self.first_name = first_name
            self.last_name = last_name
            self.preferred_name = preferred_name

    def test_reads_the_three_name_attributes_off_the_row(self):
        """The convenience form applies the same rule to a users row."""
        assert display_name_of(self._Row("Alice", "Anderson", "Ali")) == "Ali"

    def test_falls_back_to_the_full_name(self):
        """A row with no preferred name resolves to 'first last'."""
        assert display_name_of(self._Row("Alice", "Anderson", None)) == "Alice Anderson"

    def test_returns_empty_string_for_a_missing_row(self):
        """Callers pass None when the users row could not be loaded."""
        assert display_name_of(None) == ""


class DisplayNameOrIdTest(TestCase):
    class _Row:
        def __init__(self, user_id, first_name, last_name, preferred_name=None):
            self.user_id = user_id
            self.first_name = first_name
            self.last_name = last_name
            self.preferred_name = preferred_name

    def test_returns_the_display_name_when_there_is_one(self):
        assert display_name_or_id(self._Row(270, "Alice", "Anderson", "Ali")) == "Ali"

    def test_falls_back_to_the_user_id_for_a_nameless_row(self):
        """An email-code sign-in creates the account with empty names."""
        assert display_name_or_id(self._Row(270, "", "")) == "User 270"

    def test_whitespace_only_names_count_as_no_name(self):
        assert display_name_or_id(self._Row(270, " ", " ", " ")) == "User 270"


if __name__ == "__main__":
    main()
