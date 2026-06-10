from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any
from enum import Enum


class Department(str, Enum):
    MAIL = "mail"
    REGULAR = "regular"
    HEAVY = "heavy"
    UNROUTED = "unrouted"


class Parcel(BaseModel):
    weight: float = Field(..., gt=0, description="Weight in kg (must be > 0)")
    value: float = Field(..., ge=0, description="Value in euros (must be >= 0)")
    destination: str = Field(..., min_length=2, max_length=100)
    extra: Optional[dict[str, Any]] = Field(default=None, description="Optional extra attributes")

    @field_validator("destination")
    @classmethod
    def destination_must_be_valid(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Destination cannot be empty")
        return cleaned.upper()


class RoutingResult(BaseModel):
    parcel: Parcel
    department: Department
    flags: list[str] = Field(default_factory=list)
    rules_matched: list[str] = Field(default_factory=list)
    requires_insurance: bool = False
    dispatch_allowed: bool = True
    message: str = ""
    ruleset_version: str = "unknown"


class BatchRoutingResult(BaseModel):
    total: int
    routed: int
    failed: int
    results: list[RoutingResult]
    errors: list[dict[str, Any]] = Field(default_factory=list)


class RuleSimulationRequest(BaseModel):
    parcels: list[Parcel] = Field(..., min_length=1, max_length=500)
    proposed_rules: Optional[dict[str, Any]] = None


class RuleDiffItem(BaseModel):
    parcel: Parcel
    current_department: Department
    proposed_department: Department
    current_flags: list[str] = Field(default_factory=list)
    proposed_flags: list[str] = Field(default_factory=list)
    changed: bool = False


class RuleSimulationResponse(BaseModel):
    current_ruleset_version: str
    proposed_ruleset_version: str
    total_parcels: int
    changed_routes: int
    changed_flags: int
    diffs: list[RuleDiffItem]