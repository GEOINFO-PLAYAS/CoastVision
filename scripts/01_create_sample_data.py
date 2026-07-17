from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import LineString, box


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

CRS = "EPSG:32719"  # UTM 19S, util para Chile central.
NODATA = -9999.0


def write_raster(path: Path, array: np.ndarray, profile: dict) -> None:
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(array.astype("float32"), 1)


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    OUTPUTS_DIR.mkdir(exist_ok=True)

    width = 160
    height = 120
    pixel_size = 30
    x_min = 245_000
    y_max = 6_315_000
    transform = from_origin(x_min, y_max, pixel_size, pixel_size)

    rows, cols = np.indices((height, width))

    # Mascara ficticia: a la izquierda hay agua, a la derecha tierra.
    coast_position = 58 + 0.22 * rows + 6 * np.sin(rows / 12)
    water = cols < coast_position

    green = np.where(water, 0.42, 0.18)
    nir = np.where(water, 0.08, 0.46)

    # Agregamos variacion suave para que el ejemplo no sea plano.
    green += 0.03 * np.sin(cols / 10) + 0.01 * np.cos(rows / 8)
    nir += 0.04 * np.cos(cols / 14) - 0.01 * np.sin(rows / 9)

    dem = 5 + (cols - coast_position) * 1.4
    dem = np.clip(dem, 0, None)
    dem += 8 * np.sin(cols / 18) + 4 * np.cos(rows / 16)

    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "float32",
        "crs": CRS,
        "transform": transform,
        "nodata": NODATA,
        "compress": "deflate",
    }

    write_raster(DATA_DIR / "green.tif", green, profile)
    write_raster(DATA_DIR / "nir.tif", nir, profile)
    write_raster(DATA_DIR / "dem.tif", dem, profile)

    x_max = x_min + width * pixel_size
    y_min = y_max - height * pixel_size
    third = (y_max - y_min) / 3

    zones = gpd.GeoDataFrame(
        {
            "zona": ["norte", "centro", "sur"],
            "uso": ["playa", "urbano", "humedal"],
        },
        geometry=[
            box(x_min + 150, y_max - third + 150, x_max - 150, y_max - 150),
            box(x_min + 150, y_max - 2 * third + 150, x_max - 150, y_max - third - 150),
            box(x_min + 150, y_min + 150, x_max - 150, y_max - 2 * third - 150),
        ],
        crs=CRS,
    )
    zones.to_file(DATA_DIR / "zonas_costeras.gpkg", layer="zonas", driver="GPKG")

    line_points = []
    for row in range(0, height, 8):
        x = x_min + (58 + 0.22 * row + 6 * np.sin(row / 12)) * pixel_size
        y = y_max - row * pixel_size
        line_points.append((x, y))

    coastline = gpd.GeoDataFrame(
        {"nombre": ["linea_costa_ficticia"]},
        geometry=[LineString(line_points)],
        crs=CRS,
    )
    coastline.to_file(DATA_DIR / "linea_costa.geojson", driver="GeoJSON")

    print("Datos de ejemplo creados:")
    print(f"- {DATA_DIR / 'green.tif'}")
    print(f"- {DATA_DIR / 'nir.tif'}")
    print(f"- {DATA_DIR / 'dem.tif'}")
    print(f"- {DATA_DIR / 'zonas_costeras.gpkg'}")
    print(f"- {DATA_DIR / 'linea_costa.geojson'}")


if __name__ == "__main__":
    main()
