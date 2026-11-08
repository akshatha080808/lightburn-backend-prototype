"""DXF processor module for extracting geometry from DXF files using ezdxf."""
import math
import os
import tempfile
from typing import List, Optional

import ezdxf

from app.core.geometry import (
    BoundingBox,
    GeometryCollection,
    GeometryEntity,
    Point,
    compute_bounding_box,
    compute_collection_bounding_box,
)


def process_dxf(file_content: bytes, filename: str) -> GeometryCollection:
    """Parse DXF file content and extract 2D geometry entities.

    Args:
        file_content: Raw bytes of the DXF file.
        filename: Original filename.

    Returns:
        GeometryCollection containing parsed entities and bounding box in mm.
    """
    if isinstance(file_content, str):
        file_content = file_content.encode("utf-8")

    entities: List[GeometryEntity] = []
    warnings: List[str] = []
    temp_path: Optional[str] = None

    try:
        # Write content to a temporary file for ezdxf to read
        with tempfile.NamedTemporaryFile(suffix=".dxf", mode="wb", delete=False) as tmp:
            tmp.write(file_content)
            temp_path = tmp.name

        try:
            doc = ezdxf.readfile(temp_path)
            msp = doc.modelspace()
        except Exception as dxf_err:
            warnings.append(f"Failed to read DXF file {filename}: {str(dxf_err)}")
            return GeometryCollection(
                entities=[],
                total_count=0,
                bounding_box=None,
                source_file=filename,
                source_format="dxf",
                warnings=warnings,
            )

        for entity in msp:
            dxftype = entity.dxftype()

            try:
                if dxftype == "LINE":
                    start = entity.dxf.start
                    end = entity.dxf.end
                    line_points = [
                        Point(x=float(start.x), y=float(start.y)),
                        Point(x=float(end.x), y=float(end.y)),
                    ]
                    entities.append(
                        GeometryEntity(
                            entity_type="line",
                            points=line_points,
                            is_closed=False,
                            bounding_box=compute_bounding_box(line_points),
                            original_units="mm",
                        )
                    )

                elif dxftype == "LWPOLYLINE":
                    raw_points = entity.get_points(format="xy")
                    points = [Point(x=float(p[0]), y=float(p[1])) for p in raw_points]
                    if not points:
                        warnings.append("Skipped LWPOLYLINE with no points")
                        continue

                    is_closed = bool(getattr(entity, "closed", False))
                    entities.append(
                        GeometryEntity(
                            entity_type="polyline",
                            points=points,
                            is_closed=is_closed,
                            bounding_box=compute_bounding_box(points),
                            original_units="mm",
                        )
                    )

                elif dxftype == "POLYLINE":
                    raw_points = list(entity.points())
                    points: List[Point] = []
                    for p in raw_points:
                        if hasattr(p, "x"):
                            points.append(Point(x=float(p.x), y=float(p.y)))
                        else:
                            points.append(Point(x=float(p[0]), y=float(p[1])))

                    if not points:
                        warnings.append("Skipped POLYLINE with no points")
                        continue

                    is_closed = bool(getattr(entity, "is_closed", False))
                    entities.append(
                        GeometryEntity(
                            entity_type="polyline",
                            points=points,
                            is_closed=is_closed,
                            bounding_box=compute_bounding_box(points),
                            original_units="mm",
                        )
                    )

                elif dxftype == "CIRCLE":
                    center_vec = entity.dxf.center
                    radius = float(entity.dxf.radius)
                    center = Point(x=float(center_vec.x), y=float(center_vec.y))

                    num_segments = 36
                    circle_points: List[Point] = []
                    for i in range(num_segments):
                        angle = 2 * math.pi * i / num_segments
                        circle_points.append(
                            Point(
                                x=center.x + radius * math.cos(angle),
                                y=center.y + radius * math.sin(angle),
                            )
                        )

                    entities.append(
                        GeometryEntity(
                            entity_type="circle",
                            points=circle_points,
                            is_closed=True,
                            bounding_box=compute_bounding_box(circle_points),
                            original_units="mm",
                            center=center,
                            radius=radius,
                        )
                    )

                elif dxftype == "ARC":
                    center_vec = entity.dxf.center
                    radius = float(entity.dxf.radius)
                    start_angle = float(entity.dxf.start_angle)
                    end_angle = float(entity.dxf.end_angle)
                    center = Point(x=float(center_vec.x), y=float(center_vec.y))

                    start_rad = math.radians(start_angle)
                    end_rad = math.radians(end_angle)
                    if end_rad <= start_rad:
                        end_rad += 2 * math.pi

                    num_segments = 36
                    arc_points: List[Point] = []
                    for i in range(num_segments + 1):
                        angle = start_rad + (end_rad - start_rad) * i / num_segments
                        arc_points.append(
                            Point(
                                x=center.x + radius * math.cos(angle),
                                y=center.y + radius * math.sin(angle),
                            )
                        )

                    entities.append(
                        GeometryEntity(
                            entity_type="arc",
                            points=arc_points,
                            is_closed=False,
                            bounding_box=compute_bounding_box(arc_points),
                            original_units="mm",
                            center=center,
                            radius=radius,
                            start_angle=start_angle,
                            end_angle=end_angle,
                        )
                    )

                else:
                    warnings.append(f"Unsupported DXF entity type skipped: {dxftype}")

            except Exception as entity_err:
                warnings.append(f"Error processing {dxftype} entity: {str(entity_err)}")

    except Exception as e:
        warnings.append(f"Unexpected error processing DXF: {str(e)}")
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

    collection_bbox = compute_collection_bounding_box(entities)

    return GeometryCollection(
        entities=entities,
        total_count=len(entities),
        bounding_box=collection_bbox,
        source_file=filename,
        source_format="dxf",
        warnings=warnings,
    )
