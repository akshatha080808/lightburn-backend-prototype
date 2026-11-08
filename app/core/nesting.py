"""Greedy shelf-based nesting algorithm for material utilization.

This is a heuristic algorithm and does not guarantee globally optimal placement.
It uses a shelf-packing approach: shapes are sorted by height (descending) and
placed left-to-right on shelves that grow top-to-bottom.
"""
from typing import List, Optional
from pydantic import BaseModel, Field
from .geometry import GeometryEntity, BoundingBox, compute_bounding_box


class NestRequest(BaseModel):
    """Request model for nesting operation."""
    shapes: List[GeometryEntity]
    sheet_width: float = Field(gt=0, description="Sheet width in mm")
    sheet_height: float = Field(gt=0, description="Sheet height in mm")
    spacing: float = Field(ge=0, default=2.0, description="Spacing between shapes in mm")
    allow_rotation: bool = Field(default=True, description="Allow 90-degree rotation")
    margin: float = Field(ge=0, default=5.0, description="Sheet edge margin in mm")


class PlacedShape(BaseModel):
    """A shape that has been placed on the sheet."""
    shape_id: str
    x: float
    y: float
    width: float
    height: float
    rotated: bool
    bounding_box: BoundingBox


class NestResult(BaseModel):
    """Result of the nesting operation."""
    placed_shapes: List[PlacedShape]
    unplaced_shapes: List[str]
    utilization_percent: float
    sheet_width: float
    sheet_height: float
    algorithm: str = "greedy-shelf"


def _extract_shape_dimensions(entity: GeometryEntity) -> tuple[float, float]:
    """Extract width and height for a geometry entity.

    Uses bounding_box if present, otherwise computes from points or circle/ellipse geometry.
    """
    if entity.bounding_box is not None:
        if entity.bounding_box.width > 0 or entity.bounding_box.height > 0:
            return float(entity.bounding_box.width), float(entity.bounding_box.height)
    if entity.points:
        bb = compute_bounding_box(entity.points)
        return float(bb.width), float(bb.height)
    if entity.radius is not None and entity.radius > 0:
        diam = float(entity.radius * 2.0)
        return diam, diam
    if entity.rx is not None and entity.ry is not None:
        return float(entity.rx * 2.0), float(entity.ry * 2.0)
    return 0.0, 0.0


def nest_shapes(request: NestRequest) -> NestResult:
    """Nest geometry shapes onto a sheet using a greedy shelf-packing algorithm.

    Parameters:
        request: NestRequest with shapes, sheet dimensions, spacing, rotation option, and margins.

    Returns:
        NestResult with placed shape positions, unplaced shape IDs, and material utilization percentage.
    """
    if not request.shapes:
        return NestResult(
            placed_shapes=[],
            unplaced_shapes=[],
            utilization_percent=0.0,
            sheet_width=request.sheet_width,
            sheet_height=request.sheet_height,
            algorithm="greedy-shelf",
        )

    # 1. Compute bounding box width and height for each shape
    # 2. Create a list of (shape_id, width, height) tuples
    shapes_info = []
    for shape in request.shapes:
        w, h = _extract_shape_dimensions(shape)
        shapes_info.append((shape.id, w, h))

    # 3. Sort by height descending
    shapes_info.sort(key=lambda s: s[2], reverse=True)

    # Usable boundaries
    max_x = request.sheet_width - request.margin
    max_y = request.sheet_height - request.margin

    placed_shapes: List[PlacedShape] = []
    unplaced_shapes: List[str] = []

    # 5. Shelf packing
    current_x = request.margin
    current_y = request.margin
    shelf_height = 0.0

    for shape_id, w, h in shapes_info:
        # Orientations to test: (width, height, is_rotated)
        orientations = [(w, h, False)]
        if request.allow_rotation and abs(w - h) > 1e-6:
            orientations.append((h, w, True))

        # Check which orientations fit on the current shelf
        fits_current = []
        for opt_w, opt_h, is_rot in orientations:
            if current_x + opt_w <= max_x:
                eff_shelf_h = max(shelf_height, opt_h)
                if current_y + eff_shelf_h <= max_y:
                    waste = abs(shelf_height - opt_h) if shelf_height > 0 else opt_h
                    fits_current.append((waste, opt_w, opt_h, is_rot))

        if fits_current:
            # Pick orientation that wastes less vertical space on current shelf
            fits_current.sort(key=lambda item: (item[0], item[1]))
            _, chosen_w, chosen_h, chosen_rot = fits_current[0]

            placed = PlacedShape(
                shape_id=shape_id,
                x=current_x,
                y=current_y,
                width=chosen_w,
                height=chosen_h,
                rotated=chosen_rot,
                bounding_box=BoundingBox(
                    min_x=current_x,
                    min_y=current_y,
                    max_x=current_x + chosen_w,
                    max_y=current_y + chosen_h,
                    width=chosen_w,
                    height=chosen_h,
                ),
            )
            placed_shapes.append(placed)
            current_x += chosen_w + request.spacing
            shelf_height = max(shelf_height, chosen_h)

        elif shelf_height > 0:
            # Try on a new shelf
            new_y = current_y + shelf_height + request.spacing
            new_x = request.margin

            fits_new = []
            for opt_w, opt_h, is_rot in orientations:
                if new_x + opt_w <= max_x and new_y + opt_h <= max_y:
                    # Prefer smaller height to minimize new shelf height
                    fits_new.append((opt_h, opt_w, is_rot))

            if fits_new:
                fits_new.sort(key=lambda item: (item[0], item[1]))
                chosen_h, chosen_w, chosen_rot = fits_new[0]

                current_y = new_y
                current_x = new_x
                shelf_height = chosen_h

                placed = PlacedShape(
                    shape_id=shape_id,
                    x=current_x,
                    y=current_y,
                    width=chosen_w,
                    height=chosen_h,
                    rotated=chosen_rot,
                    bounding_box=BoundingBox(
                        min_x=current_x,
                        min_y=current_y,
                        max_x=current_x + chosen_w,
                        max_y=current_y + chosen_h,
                        width=chosen_w,
                        height=chosen_h,
                    ),
                )
                placed_shapes.append(placed)
                current_x += chosen_w + request.spacing
            else:
                unplaced_shapes.append(shape_id)
        else:
            # Even on an empty first shelf, shape does not fit
            unplaced_shapes.append(shape_id)

    # 6. Calculate utilization = (sum of placed shape areas) / (sheet_width * sheet_height) * 100
    sum_placed_areas = sum(shape.width * shape.height for shape in placed_shapes)
    total_area = request.sheet_width * request.sheet_height
    utilization_percent = (sum_placed_areas / total_area) * 100.0 if total_area > 0 else 0.0

    return NestResult(
        placed_shapes=placed_shapes,
        unplaced_shapes=unplaced_shapes,
        utilization_percent=round(utilization_percent, 2),
        sheet_width=request.sheet_width,
        sheet_height=request.sheet_height,
        algorithm="greedy-shelf",
    )
