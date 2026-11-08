# LightBurn Backend Prototype

A high-performance laser software backend prototype inspired by [LightBurn](https://lightburnsoftware.com/). This system provides geometric vector ingestion (SVG, DXF), affine spatial transformations (scaling, rotation, translation), 2D material nesting (greedy shelf bin-packing), laser cut/engrave layer parameter management, and GRBL-compatible G-code generation with toolpath previews.

> **DISCLAIMER:**  
> **Simulation & Preview Tool Only.** This backend prototype does NOT connect to, control, or drive physical laser hardware, CNC controllers, or high-voltage machinery. It is designed solely for mathematical simulation, geometric validation, nesting optimization, and G-code preview generation in a safe offline environment. Never stream generated G-code to laser equipment without manual verification.

---

## Tech Stack

- **Language & Runtime:** Python 3.10+
- **Web Framework:** [FastAPI](https://fastapi.tiangolo.com/) with [Pydantic v2](https://docs.pydantic.dev/) for typed schemas and data validation
- **ASGI Server:** [Uvicorn](https://www.uvicorn.org/)
- **Vector & CAD Parsing:**
  - SVG: `svgpathtools` / `xml.etree.ElementTree`
  - DXF: `ezdxf` (AutoCAD DXF R12 / 2000+)
- **Testing & Quality Assurance:** [pytest](https://docs.pytest.org/), [httpx](https://www.python-httpx.org/) TestClient

---

## Project Structure

```text
lightburn_backend/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI application setup and routing
│   ├── core/
│   │   ├── __init__.py
│   │   ├── geometry.py             # Point, BoundingBox, GeometryEntity, GeometryCollection
│   │   ├── transformations.py      # Affine transforms (scale, rotate, translate)
│   │   ├── nesting.py              # 2D greedy shelf nesting algorithm
│   │   ├── laser_parameters.py     # LaserLayer and LaserConfig models & presets
│   │   └── gcode_generator.py      # GRBL G-code generation & toolpath preview
│   └── services/
│       ├── __init__.py
│       ├── svg_processor.py        # SVG vector parser & entity extractor
│       └── dxf_processor.py        # DXF CAD parser & entity extractor
├── samples/
│   ├── sample.svg                  # Test SVG sample vector file
│   └── sample.dxf                  # Test DXF sample CAD file
├── tests/
│   ├── __init__.py
│   ├── test_api.py                 # FastAPI endpoint integration tests
│   └── test_geometry.py            # Core geometry, nesting, and G-code unit tests
├── requirements.txt                # Project dependencies
└── README.md                       # Documentation & API reference
```

---

## Installation (Windows PowerShell)

Ensure Python 3.10 or higher is installed and accessible in your PATH.

```powershell
# 1. Navigate to the backend project root
cd lightburn_backend

# 2. Create a virtual environment
python -m venv venv

# 3. Activate the virtual environment
.\venv\Scripts\Activate.ps1

# 4. Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Running the Server

Start the local development server using Uvicorn with auto-reload:

```powershell
uvicorn app.main:app --reload
```

The application will bind to `http://127.0.0.1:8000`.

- **Swagger UI Interactive API Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc Alternative Docs:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## Running Tests

Execute the complete test suite with verbose output using `pytest`:

```powershell
pytest tests/ -v
```

To run with coverage reporting:

```powershell
pytest --cov=app tests/ -v
```

---

## API Endpoints & Usage Examples

### 1. Health Check (`GET /health`)

Check the health status of the API server.

**curl:**
```bash
curl -X GET "http://127.0.0.1:8000/health"
```

**httpx (Python):**
```python
import httpx

response = httpx.get("http://127.0.0.1:8000/health")
print(response.json())
```

**Response (`200 OK`):**
```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

---

### 2. Import SVG File (`POST /api/import/svg`)

Upload an SVG vector file to extract geometric primitives (paths, rectangles, circles, polylines) normalized in millimeters.

**curl:**
```bash
curl -X POST "http://127.0.0.1:8000/api/import/svg" \
  -F "file=@samples/sample.svg"
```

**httpx (Python):**
```python
import httpx

with open("samples/sample.svg", "rb") as f:
    response = httpx.post(
        "http://127.0.0.1:8000/api/import/svg",
        files={"file": ("sample.svg", f, "image/svg+xml")}
    )
print(response.json())
```

**Response (`200 OK` - abbreviated):**
```json
{
  "entities": [
    {
      "id": "a1b2c3d4",
      "entity_type": "rectangle",
      "points": [
        {"x": 10.0, "y": 10.0},
        {"x": 60.0, "y": 10.0},
        {"x": 60.0, "y": 60.0},
        {"x": 10.0, "y": 60.0}
      ],
      "is_closed": true,
      "bounding_box": {
        "min_x": 10.0,
        "min_y": 10.0,
        "max_x": 60.0,
        "max_y": 60.0,
        "width": 50.0,
        "height": 50.0
      },
      "original_units": "mm"
    }
  ],
  "total_count": 1,
  "bounding_box": {
    "min_x": 10.0,
    "min_y": 10.0,
    "max_x": 60.0,
    "max_y": 60.0,
    "width": 50.0,
    "height": 50.0
  },
  "source_file": "sample.svg",
  "source_format": "svg",
  "warnings": []
}
```

---

### 3. Import DXF File (`POST /api/import/dxf`)

Upload an AutoCAD DXF file to parse CAD entities (lines, lwpolylines, circles, arcs).

**curl:**
```bash
curl -X POST "http://127.0.0.1:8000/api/import/dxf" \
  -F "file=@samples/sample.dxf"
```

**httpx (Python):**
```python
import httpx

with open("samples/sample.dxf", "rb") as f:
    response = httpx.post(
        "http://127.0.0.1:8000/api/import/dxf",
        files={"file": ("sample.dxf", f, "application/dxf")}
    )
print(response.json())
```

**Response (`200 OK` - abbreviated):**
```json
{
  "entities": [
    {
      "id": "e5f6a7b8",
      "entity_type": "line",
      "points": [
        {"x": 0.0, "y": 0.0},
        {"x": 50.0, "y": 50.0}
      ],
      "is_closed": false,
      "bounding_box": {
        "min_x": 0.0,
        "min_y": 0.0,
        "max_x": 50.0,
        "max_y": 50.0,
        "width": 50.0,
        "height": 50.0
      },
      "original_units": "mm"
    }
  ],
  "total_count": 1,
  "bounding_box": {
    "min_x": 0.0,
    "min_y": 0.0,
    "max_x": 50.0,
    "max_y": 50.0,
    "width": 50.0,
    "height": 50.0
  },
  "source_file": "sample.dxf",
  "source_format": "dxf",
  "warnings": []
}
```

---

### 4. Affine Transformations (`POST /api/transform`)

Apply non-uniform scaling, rotation (in degrees), and linear translations to a list of geometry entities.

**curl:**
```bash
curl -X POST "http://127.0.0.1:8000/api/transform" \
  -H "Content-Type: application/json" \
  -d '{
    "entities": [
      {
        "id": "rect1",
        "entity_type": "rectangle",
        "points": [
          {"x": 0.0, "y": 0.0},
          {"x": 10.0, "y": 0.0},
          {"x": 10.0, "y": 10.0},
          {"x": 0.0, "y": 10.0}
        ],
        "is_closed": true
      }
    ],
    "scale_x": 2.0,
    "scale_y": 2.0,
    "rotation_degrees": 90.0,
    "translate_x": 5.0,
    "translate_y": 10.0
  }'
```

**Response (`200 OK` - abbreviated):**
```json
{
  "entities": [
    {
      "id": "rect1",
      "entity_type": "rectangle",
      "points": [
        {"x": 5.0, "y": 10.0},
        {"x": 5.0, "y": 30.0},
        {"x": -15.0, "y": 30.0},
        {"x": -15.0, "y": 10.0}
      ],
      "is_closed": true,
      "bounding_box": {
        "min_x": -15.0,
        "min_y": 10.0,
        "max_x": 5.0,
        "max_y": 30.0,
        "width": 20.0,
        "height": 20.0
      }
    }
  ],
  "applied_transforms": {
    "scale_x": 2.0,
    "scale_y": 2.0,
    "rotation_degrees": 90.0,
    "translate_x": 5.0,
    "translate_y": 10.0
  }
}
```

---

### 5. 2D Sheet Nesting (`POST /api/nest`)

Pack multiple geometric parts onto a rectangular sheet, accounting for part spacing, margins, and 90-degree rotations.

**curl:**
```bash
curl -X POST "http://127.0.0.1:8000/api/nest" \
  -H "Content-Type: application/json" \
  -d '{
    "shapes": [
      {
        "id": "part_1",
        "entity_type": "rectangle",
        "points": [{"x": 0, "y": 0}, {"x": 40, "y": 0}, {"x": 40, "y": 20}, {"x": 0, "y": 20}],
        "bounding_box": {"min_x": 0, "min_y": 0, "max_x": 40, "max_y": 20, "width": 40, "height": 20}
      },
      {
        "id": "part_2",
        "entity_type": "rectangle",
        "points": [{"x": 0, "y": 0}, {"x": 30, "y": 0}, {"x": 30, "y": 30}, {"x": 0, "y": 30}],
        "bounding_box": {"min_x": 0, "min_y": 0, "max_x": 30, "max_y": 30, "width": 30, "height": 30}
      }
    ],
    "sheet_width": 300.0,
    "sheet_height": 200.0,
    "spacing": 3.0,
    "allow_rotation": true,
    "margin": 10.0
  }'
```

**Response (`200 OK` - abbreviated):**
```json
{
  "placed_shapes": [
    {
      "shape_id": "part_1",
      "x": 10.0,
      "y": 10.0,
      "width": 40.0,
      "height": 20.0,
      "rotated": false,
      "bounding_box": {
        "min_x": 10.0,
        "min_y": 10.0,
        "max_x": 50.0,
        "max_y": 30.0,
        "width": 40.0,
        "height": 20.0
      }
    },
    {
      "shape_id": "part_2",
      "x": 53.0,
      "y": 10.0,
      "width": 30.0,
      "height": 30.0,
      "rotated": false,
      "bounding_box": {
        "min_x": 53.0,
        "min_y": 10.0,
        "max_x": 83.0,
        "max_y": 40.0,
        "width": 30.0,
        "height": 30.0
      }
    }
  ],
  "unplaced_shapes": [],
  "utilization_percent": 2.83,
  "sheet_width": 300.0,
  "sheet_height": 200.0,
  "algorithm": "greedy-shelf"
}
```

---

### 6. Laser Parameters Configuration (`POST /api/laser-parameters`)

Configure laser power, traverse feed rates, pass counts, and spindle scaling.

**curl:**
```bash
curl -X POST "http://127.0.0.1:8000/api/laser-parameters" \
  -H "Content-Type: application/json" \
  -d '{
    "layers": [
      {
        "name": "cut_3mm_plywood",
        "speed_mm_min": 500.0,
        "power_percent": 95.0,
        "passes": 2
      },
      {
        "name": "engrave_surface",
        "speed_mm_min": 3000.0,
        "power_percent": 25.0,
        "passes": 1
      }
    ],
    "max_s_value": 1000.0
  }'
```

**Response (`200 OK`):**
```json
{
  "layers": [
    {
      "name": "cut_3mm_plywood",
      "speed_mm_min": 500.0,
      "power_percent": 95.0,
      "passes": 2,
      "frequency": null
    },
    {
      "name": "engrave_surface",
      "speed_mm_min": 3000.0,
      "power_percent": 25.0,
      "passes": 1,
      "frequency": null
    }
  ],
  "max_s_value": 1000.0
}
```

---

### 7. G-Code Generation (`POST /api/gcode`)

Translate geometry entities and laser parameters into GRBL-standard G-code with toolpath previews.

**curl:**
```bash
curl -X POST "http://127.0.0.1:8000/api/gcode" \
  -H "Content-Type: application/json" \
  -d '{
    "entities": [
      {
        "id": "box_1",
        "entity_type": "rectangle",
        "points": [
          {"x": 10.0, "y": 10.0},
          {"x": 30.0, "y": 10.0},
          {"x": 30.0, "y": 30.0},
          {"x": 10.0, "y": 30.0},
          {"x": 10.0, "y": 10.0}
        ],
        "is_closed": true
      }
    ],
    "laser_config": {
      "layers": [
        {
          "name": "cut",
          "speed_mm_min": 800.0,
          "power_percent": 80.0,
          "passes": 1
        }
      ],
      "max_s_value": 1000.0
    },
    "selected_layer": "cut"
  }'
```

**Response (`200 OK` - abbreviated):**
```json
{
  "gcode": "; LightBurn Backend Prototype - GRBL G-code\n; Layer: cut (Speed: 800 mm/min, Power: 80%, Passes: 1)\nG21 ; Millimeter units\nG90 ; Absolute distance mode\nM5 ; Laser off safety\nG0 X10.000 Y10.000\nM3 S800.0 ; Laser on\nG1 X30.000 Y10.000 F800\nG1 X30.000 Y30.000 F800\nG1 X10.000 Y30.000 F800\nG1 X10.000 Y10.000 F800\nM5 ; Laser off\nM2 ; Program end\n",
  "line_count": 12,
  "estimated_duration_seconds": 6.8,
  "toolpath_preview": [
    {
      "segment_type": "rapid",
      "start": {"x": 0.0, "y": 0.0},
      "end": {"x": 10.0, "y": 10.0}
    },
    {
      "segment_type": "cut",
      "start": {"x": 10.0, "y": 10.0},
      "end": {"x": 30.0, "y": 10.0}
    }
  ],
  "warnings": []
}
```

---

## Known Limitations

1. **Greedy-Shelf Nesting:**  
   The current nesting engine uses bounding-box approximation and a greedy 2D shelf-packing heuristic. It does not perform true irregular polygon concave nesting (no No-Fit Polygon / NFP computation) or part-in-part nesting (placing small parts inside donut holes or hollows).
2. **Simplified Arc & Spline Linearization:**  
   Complex SVG Bezier curves and CAD splines are tessellated into linear segments (`points`) during ingestion rather than native circular arc G-code interpolation (`G2`/`G3`).
3. **No Direct Hardware Serial Communication:**  
   There is no CH340/FTDI USB COM port streamer or web-serial communication loop. The backend outputs standard G-code files suitable for external previewers (e.g. LaserGRBL, LightBurn, ncviewer) or simulation engines.
4. **Raster Image Engraving:**  
   Bitmap raster engraving (halftone, dithering, bidirectional raster scanning) is not currently implemented in this vector-focused prototype.

---

## Laser Safety & Operational Disclaimer

- **Never connect this software directly to unshielded or active laser equipment without independent hardware emergency stops.**
- Laser cutters produce toxic fumes, fire hazards, and invisible ionizing or non-ionizing optical radiation that can cause permanent blindness.
- Always review toolpaths and verify feed rates, focus heights, and power levels before machining on physical hardware.

