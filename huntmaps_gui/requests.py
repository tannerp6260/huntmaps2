"""Validated mutation payloads; geometry and source checks remain in services."""

from typing import Literal
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    field_validator,
)

Decision = Literal["unmarked", "keep", "reject", "needs inspection"]


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Review(Payload):
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)
    status: Decision = "needs inspection"
    notes: str = Field(default="", max_length=10000)
    name: str = Field(default="Nearby observer", min_length=1, max_length=100)


class Annotation(Payload):
    revision: StrictInt = Field(default=0, ge=0)
    status: Decision
    notes: str = Field(default="", max_length=10000)


class Observer(Payload):
    observer_east_m: StrictFloat | StrictInt
    observer_north_m: StrictFloat | StrictInt


class Waypoint(Observer, Review):
    scene_key: str | None = None
    anchor: str | None = None


class Profile(Payload):
    east_m: StrictFloat | StrictInt
    north_m: StrictFloat | StrictInt
    eye_m: float = Field(default=1.7, ge=0.8, le=2.2)
    target_height_m: float = Field(default=0.8, ge=0, le=2.5)
    vegetation_scenario: Literal["sparse", "medium", "dense"] | None = None
    vegetation_radius_m: Literal[30, 60, 120] = 120
    observer_east_m: StrictFloat | StrictInt | None = None
    observer_north_m: StrictFloat | StrictInt | None = None


class Preparation(Payload):
    name: str = Field(
        min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$"
    )
    import_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    polygon: str | int
    radius_m: float = Field(default=1828.8, ge=457.2, le=3000)
    observation_minutes: int = Field(default=30, ge=5, le=120)
    max_download_mb: int = Field(default=600, ge=1)
    estimate_first: bool = True
    candidate_count: int = Field(default=150, ge=12, le=5000)
    recommendation_count: int = Field(default=20, ge=1, le=200)
    recommendation_separation_m: float = Field(default=150, ge=0, le=2000)
    nearby_radius_m: Literal[10, 30, 60, 120] = 30
    tree_threshold_percent: float = Field(default=10, ge=0, le=100)
    target_filters: dict | None = None
    habitat: dict | None = None
    avoid_dense_vegetation: StrictBool = False
    access_sampling: dict | None = None
    include_network: StrictBool = False
    unit_id: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    pack_version: str | None = Field(
        default=None, pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$"
    )

    @field_validator("habitat")
    @classmethod
    def habitat_settings(cls, value):
        if value is None:
            return None
        from .habitat import validate

        return validate(value)

    @field_validator("radius_m")
    @classmethod
    def radius_preset(cls, value):
        choices = [500, 1000, 1500, 2000, 2500, 3000]
        if not any(
            abs(value - x) < 1e-7 for x in choices + [x * 0.9144 for x in choices]
        ):
            raise ValueError("Choose a yard preset or a recorded legacy metre preset")
        return int(value) if float(value).is_integer() else value


class Start(Payload):
    review_signature: str | None = None
    download: StrictBool = False
