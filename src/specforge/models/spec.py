from __future__ import annotations
import math
from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator

FieldType = Literal["string", "integer", "number", "boolean", "object", "array", "null"]


class FieldSpec(BaseModel):
    model_config = {"extra": "forbid"}

    type: FieldType
    required: bool = False
    nullable: bool = True
    description: str | None = None

    # String
    minLength: int | None = Field(default=None, ge=0)
    maxLength: int | None = Field(default=None, ge=0)
    pattern: str | None = None
    format: str | None = None  # email, date, date-time

    # Numeric
    minimum: float | None = None
    maximum: float | None = None

    # Enum
    enum: list[Any] | None = None

    # Object
    fields: dict[str, FieldSpec] | None = None

    # Array
    items: FieldSpec | None = None
    minItems: int | None = Field(default=None, ge=0)
    maxItems: int | None = Field(default=None, ge=0)
    uniqueItems: bool = False

    @model_validator(mode="after")
    def _check_constraints(self) -> FieldSpec:
        if self.type == "object" and self.fields is None:
            raise ValueError("Field of type 'object' must define 'fields'")
        if self.minLength is not None and self.maxLength is not None:
            if self.minLength > self.maxLength:
                raise ValueError(f"minLength ({self.minLength}) must be <= maxLength ({self.maxLength})")
        for name, val in (("minimum", self.minimum), ("maximum", self.maximum)):
            if val is not None and not math.isfinite(val):
                raise ValueError(f"{name} must be a finite number, got {val}")
        if self.minimum is not None and self.maximum is not None:
            if self.minimum > self.maximum:
                raise ValueError(f"minimum ({self.minimum}) must be <= maximum ({self.maximum})")
        if self.minItems is not None and self.maxItems is not None:
            if self.minItems > self.maxItems:
                raise ValueError(f"minItems ({self.minItems}) must be <= maxItems ({self.maxItems})")
        return self


FieldSpec.model_rebuild()


class SpecFile(BaseModel):
    model_config = {"extra": "forbid"}

    type: Literal["object"] = "object"
    fields: dict[str, FieldSpec]
