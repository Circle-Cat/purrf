from dataclasses import dataclass

from sqlalchemy import Select


@dataclass(frozen=True)
class UserIdCondition:
    """Keep only the people a single-column user_id query returns, or with
    ``exclude`` leave them out."""

    query: Select
    exclude: bool = False

    def applied_to(self, column):
        return column.not_in(self.query) if self.exclude else column.in_(self.query)
