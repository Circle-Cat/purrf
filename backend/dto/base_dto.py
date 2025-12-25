from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class BaseDto(BaseModel):
    """
    Base DTO class with shared Pydantic configuration.

    - alias_generator: Automatically convert field names to camelCase.
    - populate_by_name: Allow initialization using Python field names.
    - from_attributes: Allow constructing models from object attributes
      (useful for ORM objects).
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )
