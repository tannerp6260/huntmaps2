"""Validated mutation payloads; geometry and source checks remain in services."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt

Decision = Literal["unmarked", "keep", "reject", "needs inspection"]


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Review(Payload):
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)
    status: Decision = "needs inspection"
    notes: str = Field(default="", max_length=10000)
    name: str = Field(default="Nearby observer", min_length=1, max_length=100)


class Annotation(Payload):
    status: Decision
    notes: str = Field(default="", max_length=10000)


class Observer(Payload):
    observer_east_m: StrictFloat | StrictInt
    observer_north_m: StrictFloat | StrictInt


class Waypoint(Observer, Review):
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
    radius_m: Literal[500, 1000, 1500, 2000, 2500, 3000] = 2000
    observation_minutes: int = Field(default=30, ge=5, le=120)
    max_download_mb: int = Field(default=600, ge=1, le=1900)
    candidate_count: int = Field(default=150, ge=12, le=200)


class Start(Payload):
    download: StrictBool = False
