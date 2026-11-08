"""Integration tests for the LightBurn Backend Prototype API endpoints."""
import os
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

SAMPLES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "samples")

sample_entity = {
    "id": "test1",
    "entity_type": "rectangle",
    "points": [
        {"x": 0.0, "y": 0.0},
        {"x": 10.0, "y": 0.0},
        {"x": 10.0, "y": 10.0},
        {"x": 0.0, "y": 10.0},
    ],
    "is_closed": True,
    "bounding_box": {
        "min_x": 0.0,
        "min_y": 0.0,
        "max_x": 10.0,
        "max_y": 10.0,
        "width": 10.0,
        "height": 10.0,
    },
    "original_units": "mm",
}

sample_entity_2 = {
    "id": "test2",
    "entity_type": "rectangle",
    "points": [
        {"x": 0.0, "y": 0.0},
        {"x": 20.0, "y": 0.0},
        {"x": 20.0, "y": 15.0},
        {"x": 0.0, "y": 15.0},
    ],
    "is_closed": True,
    "bounding_box": {
        "min_x": 0.0,
        "min_y": 0.0,
        "max_x": 20.0,
        "max_y": 15.0,
        "width": 20.0,
        "height": 15.0,
    },
    "original_units": "mm",
}


def test_health():
    """Test GET /health returns 200 with status 'healthy'."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "0.1.0"


def test_import_svg():
    """Test POST /api/import/svg with sample SVG file and verify geometry entities."""
    sample_path = os.path.join(SAMPLES_DIR, "sample.svg")
    if os.path.exists(sample_path):
        with open(sample_path, "rb") as f:
            file_bytes = f.read()
    else:
        file_bytes = (
            b'<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100">'
            b'<rect x="10" y="10" width="50" height="50" fill="none" stroke="black"/>'
            b'<circle cx="50" cy="50" r="20" fill="none" stroke="red"/>'
            b'<line x1="0" y1="0" x2="100" y2="100" stroke="blue"/>'
            b"</svg>"
        )

    response = client.post(
        "/api/import/svg",
        files={"file": ("sample.svg", file_bytes, "image/svg+xml")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "entities" in data
    assert isinstance(data["entities"], list)
    assert len(data["entities"]) > 0
    assert "total_count" in data
    assert data["total_count"] == len(data["entities"])
    assert "source_file" in data


def test_import_dxf():
    """Test POST /api/import/dxf with sample DXF file and verify geometry entities."""
    sample_path = os.path.join(SAMPLES_DIR, "sample.dxf")
    if os.path.exists(sample_path):
        with open(sample_path, "rb") as f:
            file_bytes = f.read()
    else:
        file_bytes = (
            "0\nSECTION\n"
            "2\nENTITIES\n"
            "0\nLINE\n"
            "8\n0\n"
            "10\n0.0\n"
            "20\n0.0\n"
            "30\n0.0\n"
            "11\n50.0\n"
            "21\n50.0\n"
            "31\n0.0\n"
            "0\nCIRCLE\n"
            "8\n0\n"
            "10\n25.0\n"
            "20\n25.0\n"
            "30\n0.0\n"
            "40\n10.0\n"
            "0\nENDSEC\n"
            "0\nEOF\n"
        ).encode("utf-8")

    response = client.post(
        "/api/import/dxf",
        files={"file": ("sample.dxf", file_bytes, "application/dxf")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "entities" in data
    assert isinstance(data["entities"], list)
    assert len(data["entities"]) > 0
    assert "total_count" in data
    assert data["total_count"] == len(data["entities"])
    assert "source_file" in data


def test_import_svg_invalid_extension():
    """Test POST /api/import/svg with non-SVG file, expecting 400 Bad Request."""
    response = client.post(
        "/api/import/svg",
        files={"file": ("test.txt", b"plain text content", "text/plain")},
    )
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "svg" in data["detail"].lower()


def test_import_dxf_invalid_extension():
    """Test POST /api/import/dxf with non-DXF file, expecting 400 Bad Request."""
    response = client.post(
        "/api/import/dxf",
        files={"file": ("test.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert "dxf" in data["detail"].lower()


def test_transform():
    """Test POST /api/transform with entities and transformation parameters."""
    payload = {
        "entities": [sample_entity],
        "scale_x": 2.0,
        "scale_y": 2.0,
        "rotation_degrees": 45.0,
        "translate_x": 10.0,
        "translate_y": 20.0,
    }
    response = client.post("/api/transform", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "entities" in data
    assert len(data["entities"]) == 1
    assert "applied_transforms" in data
    assert data["applied_transforms"]["scale_x"] == 2.0
    assert data["applied_transforms"]["scale_y"] == 2.0
    assert data["applied_transforms"]["rotation_degrees"] == 45.0
    assert data["applied_transforms"]["translate_x"] == 10.0
    assert data["applied_transforms"]["translate_y"] == 20.0


def test_transform_with_applied_transforms():
    """Regression test for POST /api/transform when parameters are passed inside applied_transforms dict."""
    payload = {
        "entities": [
            {
                "id": "rect_test",
                "entity_type": "rectangle",
                "points": [
                    {"x": 10.0, "y": 10.0},
                    {"x": 30.0, "y": 10.0},
                    {"x": 30.0, "y": 20.0},
                    {"x": 10.0, "y": 20.0},
                ],
                "is_closed": True,
            }
        ],
        "applied_transforms": {
            "scale_x": 2.0,
            "scale_y": 2.0,
            "rotation_degrees": 0.0,
            "translate_x": 5.0,
            "translate_y": 5.0,
        },
    }
    response = client.post("/api/transform", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "entities" in data
    assert len(data["entities"]) == 1

    # Verify expected coordinates: (25,25), (65,25), (65,45), (25,45)
    points = data["entities"][0]["points"]
    expected_points = [(25.0, 25.0), (65.0, 25.0), (65.0, 45.0), (25.0, 45.0)]
    assert len(points) == len(expected_points)
    for p, (exp_x, exp_y) in zip(points, expected_points):
        assert pytest.approx(p["x"], abs=1e-3) == exp_x
        assert pytest.approx(p["y"], abs=1e-3) == exp_y

    # Verify returned transformation values
    assert "applied_transforms" in data
    assert data["applied_transforms"]["scale_x"] == 2.0
    assert data["applied_transforms"]["scale_y"] == 2.0
    assert data["applied_transforms"]["rotation_degrees"] == 0.0
    assert data["applied_transforms"]["translate_x"] == 5.0
    assert data["applied_transforms"]["translate_y"] == 5.0


def test_nest():
    """Test POST /api/nest with multiple shapes and sheet dimensions."""
    payload = {
        "shapes": [sample_entity, sample_entity_2],
        "sheet_width": 200.0,
        "sheet_height": 200.0,
        "spacing": 2.0,
        "allow_rotation": True,
        "margin": 5.0,
    }
    response = client.post("/api/nest", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "placed_shapes" in data
    assert len(data["placed_shapes"]) == 2
    assert "unplaced_shapes" in data
    assert len(data["unplaced_shapes"]) == 0
    assert "utilization_percent" in data
    assert data["utilization_percent"] >= 0.0
    assert data["sheet_width"] == 200.0
    assert data["sheet_height"] == 200.0
    assert "algorithm" in data


def test_laser_parameters():
    """Test POST /api/laser-parameters with valid config."""
    payload = {
        "layers": [
            {
                "name": "cut",
                "speed_mm_min": 600.0,
                "power_percent": 85.0,
                "passes": 2,
                "frequency": None,
            },
            {
                "name": "engrave",
                "speed_mm_min": 2500.0,
                "power_percent": 30.0,
                "passes": 1,
                "frequency": None,
            },
        ],
        "max_s_value": 1000.0,
    }
    response = client.post("/api/laser-parameters", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "layers" in data
    assert len(data["layers"]) == 2
    assert data["max_s_value"] == 1000.0
    assert data["layers"][0]["name"] == "cut"
    assert data["layers"][0]["speed_mm_min"] == 600.0
    assert data["layers"][0]["power_percent"] == 85.0
    assert data["layers"][0]["passes"] == 2
    assert data["layers"][1]["name"] == "engrave"


def test_laser_parameters_default():
    """Test GET /api/laser-parameters/default returns default presets."""
    response = client.get("/api/laser-parameters/default")
    assert response.status_code == 200
    data = response.json()
    assert "layers" in data
    assert len(data["layers"]) > 0
    assert "max_s_value" in data


def test_laser_parameters_invalid():
    """Test POST /api/laser-parameters with empty layers list or out-of-range values."""
    # Test empty layers list (should fail validation)
    empty_payload = {"layers": [], "max_s_value": 1000.0}
    response_empty = client.post("/api/laser-parameters", json=empty_payload)
    assert response_empty.status_code in (400, 422)

    # Test out of range power_percent (> 100)
    out_of_range_payload = {
        "layers": [
            {
                "name": "burn",
                "speed_mm_min": 1000.0,
                "power_percent": 150.0,
                "passes": 1,
            }
        ],
        "max_s_value": 1000.0,
    }
    response_out = client.post("/api/laser-parameters", json=out_of_range_payload)
    assert response_out.status_code in (400, 422)

    # Test negative speed
    negative_speed_payload = {
        "layers": [
            {
                "name": "fast",
                "speed_mm_min": -500.0,
                "power_percent": 50.0,
                "passes": 1,
            }
        ],
        "max_s_value": 1000.0,
    }
    response_neg = client.post("/api/laser-parameters", json=negative_speed_payload)
    assert response_neg.status_code in (400, 422)


def test_gcode_generation():
    """Test POST /api/gcode with entities and laser config."""
    payload = {
        "entities": [sample_entity],
        "laser_config": {
            "layers": [
                {
                    "name": "default",
                    "speed_mm_min": 1000.0,
                    "power_percent": 50.0,
                    "passes": 1,
                    "frequency": None,
                }
            ],
            "max_s_value": 1000.0,
        },
        "selected_layer": "default",
    }
    response = client.post("/api/gcode", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "gcode" in data
    assert isinstance(data["gcode"], str)
    assert data["line_count"] > 0
    assert "toolpath_preview" in data
    assert isinstance(data["toolpath_preview"], list)
    assert len(data["toolpath_preview"]) > 0
    # Safety checks in G-code
    assert "M5" in data["gcode"]
    assert "G90" in data["gcode"]
    assert "G21" in data["gcode"]
