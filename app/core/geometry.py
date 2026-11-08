"""Core geometry data models for the LightBurn backend prototype."""
import uuid
from typing import List, Optional
from pydantic import BaseModel, Field


class Point(BaseModel):
    """A 2D point."""
    x: float
    y: float


class BoundingBox(BaseModel):
    """Axis-aligned bounding box."""
    min_x: float
    min_y: float
    max_x: float
    max_y: float
    width: float
    height: float


class GeometryEntity(BaseModel):
    """A single geometry entity extracted from an imported file."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    entity_type: str  # "line", "polyline", "circle", "arc", "path", "rectangle", "ellipse", "polygon"
    points: List[Point] = []
    is_closed: bool = False
    bounding_box: Optional[BoundingBox] = None
    original_units: str = "mm"
    # Circle/arc specific
    center: Optional[Point] = None
    radius: Optional[float] = None
    start_angle: Optional[float] = None
    end_angle: Optional[float] = None
    # Ellipse specific
    rx: Optional[float] = None
    ry: Optional[float] = None


class GeometryCollection(BaseModel):
    """Collection of geometry entities from a single file import."""
    entities: List[GeometryEntity]
    total_count: int
    bounding_box: Optional[BoundingBox] = None
    source_file: str
    source_format: str
    warnings: List[str] = []


def compute_bounding_box(points: List[Point]) -> BoundingBox:
    """Compute an axis-aligned bounding box from a list of points."""
    if not points:
        return BoundingBox(min_x=0, min_y=0, max_x=0, max_y=0, width=0, height=0)
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    return BoundingBox(
        min_x=min_x, min_y=min_y,
        max_x=max_x, max_y=max_y,
        width=max_x - min_x, height=max_y - min_y
    )


def compute_collection_bounding_box(entities: List[GeometryEntity]) -> Optional[BoundingBox]:
    """Compute the overall bounding box for a collection of entities."""
    all_points = []
    for entity in entities:
        all_points.extend(entity.points)
        if entity.center and entity.radius:
            # Include circle/arc extents
            c = entity.center
            r = entity.radius
            all_points.extend([
                Point(x=c.x - r, y=c.y - r),
                Point(x=c.x + r, y=c.y + r)
            ])
    if not all_points:
        return None
    return compute_bounding_box(all_points)
