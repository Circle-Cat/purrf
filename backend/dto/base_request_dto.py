from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class BaseRequestDto(BaseModel):
    """
    Base DTO class for API requests.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    def to_db_dict(self) -> dict:
        return self.model_dump(
            mode="json",
            by_alias=False,
            exclude_unset=True,
        )
