"""GRBL-style G-code generation.

Generates G-code for laser operations. This is a simulation/preview tool only.
It never transmits commands to physical laser hardware.
"""
import math
from typing import List, Optional
from pydantic import BaseModel, Field
from .geometry import GeometryEntity, Point
from .laser_parameters import LaserConfig, LaserLayer


class GCodeRequest(BaseModel):
    """Request model for G-code generation."""
    entities: List[GeometryEntity]
    laser_config: LaserConfig
    selected_layer: str = Field(default="default", description="Layer name to use")


class ToolpathSegment(BaseModel):
    """A single segment of the toolpath preview."""
    segment_type: str  # "rapid" or "cut"
    start: Point
    end: Point


class GCodeResult(BaseModel):
    """Result of G-code generation."""
    gcode: str
    line_count: int
    estimated_duration_seconds: Optional[float] = None
    toolpath_preview: List[ToolpathSegment]
    warnings: List[str] = []


def _format_coord(val: float) -> str:
    """Format coordinate floating point value cleanly without exponential notation."""
    formatted = f"{val:.3f}".rstrip("0").rstrip(".")
    if formatted in ("", "-0"):
        return "0"
    return formatted


def generate_gcode(request: GCodeRequest) -> GCodeResult:
    """Generate GRBL-compatible G-code and preview toolpath segments for entities.

    Parameters:
        request: GCodeRequest containing entities, laser_config, and selected_layer.

    Returns:
        GCodeResult with full G-code text, line count, duration estimate, toolpaths, and warnings.
    """
    warnings: List[str] = []

    # 1. Find the selected layer in laser_config.layers (by name). If not found, use first layer.
    if not request.laser_config.layers:
        layer = LaserLayer(name="default", speed_mm_min=1000.0, power_percent=50.0, passes=1)
        warnings.append("No layers found in laser config; using default layer settings.")
    else:
        found_layer = next((l for l in request.laser_config.layers if l.name == request.selected_layer), None)
        if found_layer is not None:
            layer = found_layer
        else:
            layer = request.laser_config.layers[0]
            warnings.append(
                f"Layer '{request.selected_layer}' not found in laser configuration; using layer '{layer.name}'."
            )

    # 2. Compute S value = (power_percent / 100) * max_s_value
    raw_s = (layer.power_percent / 100.0) * request.laser_config.max_s_value
    s_val = round(raw_s, 2)
    s_val_str = str(int(s_val)) if s_val == int(s_val) else f"{s_val:.2f}".rstrip("0").rstrip(".")

    speed = layer.speed_mm_min
    speed_str = str(int(speed)) if speed == int(speed) else f"{speed:.2f}".rstrip("0").rstrip(".")

    # 3. Build G-code lines (Header)
    gcode_lines: List[str] = [
        "; =========================================",
        "; LightBurn-inspired Laser G-Code Preview",
        f"; Layer: {layer.name}",
        f"; Speed: {speed_str} mm/min",
        f"; Laser Power: {layer.power_percent}% (S{s_val_str})",
        f"; Passes: {layer.passes}",
        f"; Total Entities: {len(request.entities)}",
        "; =========================================",
        "G90",
        "G21",
        "G0 X0 Y0",
        "M5",
    ]

    toolpath_preview: List[ToolpathSegment] = []
    current_pos = Point(x=0.0, y=0.0)

    if not request.entities:
        warnings.append("Entity list is empty; generated G-code contains only preamble and postamble.")

    # 4. For each entity, for each pass
    for entity in request.entities:
        for pass_num in range(1, layer.passes + 1):
            pts: List[Point] = []
            is_closed = entity.is_closed

            if entity.points and len(entity.points) > 0:
                pts = entity.points
            elif entity.center is not None and entity.radius is not None and entity.radius > 0:
                # Approximate circle with 36 line segments
                num_segments = 36
                pts = []
                for i in range(num_segments):
                    angle = 2.0 * math.pi * i / num_segments
                    x = entity.center.x + entity.radius * math.cos(angle)
                    y = entity.center.y + entity.radius * math.sin(angle)
                    pts.append(Point(x=x, y=y))
                is_closed = True
            else:
                if pass_num == 1:
                    warnings.append(
                        f"Entity '{entity.id}' ({entity.entity_type}) has no points or circular geometry; skipped."
                    )
                continue

            if not pts:
                continue

            gcode_lines.append(f"; Entity {entity.id} - Pass {pass_num}/{layer.passes}")
            first = pts[0]

            # Rapid move to start
            gcode_lines.append(f"G0 X{_format_coord(first.x)} Y{_format_coord(first.y)}")
            toolpath_preview.append(
                ToolpathSegment(
                    segment_type="rapid",
                    start=Point(x=current_pos.x, y=current_pos.y),
                    end=Point(x=first.x, y=first.y),
                )
            )
            current_pos = Point(x=first.x, y=first.y)

            # Laser on
            gcode_lines.append(f"M3 S{s_val_str}")

            # Subsequent points
            for p in pts[1:]:
                gcode_lines.append(f"G1 X{_format_coord(p.x)} Y{_format_coord(p.y)} F{speed_str}")
                toolpath_preview.append(
                    ToolpathSegment(
                        segment_type="cut",
                        start=Point(x=current_pos.x, y=current_pos.y),
                        end=Point(x=p.x, y=p.y),
                    )
                )
                current_pos = Point(x=p.x, y=p.y)

            # If is_closed and len(points) > 2: close path
            if is_closed and len(pts) > 2:
                if abs(current_pos.x - first.x) > 1e-6 or abs(current_pos.y - first.y) > 1e-6:
                    gcode_lines.append(f"G1 X{_format_coord(first.x)} Y{_format_coord(first.y)} F{speed_str}")
                    toolpath_preview.append(
                        ToolpathSegment(
                            segment_type="cut",
                            start=Point(x=current_pos.x, y=current_pos.y),
                            end=Point(x=first.x, y=first.y),
                        )
                    )
                    current_pos = Point(x=first.x, y=first.y)

            # Laser off
            gcode_lines.append("M5")

    # 5. Footer
    gcode_lines.append("; Postamble")
    gcode_lines.append("M5")
    gcode_lines.append("G0 X0 Y0")

    # Add final rapid return to home if not already at home
    if abs(current_pos.x - 0.0) > 1e-6 or abs(current_pos.y - 0.0) > 1e-6:
        toolpath_preview.append(
            ToolpathSegment(
                segment_type="rapid",
                start=Point(x=current_pos.x, y=current_pos.y),
                end=Point(x=0.0, y=0.0),
            )
        )
        current_pos = Point(x=0.0, y=0.0)

    gcode_lines.append("M2")

    # 6 & 7. Estimate duration based on total distance / speed
    total_distance = sum(
        math.hypot(seg.end.x - seg.start.x, seg.end.y - seg.start.y)
        for seg in toolpath_preview
    )
    if speed > 0:
        estimated_duration_seconds = round((total_distance / speed) * 60.0, 2)
    else:
        estimated_duration_seconds = 0.0

    return GCodeResult(
        gcode="\n".join(gcode_lines),
        line_count=len(gcode_lines),
        estimated_duration_seconds=estimated_duration_seconds,
        toolpath_preview=toolpath_preview,
        warnings=warnings,
    )
