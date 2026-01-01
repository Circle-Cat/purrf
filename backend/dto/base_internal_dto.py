from pydantic import BaseModel, ConfigDict


class BaseInternalDTO(BaseModel):
    """Base DTO for internal logic with flexible configuration and attribute-based loading."""

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)
