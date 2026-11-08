"""SVG processor module for extracting geometry from SVG files."""
import math
import os
import re
import tempfile
from typing import List, Optional
import xml.etree.ElementTree as ET

from svgpathtools import Line, parse_path

from app.core.geometry import (
    BoundingBox,
    GeometryCollection,
    GeometryEntity,
    Point,
    compute_bounding_box,
    compute_collection_bounding_box,
)

# Standard SVG coordinate conversion factor (at 96 DPI: 1px = 25.4mm / 96 ≈ 0.2645833mm)
PX_TO_MM = 0.2645833


def _parse_float(val: Optional[str], default: float = 0.0) -> float:
    """Parse a float from an SVG attribute string, stripping units if present."""
    if val is None:
        return default
    match = re.search(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", val.strip())
    if match:
        try:
            return float(match.group(0))
        except ValueError:
            return default
    return default


def _parse_coordinate_pairs(points_str: str) -> List[Point]:
    """Parse coordinate pairs from SVG points attribute string."""
    raw_coords = re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", points_str)
    coords = [float(v) for v in raw_coords]
    points: List[Point] = []
    for i in range(0, len(coords) - 1, 2):
        x = coords[i] * PX_TO_MM
        y = coords[i + 1] * PX_TO_MM
        points.append(Point(x=x, y=y))
    return points


def process_svg(file_content: bytes, filename: str) -> GeometryCollection:
    """Parse SVG file content and extract 2D geometry entities.

    Args:
        file_content: Raw bytes of the SVG file.
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
        # Write content to a temporary file for processing and safe cleanup
        with tempfile.NamedTemporaryFile(suffix=".svg", mode="wb", delete=False) as tmp:
            tmp.write(file_content)
            temp_path = tmp.name

        try:
            tree = ET.parse(temp_path)
            root = tree.getroot()
        except ET.ParseError as pe:
            warnings.append(f"XML parse error in {filename}: {str(pe)}")
            return GeometryCollection(
                entities=[],
                total_count=0,
                bounding_box=None,
                source_file=filename,
                source_format="svg",
                warnings=warnings,
            )

        for elem in root.iter():
            tag = elem.tag.split("}")[-1].lower() if "}" in elem.tag else elem.tag.lower()

            try:
                if tag == "rect":
                    x = _parse_float(elem.get("x", "0")) * PX_TO_MM
                    y = _parse_float(elem.get("y", "0")) * PX_TO_MM
                    w = _parse_float(elem.get("width", "0")) * PX_TO_MM
                    h = _parse_float(elem.get("height", "0")) * PX_TO_MM

                    if w <= 0 or h <= 0:
                        warnings.append(f"Ignored rect with non-positive dimensions: width={w}, height={h}")
                        continue

                    rect_points = [
                        Point(x=x, y=y),
                        Point(x=x + w, y=y),
                        Point(x=x + w, y=y + h),
                        Point(x=x, y=y + h),
                    ]
                    entities.append(
                        GeometryEntity(
                            entity_type="rectangle",
                            points=rect_points,
                            is_closed=True,
                            bounding_box=compute_bounding_box(rect_points),
                            original_units="mm",
                        )
                    )

                elif tag == "circle":
                    cx = _parse_float(elem.get("cx", "0")) * PX_TO_MM
                    cy = _parse_float(elem.get("cy", "0")) * PX_TO_MM
                    r = _parse_float(elem.get("r", "0")) * PX_TO_MM

                    if r <= 0:
                        warnings.append(f"Ignored circle with non-positive radius: r={r}")
                        continue

                    num_segments = 36
                    circle_points: List[Point] = []
                    for i in range(num_segments):
                        angle = 2 * math.pi * i / num_segments
                        circle_points.append(
                            Point(
                                x=cx + r * math.cos(angle),
                                y=cy + r * math.sin(angle),
                            )
                        )

                    entities.append(
                        GeometryEntity(
                            entity_type="circle",
                            points=circle_points,
                            is_closed=True,
                            bounding_box=compute_bounding_box(circle_points),
                            original_units="mm",
                            center=Point(x=cx, y=cy),
                            radius=r,
                        )
                    )

                elif tag == "ellipse":
                    cx = _parse_float(elem.get("cx", "0")) * PX_TO_MM
                    cy = _parse_float(elem.get("cy", "0")) * PX_TO_MM
                    rx = _parse_float(elem.get("rx", "0")) * PX_TO_MM
                    ry = _parse_float(elem.get("ry", "0")) * PX_TO_MM

                    if rx <= 0 or ry <= 0:
                        warnings.append(f"Ignored ellipse with non-positive radii: rx={rx}, ry={ry}")
                        continue

                    num_segments = 36
                    ellipse_points: List[Point] = []
                    for i in range(num_segments):
                        angle = 2 * math.pi * i / num_segments
                        ellipse_points.append(
                            Point(
                                x=cx + rx * math.cos(angle),
                                y=cy + ry * math.sin(angle),
                            )
                        )

                    entities.append(
                        GeometryEntity(
                            entity_type="ellipse",
                            points=ellipse_points,
                            is_closed=True,
                            bounding_box=compute_bounding_box(ellipse_points),
                            original_units="mm",
                            center=Point(x=cx, y=cy),
                            rx=rx,
                            ry=ry,
                        )
                    )

                elif tag == "line":
                    x1 = _parse_float(elem.get("x1", "0")) * PX_TO_MM
                    y1 = _parse_float(elem.get("y1", "0")) * PX_TO_MM
                    x2 = _parse_float(elem.get("x2", "0")) * PX_TO_MM
                    y2 = _parse_float(elem.get("y2", "0")) * PX_TO_MM

                    line_points = [Point(x=x1, y=y1), Point(x=x2, y=y2)]
                    entities.append(
                        GeometryEntity(
                            entity_type="line",
                            points=line_points,
                            is_closed=False,
                            bounding_box=compute_bounding_box(line_points),
                            original_units="mm",
                        )
                    )

                elif tag == "polygon":
                    pts_attr = elem.get("points", "")
                    poly_points = _parse_coordinate_pairs(pts_attr)
                    if not poly_points:
                        warnings.append("Skipped polygon with no valid points")
                        continue

                    entities.append(
                        GeometryEntity(
                            entity_type="polygon",
                            points=poly_points,
                            is_closed=True,
                            bounding_box=compute_bounding_box(poly_points),
                            original_units="mm",
                        )
                    )

                elif tag == "polyline":
                    pts_attr = elem.get("points", "")
                    pline_points = _parse_coordinate_pairs(pts_attr)
                    if not pline_points:
                        warnings.append("Skipped polyline with no valid points")
                        continue

                    entities.append(
                        GeometryEntity(
                            entity_type="polyline",
                            points=pline_points,
                            is_closed=False,
                            bounding_box=compute_bounding_box(pline_points),
                            original_units="mm",
                        )
                    )

                elif tag == "path":
                    d_attr = elem.get("d", "").strip()
                    if not d_attr:
                        warnings.append("Skipped path with empty d attribute")
                        continue

                    try:
                        parsed_path = parse_path(d_attr)
                    except Exception as pe:
                        warnings.append(f"Failed to parse path: {str(pe)}")
                        continue

                    path_points: List[Point] = []
                    if len(parsed_path) > 0:
                        first_pt = parsed_path[0].start
                        path_points.append(
                            Point(
                                x=first_pt.real * PX_TO_MM,
                                y=first_pt.imag * PX_TO_MM,
                            )
                        )

                        for segment in parsed_path:
                            curr_start_x = segment.start.real * PX_TO_MM
                            curr_start_y = segment.start.imag * PX_TO_MM
                            if not (
                                math.isclose(path_points[-1].x, curr_start_x, abs_tol=1e-4)
                                and math.isclose(path_points[-1].y, curr_start_y, abs_tol=1e-4)
                            ):
                                path_points.append(Point(x=curr_start_x, y=curr_start_y))

                            is_line = (type(segment).__name__ == "Line") or isinstance(segment, Line)
                            if is_line:
                                path_points.append(
                                    Point(
                                        x=segment.end.real * PX_TO_MM,
                                        y=segment.end.imag * PX_TO_MM,
                                    )
                                )
                            else:
                                num_samples = 50
                                for i in range(1, num_samples + 1):
                                    pt = segment.point(i / float(num_samples))
                                    path_points.append(
                                        Point(
                                            x=pt.real * PX_TO_MM,
                                            y=pt.imag * PX_TO_MM,
                                        )
                                    )

                    is_closed = False
                    try:
                        is_closed = bool(parsed_path.isclosed())
                    except Exception:
                        pass
                    if not is_closed and d_attr:
                        is_closed = d_attr.strip().upper().endswith("Z")
                    if not is_closed and len(path_points) > 2:
                        if math.isclose(path_points[0].x, path_points[-1].x, abs_tol=1e-3) and math.isclose(
                            path_points[0].y, path_points[-1].y, abs_tol=1e-3
                        ):
                            is_closed = True

                    entities.append(
                        GeometryEntity(
                            entity_type="path",
                            points=path_points,
                            is_closed=is_closed,
                            bounding_box=compute_bounding_box(path_points),
                            original_units="mm",
                        )
                    )

            except Exception as elem_err:
                warnings.append(f"Failed to process <{tag}> element: {str(elem_err)}")

    except Exception as e:
        warnings.append(f"Unexpected error processing SVG: {str(e)}")
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
        source_format="svg",
        warnings=warnings,
    )
