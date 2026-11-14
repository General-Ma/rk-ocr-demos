"""Validate transient extraction data returned by the browser for auditing."""
from typing import Annotated, Literal
from pydantic import BaseModel, Field

Text = Annotated[str, Field(max_length=2000)]
Coordinate = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Box = tuple[Coordinate, Coordinate, Coordinate, Coordinate]


class ExtractedField(BaseModel):
    text: Text = ''
    value: Text | None = None
    confidence: Coordinate | None = None
    uncertain: bool = False
    bbox: Box | None = None
    location_kind: Literal['expected', 'detected', 'form'] = 'expected'


class Reading(BaseModel):
    page: int = Field(ge=1, le=12)
    local_page: int = Field(ge=1, le=12)
    document_name: Text
    time: Text | None = None
    time_text: Text = ''
    minutes: int | None = Field(default=None, ge=0, lt=1440)
    slot_offset: int | None = Field(default=None, ge=0, lt=1440)
    bbox: Box
    fields: dict[Literal['performed','systolic','diastolic','heart_rate','temperature','weight','significant'], ExtractedField]


class Document(BaseModel):
    name: Annotated[str, Field(max_length=255)]
    readings: list[Reading] = Field(max_length=64)


class AuditInput(BaseModel):
    documents: list[Document] = Field(min_length=1, max_length=10)
