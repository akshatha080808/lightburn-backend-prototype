"""Shape transformation operations using Shapely."""
import math
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator
from shapely.geometry import LineString, Point as ShapelyPoint, Polygon
from shapely.affinity import scale, rotate, translate
from .geometry import GeometryEntity, Point, BoundingBox, compute_bounding_box


class TransformRequest(BaseModel):
    """Request model for shape transformations."""
    entities: List[GeometryEntity]
    scale_x: float = Field(default=1.0, description="Scale factor along X axis")
    scale_y: float = Field(default=1.0, description="Scale factor along Y axis")
    rotation_degrees: float = Field(default=0.0, description="Rotation angle in degrees")
    translate_x: float = Field(default=0.0, description="Translation along X axis in mm")
    translate_y: float = Field(default=0.0, description="Translation along Y axis in mm")
    applied_transforms: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional dictionary containing transformation parameters (e.g. scale_x, scale_y, rotation_degrees, translate_x, translate_y)"
    )

    @model_validator(mode="before")
    @classmethod
    def extract_applied_transforms(cls, data: Any) -> Any:
        """Extract transform parameters from applied_transforms if provided."""
        if isinstance(data, dict):
            nested = data.get("applied_transforms")
            if isinstance(nested, dict):
                # If top-level transform parameters were not explicitly provided, unpack from nested dict
                for key in ("scale_x", "scale_y", "rotation_degrees", "translate_x", "translate_y"):
                    if key in nested and key not in data:
                        data[key] = nested[key]
        return data


class TransformResponse(BaseModel):
    """Response model for shape transformations."""
    entities: List[GeometryEntity]
    applied_transforms: dict


def apply_transformations(request: TransformRequest) -> TransformResponse:
    """Apply affine transformations (scale, rotate, translate) to a list of geometry entities.

    Parameters:
        request: TransformRequest containing the entities to transform and affine parameters.

    Returns:
        TransformResponse with transformed entities and a dictionary of applied transforms.
    """
    transformed_entities: List[GeometryEntity] = []

    for entity in request.entities:
        # Clone entity data so the original is not mutated
        new_entity = entity.model_copy(deep=True) if hasattr(entity, "model_copy") else entity.copy(deep=True)
        new_points: List[Point] = []

        if len(new_entity.points) == 1:
            geom = ShapelyPoint(new_entity.points[0].x, new_entity.points[0].y)
            geom = scale(geom, xfact=request.scale_x, yfact=request.scale_y, origin=(0, 0))
            geom = rotate(geom, angle=request.rotation_degrees, origin=(0, 0), use_radians=False)
            geom = translate(geom, xoff=request.translate_x, yoff=request.translate_y)
            new_points = [Point(x=geom.x, y=geom.y)]
        elif len(new_entity.points) >= 2:
            coords = [(p.x, p.y) for p in new_entity.points]
            if new_entity.is_closed and len(coords) >= 3:
                try:
                    geom = Polygon(coords)
                except Exception:
                    geom = LineString(coords)
            else:
                geom = LineString(coords)

            geom = scale(geom, xfact=request.scale_x, yfact=request.scale_y, origin=(0, 0))
            geom = rotate(geom, angle=request.rotation_degrees, origin=(0, 0), use_radians=False)
            geom = translate(geom, xoff=request.translate_x, yoff=request.translate_y)

            if geom.geom_type == "Polygon":
                poly_coords = list(geom.exterior.coords)
                # Polygon always appends the first coord to the end. If original did not, remove the added closure point.
                if len(new_entity.points) > 0 and len(poly_coords) == len(new_entity.points) + 1:
                    poly_coords = poly_coords[:-1]
                new_points = [Point(x=c[0], y=c[1]) for c in poly_coords]
            else:
                new_points = [Point(x=c[0], y=c[1]) for c in geom.coords]
        else:
            new_points = []

        new_entity.points = new_points

        # Transform center if present
        if new_entity.center is not None:
            c_geom = ShapelyPoint(new_entity.center.x, new_entity.center.y)
            c_geom = scale(c_geom, xfact=request.scale_x, yfact=request.scale_y, origin=(0, 0))
            c_geom = rotate(c_geom, angle=request.rotation_degrees, origin=(0, 0), use_radians=False)
            c_geom = translate(c_geom, xoff=request.translate_x, yoff=request.translate_y)
            new_entity.center = Point(x=c_geom.x, y=c_geom.y)

        # Scale radius if present
        if new_entity.radius is not None:
            scale_factor = (abs(request.scale_x) + abs(request.scale_y)) / 2.0
            new_entity.radius = new_entity.radius * scale_factor

        # Scale ellipse rx/ry if present
        if new_entity.rx is not None:
            new_entity.rx = new_entity.rx * abs(request.scale_x)
        if new_entity.ry is not None:
            new_entity.ry = new_entity.ry * abs(request.scale_y)

        # Shift angles for arcs
        if new_entity.start_angle is not None:
            new_entity.start_angle = (new_entity.start_angle + request.rotation_degrees) % 360.0
        if new_entity.end_angle is not None:
            new_entity.end_angle = (new_entity.end_angle + request.rotation_degrees) % 360.0

        # Recompute bounding box
        if new_entity.points:
            new_entity.bounding_box = compute_bounding_box(new_entity.points)
        elif new_entity.center is not None and new_entity.radius is not None:
            c = new_entity.center
            r = new_entity.radius
            new_entity.bounding_box = BoundingBox(
                min_x=c.x - r,
                min_y=c.y - r,
                max_x=c.x + r,
                max_y=c.y + r,
                width=2.0 * r,
                height=2.0 * r,
            )
        elif new_entity.center is not None and new_entity.rx is not None and new_entity.ry is not None:
            c = new_entity.center
            rx, ry = new_entity.rx, new_entity.ry
            new_entity.bounding_box = BoundingBox(
                min_x=c.x - rx,
                min_y=c.y - ry,
                max_x=c.x + rx,
                max_y=c.y + ry,
                width=2.0 * rx,
                height=2.0 * ry,
            )
        else:
            new_entity.bounding_box = None

        transformed_entities.append(new_entity)

    applied = {
        "scale_x": request.scale_x,
        "scale_y": request.scale_y,
        "rotation_degrees": request.rotation_degrees,
        "translate_x": request.translate_x,
        "translate_y": request.translate_y,
    }

    return TransformResponse(
        entities=transformed_entities,
        applied_transforms=applied,
    )
