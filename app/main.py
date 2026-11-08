"""LightBurn Backend Prototype - FastAPI Application.

A laser software backend prototype inspired by LightBurn.
This is a simulation/preview tool only and never connects to physical laser hardware.
"""
from typing import Dict, Any
from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.geometry import GeometryCollection
from app.core.transformations import TransformRequest, TransformResponse, apply_transformations
from app.core.nesting import NestRequest, NestResult, nest_shapes
from app.core.laser_parameters import (
    LaserConfigRequest,
    LaserConfig,
    create_laser_config,
    get_default_config,
)
from app.core.gcode_generator import GCodeRequest, GCodeResult, generate_gcode
from app.services.svg_processor import process_svg
from app.services.dxf_processor import process_dxf

app = FastAPI(
    title="LightBurn Backend Prototype",
    description=(
        "A laser software backend prototype inspired by LightBurn for geometry processing, "
        "affine transformations, 2D nesting, laser parameter management, and G-code generation. "
        "Notice: This is a simulation/preview tool only and never connects to physical laser hardware."
    ),
    version="0.1.0",
)

# Enable CORS for frontend integration and local visualization tools
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/health",
    summary="Health Check",
    response_model=Dict[str, str],
    tags=["System"],
)
async def health_check() -> Dict[str, str]:
    """Health check endpoint to verify backend operational status.

    Returns:
        Dict[str, str]: Service status and current version.
    """
    return {"status": "healthy", "version": "0.1.0"}


@app.post(
    "/api/import/svg",
    summary="Import SVG File",
    response_model=GeometryCollection,
    tags=["Import"],
)
async def import_svg(file: UploadFile = File(...)) -> GeometryCollection:
    """Import and parse an SVG file into standardized geometric entities.

    Validates file extension, extracts paths, lines, rectangles, circles,
    and polylines, and standardizes coordinates in millimeters (mm).

    Args:
        file (UploadFile): The uploaded SVG vector file.

    Returns:
        GeometryCollection: Parsed geometry entities, bounding box, and metadata.

    Raises:
        HTTPException: 400 Bad Request if file extension is invalid or parsing fails.
        HTTPException: 500 Internal Server Error for unhandled exceptions.
    """
    if not file.filename or not file.filename.lower().endswith(".svg"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only .svg files are supported.",
        )
    try:
        content = await file.read()
        return process_svg(content, file.filename)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process SVG file: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error processing SVG: {str(e)}",
        )


@app.post(
    "/api/import/dxf",
    summary="Import DXF File",
    response_model=GeometryCollection,
    tags=["Import"],
)
async def import_dxf(file: UploadFile = File(...)) -> GeometryCollection:
    """Import and parse an AutoCAD DXF file into standardized geometric entities.

    Validates file extension, extracts lines, lwpolylines, polylines, circles,
    arcs, and splines, and standardizes coordinates in millimeters (mm).

    Args:
        file (UploadFile): The uploaded DXF CAD file.

    Returns:
        GeometryCollection: Parsed geometry entities, bounding box, and metadata.

    Raises:
        HTTPException: 400 Bad Request if file extension is invalid or parsing fails.
        HTTPException: 500 Internal Server Error for unhandled exceptions.
    """
    if not file.filename or not file.filename.lower().endswith(".dxf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only .dxf files are supported.",
        )
    try:
        content = await file.read()
        return process_dxf(content, file.filename)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process DXF file: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error processing DXF: {str(e)}",
        )


@app.post(
    "/api/transform",
    summary="Apply Affine Transformations",
    response_model=TransformResponse,
    tags=["Transformations"],
)
async def transform(request: TransformRequest) -> TransformResponse:
    """Apply affine transformations to geometry entities.

    Supports non-uniform scaling (scale_x, scale_y), rotation around the origin
    or centroid in degrees, and linear translation (translate_x, translate_y).

    Args:
        request (TransformRequest): Entities and transformation parameters.

    Returns:
        TransformResponse: Transformed geometry entities and applied parameter records.

    Raises:
        HTTPException: 400 Bad Request if transform parameters are invalid.
        HTTPException: 500 Internal Server Error for unhandled exceptions.
    """
    try:
        return apply_transformations(request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transformation error: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply transformations: {str(e)}",
        )


@app.post(
    "/api/nest",
    summary="Nest Shapes on Sheet",
    response_model=NestResult,
    tags=["Nesting"],
)
async def nest(request: NestRequest) -> NestResult:
    """Arrange multiple geometric shapes onto a defined rectangular material sheet.

    Uses a greedy 2D shelf bin-packing algorithm with support for part spacing,
    sheet margins, and optional 90-degree rotations.

    Args:
        request (NestRequest): Shapes to nest, sheet dimensions, spacing, and rotation flag.

    Returns:
        NestResult: Placed shapes with coordinates, unplaced shape IDs, and utilization percentage.

    Raises:
        HTTPException: 400 Bad Request if sheet dimensions or spacing are invalid.
        HTTPException: 500 Internal Server Error for unhandled exceptions.
    """
    try:
        return nest_shapes(request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Nesting error: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to nest shapes: {str(e)}",
        )


@app.post(
    "/api/laser-parameters",
    summary="Configure Laser Parameters",
    response_model=LaserConfig,
    tags=["Laser Configuration"],
)
async def configure_laser_parameters(request: LaserConfigRequest) -> LaserConfig:
    """Create and validate a laser parameter configuration.

    Validates layer settings including feed rate (speed in mm/min), power percentage
    (0-100%), number of passes, optional pulse frequency, and maximum spindle/laser S-value.

    Args:
        request (LaserConfigRequest): Layer definitions and controller configuration.

    Returns:
        LaserConfig: Validated laser parameter configuration.

    Raises:
        HTTPException: 400 Bad Request if parameters or layer configurations are invalid.
        HTTPException: 500 Internal Server Error for unhandled exceptions.
    """
    try:
        return create_laser_config(request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Laser parameter validation error: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create laser configuration: {str(e)}",
        )


@app.get(
    "/api/laser-parameters/default",
    summary="Get Default Laser Parameters",
    response_model=LaserConfig,
    tags=["Laser Configuration"],
)
async def get_default_laser_parameters() -> LaserConfig:
    """Retrieve default laser configuration presets (Cut, Engrave, Score).

    Returns:
        LaserConfig: Default multi-layer laser configuration.
    """
    return get_default_config()


@app.post(
    "/api/gcode",
    summary="Generate G-Code",
    response_model=GCodeResult,
    tags=["G-Code Generation"],
)
async def generate_gcode_endpoint(request: GCodeRequest) -> GCodeResult:
    """Generate GRBL-compatible G-code from geometry entities and laser parameters.

    Produces standardized G-code with safety headers (G21, G90, M5), rapid traverse
    motions (G0), cutting motions (G1) with laser power (S-value) and feed rate (F-value),
    support for multi-pass cutting, and toolpath preview vectors.

    Args:
        request (GCodeRequest): Geometry entities, laser configuration, and selected layer.

    Returns:
        GCodeResult: Generated G-code text, total line count, estimated runtime,
                     toolpath preview segments, and any warnings.

    Raises:
        HTTPException: 400 Bad Request if input parameters or layer mapping are invalid.
        HTTPException: 500 Internal Server Error for unhandled exceptions.
    """
    try:
        return generate_gcode(request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"G-code generation error: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate G-code: {str(e)}",
        )
