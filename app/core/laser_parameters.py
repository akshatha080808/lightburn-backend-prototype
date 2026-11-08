"""Laser parameter configuration and validation."""
from typing import List, Optional
from pydantic import BaseModel, Field


class LaserLayer(BaseModel):
    """Settings for a single laser layer."""
    name: str = Field(description="Layer name")
    speed_mm_min: float = Field(ge=1, le=60000, default=1000, description="Speed in mm/min")
    power_percent: float = Field(ge=0, le=100, default=50, description="Laser power percentage")
    passes: int = Field(ge=1, le=100, default=1, description="Number of passes")
    frequency: Optional[float] = Field(ge=0, default=None, description="Laser frequency in Hz")


class LaserConfig(BaseModel):
    """Complete laser configuration."""
    layers: List[LaserLayer]
    max_s_value: float = Field(ge=1, default=1000, description="Maximum S value for GRBL")


class LaserConfigRequest(BaseModel):
    """Request model for creating/validating laser configuration."""
    layers: List[LaserLayer]
    max_s_value: float = Field(ge=1, default=1000)


def create_laser_config(request: LaserConfigRequest) -> LaserConfig:
    """Create and validate a LaserConfig from a LaserConfigRequest.

    Parameters:
        request: LaserConfigRequest with layer configurations and max S value.

    Returns:
        LaserConfig instance.

    Raises:
        ValueError: If the layers list is empty.
    """
    if not request.layers:
        raise ValueError("At least one laser layer must be specified in the configuration.")

    return LaserConfig(
        layers=request.layers,
        max_s_value=request.max_s_value,
    )


def get_default_config() -> LaserConfig:
    """Return a default laser configuration with a single layer named 'default'."""
    return LaserConfig(
        layers=[
            LaserLayer(
                name="default",
                speed_mm_min=1000.0,
                power_percent=50.0,
                passes=1,
            )
        ],
        max_s_value=1000.0,
    )
