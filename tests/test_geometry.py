"""Unit tests for core geometry, transformations, nesting, laser parameters, and G-code generation."""
import math
import pytest

from app.core.geometry import (
    Point,
    BoundingBox,
    GeometryEntity,
    compute_bounding_box,
    compute_collection_bounding_box,
)
from app.core.transformations import TransformRequest, apply_transformations
from app.core.nesting import NestRequest, nest_shapes
from app.core.laser_parameters import (
    LaserConfigRequest,
    LaserLayer,
    LaserConfig,
    create_laser_config,
    get_default_config,
)
from app.core.gcode_generator import GCodeRequest, generate_gcode


def test_compute_bounding_box():
    """Test compute_bounding_box with known points."""
    points = [
        Point(x=10.0, y=20.0),
        Point(x=-5.0, y=15.0),
        Point(x=30.0, y=-10.0),
        Point(x=0.0, y=0.0),
    ]
    bbox = compute_bounding_box(points)
    assert bbox is not None
    assert bbox.min_x == -5.0
    assert bbox.min_y == -10.0
    assert bbox.max_x == 30.0
    assert bbox.max_y == 20.0
    assert pytest.approx(bbox.width) == 35.0
    assert pytest.approx(bbox.height) == 30.0


def test_compute_bounding_box_empty():
    """Test compute_bounding_box with an empty list."""
    bbox = compute_bounding_box([])
    assert bbox is None or (bbox.width == 0.0 and bbox.height == 0.0)


def test_compute_collection_bounding_box():
    """Test compute_collection_bounding_box aggregating multiple entity bounding boxes."""
    entities = [
        GeometryEntity(
            id="e1",
            entity_type="rectangle",
            points=[Point(x=0.0, y=0.0), Point(x=10.0, y=10.0)],
            bounding_box=BoundingBox(
                min_x=0.0, min_y=0.0, max_x=10.0, max_y=10.0, width=10.0, height=10.0
            ),
        ),
        GeometryEntity(
            id="e2",
            entity_type="rectangle",
            points=[Point(x=5.0, y=5.0), Point(x=25.0, y=30.0)],
            bounding_box=BoundingBox(
                min_x=5.0, min_y=5.0, max_x=25.0, max_y=30.0, width=20.0, height=25.0
            ),
        ),
    ]
    col_bbox = compute_collection_bounding_box(entities)
    assert col_bbox is not None
    assert col_bbox.min_x == 0.0
    assert col_bbox.min_y == 0.0
    assert col_bbox.max_x == 25.0
    assert col_bbox.max_y == 30.0
    assert pytest.approx(col_bbox.width) == 25.0
    assert pytest.approx(col_bbox.height) == 30.0


def test_geometry_entity_creation():
    """Test creation and default fields of various geometry entity types."""
    # Rectangle entity
    rect = GeometryEntity(
        id="rect_1",
        entity_type="rectangle",
        points=[
            Point(x=0.0, y=0.0),
            Point(x=10.0, y=0.0),
            Point(x=10.0, y=10.0),
            Point(x=0.0, y=10.0),
        ],
        is_closed=True,
        bounding_box=BoundingBox(
            min_x=0.0, min_y=0.0, max_x=10.0, max_y=10.0, width=10.0, height=10.0
        ),
    )
    assert rect.id == "rect_1"
    assert rect.entity_type == "rectangle"
    assert len(rect.points) == 4
    assert rect.is_closed is True
    assert rect.original_units == "mm"

    # Circle entity
    circle = GeometryEntity(
        id="circ_1",
        entity_type="circle",
        center=Point(x=20.0, y=20.0),
        radius=10.0,
        is_closed=True,
        bounding_box=BoundingBox(
            min_x=10.0, min_y=10.0, max_x=30.0, max_y=30.0, width=20.0, height=20.0
        ),
    )
    assert circle.entity_type == "circle"
    assert circle.center.x == 20.0
    assert circle.radius == 10.0

    # Arc entity
    arc = GeometryEntity(
        id="arc_1",
        entity_type="arc",
        center=Point(x=0.0, y=0.0),
        radius=15.0,
        start_angle=0.0,
        end_angle=90.0,
        is_closed=False,
    )
    assert arc.entity_type == "arc"
    assert arc.start_angle == 0.0
    assert arc.end_angle == 90.0


def test_scale_transformation():
    """Test scaling a rectangle by 2x and verifying coordinates doubled."""
    rect = GeometryEntity(
        id="scale_rect",
        entity_type="rectangle",
        points=[
            Point(x=0.0, y=0.0),
            Point(x=10.0, y=0.0),
            Point(x=10.0, y=10.0),
            Point(x=0.0, y=10.0),
        ],
        is_closed=True,
        bounding_box=BoundingBox(
            min_x=0.0, min_y=0.0, max_x=10.0, max_y=10.0, width=10.0, height=10.0
        ),
    )
    req = TransformRequest(entities=[rect], scale_x=2.0, scale_y=2.0)
    res = apply_transformations(req)

    assert len(res.entities) == 1
    transformed = res.entities[0]
    xs = [p.x for p in transformed.points]
    ys = [p.y for p in transformed.points]
    assert 20.0 in xs or pytest.approx(max(xs)) == 20.0
    assert 20.0 in ys or pytest.approx(max(ys)) == 20.0

    if transformed.bounding_box:
        assert pytest.approx(transformed.bounding_box.width, rel=1e-2) == 20.0
        assert pytest.approx(transformed.bounding_box.height, rel=1e-2) == 20.0


def test_rotation_transformation():
    """Test rotating a point/line by 90 degrees."""
    line = GeometryEntity(
        id="rot_line",
        entity_type="line",
        points=[Point(x=0.0, y=0.0), Point(x=10.0, y=0.0)],
        is_closed=False,
    )
    req = TransformRequest(entities=[line], rotation_degrees=90.0)
    res = apply_transformations(req)

    assert len(res.entities) == 1
    p1 = res.entities[0].points[0]
    p2 = res.entities[0].points[1]

    assert pytest.approx(p1.x, abs=1e-2) == 0.0
    assert pytest.approx(p1.y, abs=1e-2) == 0.0
    # Point (10, 0) rotated by 90 deg has x approx 0 and abs(y) approx 10
    assert pytest.approx(p2.x, abs=1e-2) == 0.0
    assert pytest.approx(abs(p2.y), abs=1e-2) == 10.0


def test_translation_transformation():
    """Test translating an entity by (10, 20)."""
    line = GeometryEntity(
        id="trans_line",
        entity_type="line",
        points=[Point(x=0.0, y=0.0), Point(x=5.0, y=5.0)],
        is_closed=False,
    )
    req = TransformRequest(entities=[line], translate_x=10.0, translate_y=20.0)
    res = apply_transformations(req)

    assert len(res.entities) == 1
    pts = res.entities[0].points
    assert pytest.approx(pts[0].x, abs=1e-3) == 10.0
    assert pytest.approx(pts[0].y, abs=1e-3) == 20.0
    assert pytest.approx(pts[1].x, abs=1e-3) == 15.0
    assert pytest.approx(pts[1].y, abs=1e-3) == 25.0


def test_combined_transformation():
    """Test combined scale, rotation, and translation transformations."""
    entity = GeometryEntity(
        id="comb_ent",
        entity_type="line",
        points=[Point(x=5.0, y=0.0), Point(x=10.0, y=0.0)],
        is_closed=False,
    )
    req = TransformRequest(
        entities=[entity],
        scale_x=2.0,
        scale_y=2.0,
        rotation_degrees=90.0,
        translate_x=15.0,
        translate_y=25.0,
    )
    res = apply_transformations(req)

    assert len(res.entities) == 1
    assert "scale_x" in res.applied_transforms
    assert "rotation_degrees" in res.applied_transforms
    assert "translate_x" in res.applied_transforms
    assert len(res.entities[0].points) == 2


def test_nesting_basic():
    """Test nesting 3 small rectangles on a large sheet; all should fit."""
    shapes = [
        GeometryEntity(
            id=f"rect_nest_{i}",
            entity_type="rectangle",
            points=[
                Point(x=0.0, y=0.0),
                Point(x=20.0, y=0.0),
                Point(x=20.0, y=20.0),
                Point(x=0.0, y=20.0),
            ],
            bounding_box=BoundingBox(
                min_x=0.0, min_y=0.0, max_x=20.0, max_y=20.0, width=20.0, height=20.0
            ),
        )
        for i in range(3)
    ]
    req = NestRequest(
        shapes=shapes,
        sheet_width=200.0,
        sheet_height=200.0,
        spacing=5.0,
        margin=5.0,
        allow_rotation=True,
    )
    res = nest_shapes(req)

    assert len(res.placed_shapes) == 3
    assert len(res.unplaced_shapes) == 0
    assert res.utilization_percent > 0.0
    assert res.sheet_width == 200.0
    assert res.sheet_height == 200.0


def test_nesting_overflow():
    """Test nesting shapes too large for sheet; verify unplaced list contains overflow shapes."""
    shapes = [
        GeometryEntity(
            id="huge_1",
            entity_type="rectangle",
            points=[
                Point(x=0.0, y=0.0),
                Point(x=80.0, y=0.0),
                Point(x=80.0, y=80.0),
                Point(x=0.0, y=80.0),
            ],
            bounding_box=BoundingBox(
                min_x=0.0, min_y=0.0, max_x=80.0, max_y=80.0, width=80.0, height=80.0
            ),
        ),
        GeometryEntity(
            id="huge_2",
            entity_type="rectangle",
            points=[
                Point(x=0.0, y=0.0),
                Point(x=80.0, y=0.0),
                Point(x=80.0, y=80.0),
                Point(x=0.0, y=80.0),
            ],
            bounding_box=BoundingBox(
                min_x=0.0, min_y=0.0, max_x=80.0, max_y=80.0, width=80.0, height=80.0
            ),
        ),
    ]
    # Sheet 100x100 with margin 15 leaves 70x70, so an 80x80 shape cannot fit
    req = NestRequest(
        shapes=shapes,
        sheet_width=100.0,
        sheet_height=100.0,
        spacing=5.0,
        margin=15.0,
        allow_rotation=False,
    )
    res = nest_shapes(req)

    assert len(res.unplaced_shapes) >= 1


def test_nesting_utilization():
    """Test nesting material utilization calculation is positive and <= 100%."""
    shape = GeometryEntity(
        id="util_shape",
        entity_type="rectangle",
        points=[
            Point(x=0.0, y=0.0),
            Point(x=50.0, y=0.0),
            Point(x=50.0, y=50.0),
            Point(x=0.0, y=50.0),
        ],
        bounding_box=BoundingBox(
            min_x=0.0, min_y=0.0, max_x=50.0, max_y=50.0, width=50.0, height=50.0
        ),
    )
    req = NestRequest(
        shapes=[shape],
        sheet_width=100.0,
        sheet_height=100.0,
        spacing=2.0,
        margin=5.0,
    )
    res = nest_shapes(req)

    assert 0.0 < res.utilization_percent <= 100.0


def test_laser_config_default():
    """Test get_default_config returns a valid LaserConfig with standard layers."""
    cfg = get_default_config()
    assert isinstance(cfg, LaserConfig)
    assert len(cfg.layers) > 0
    assert cfg.max_s_value >= 1.0

    layer_names = [l.name.lower() for l in cfg.layers]
    assert any(name in layer_names for name in ["cut", "engrave", "score", "default"])


def test_laser_config_custom():
    """Test creating custom laser configuration with multiple layers."""
    layers = [
        LaserLayer(name="cut", speed_mm_min=450.0, power_percent=90.0, passes=2),
        LaserLayer(name="engrave", speed_mm_min=2800.0, power_percent=25.0, passes=1, frequency=5000.0),
    ]
    req = LaserConfigRequest(layers=layers, max_s_value=1000.0)
    cfg = create_laser_config(req)

    assert len(cfg.layers) == 2
    assert cfg.layers[0].name == "cut"
    assert cfg.layers[0].speed_mm_min == 450.0
    assert cfg.layers[0].power_percent == 90.0
    assert cfg.layers[0].passes == 2
    assert cfg.layers[1].name == "engrave"
    assert cfg.layers[1].frequency == 5000.0


def test_laser_config_empty_layers():
    """Test that empty layers list raises ValueError."""
    with pytest.raises((ValueError, Exception)):
        create_laser_config(LaserConfigRequest(layers=[]))


def test_gcode_basic():
    """Test generating basic G-code for a simple rectangle."""
    rect = GeometryEntity(
        id="gcode_rect",
        entity_type="rectangle",
        points=[
            Point(x=0.0, y=0.0),
            Point(x=10.0, y=0.0),
            Point(x=10.0, y=10.0),
            Point(x=0.0, y=10.0),
            Point(x=0.0, y=0.0),
        ],
        is_closed=True,
        bounding_box=BoundingBox(
            min_x=0.0, min_y=0.0, max_x=10.0, max_y=10.0, width=10.0, height=10.0
        ),
    )
    cfg = get_default_config()
    req = GCodeRequest(entities=[rect], laser_config=cfg)
    res = generate_gcode(req)

    assert isinstance(res.gcode, str)
    assert res.line_count > 0
    assert len(res.toolpath_preview) > 0
    assert any("G1" in line or "G0" in line for line in res.gcode.splitlines())


def test_gcode_circle():
    """Test generating G-code for a circle entity."""
    circle = GeometryEntity(
        id="gcode_circ",
        entity_type="circle",
        center=Point(x=20.0, y=20.0),
        radius=10.0,
        is_closed=True,
        bounding_box=BoundingBox(
            min_x=10.0, min_y=10.0, max_x=30.0, max_y=30.0, width=20.0, height=20.0
        ),
    )
    cfg = get_default_config()
    req = GCodeRequest(entities=[circle], laser_config=cfg)
    res = generate_gcode(req)

    assert isinstance(res.gcode, str)
    assert res.line_count > 0
    assert len(res.gcode) > 0


def test_gcode_multiple_passes():
    """Test that multiple passes generate repeated cutting commands."""
    rect = GeometryEntity(
        id="gcode_multi_rect",
        entity_type="rectangle",
        points=[
            Point(x=0.0, y=0.0),
            Point(x=10.0, y=0.0),
            Point(x=10.0, y=10.0),
            Point(x=0.0, y=10.0),
            Point(x=0.0, y=0.0),
        ],
        is_closed=True,
        bounding_box=BoundingBox(
            min_x=0.0, min_y=0.0, max_x=10.0, max_y=10.0, width=10.0, height=10.0
        ),
    )
    layer_single = LaserLayer(name="cut", speed_mm_min=1000.0, power_percent=80.0, passes=1)
    layer_multi = LaserLayer(name="cut", speed_mm_min=1000.0, power_percent=80.0, passes=3)

    cfg_single = LaserConfig(layers=[layer_single], max_s_value=1000.0)
    cfg_multi = LaserConfig(layers=[layer_multi], max_s_value=1000.0)

    res_single = generate_gcode(
        GCodeRequest(entities=[rect], laser_config=cfg_single, selected_layer="cut")
    )
    res_multi = generate_gcode(
        GCodeRequest(entities=[rect], laser_config=cfg_multi, selected_layer="cut")
    )

    assert res_multi.line_count > res_single.line_count


def test_gcode_contains_safety_commands():
    """Test that generated G-code contains critical laser safety commands (M5, G90, G21)."""
    entity = GeometryEntity(
        id="safe_ent",
        entity_type="line",
        points=[Point(x=0.0, y=0.0), Point(x=10.0, y=10.0)],
        is_closed=False,
    )
    cfg = get_default_config()
    res = generate_gcode(GCodeRequest(entities=[entity], laser_config=cfg))

    gcode_text = res.gcode
    # Laser disable / safety
    assert "M5" in gcode_text
    # Absolute distance mode
    assert "G90" in gcode_text
    # Millimeter units
    assert "G21" in gcode_text
