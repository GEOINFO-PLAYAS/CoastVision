from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterstats import zonal_stats


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
NODATA = -9999.0


def main() -> None:
    green_path = DATA_DIR / "green.tif"
    nir_path = DATA_DIR / "nir.tif"
    zones_path = DATA_DIR / "zonas_costeras.gpkg"

    if not green_path.exists() or not nir_path.exists() or not zones_path.exists():
        raise FileNotFoundError(
            "Faltan datos base. Ejecuta primero: python scripts\\01_create_sample_data.py"
        )

    OUTPUTS_DIR.mkdir(exist_ok=True)

    with rasterio.open(green_path) as green_src, rasterio.open(nir_path) as nir_src:
        green = green_src.read(1).astype("float32")
        nir = nir_src.read(1).astype("float32")
        profile = green_src.profile.copy()

    denominator = green + nir
    ndwi = np.full(green.shape, NODATA, dtype="float32")
    valid = denominator != 0
    ndwi[valid] = (green[valid] - nir[valid]) / denominator[valid]

    profile.update(dtype="float32", nodata=NODATA, compress="deflate")
    ndwi_path = OUTPUTS_DIR / "ndwi.tif"
    with rasterio.open(ndwi_path, "w", **profile) as dst:
        dst.write(ndwi, 1)

    zones = gpd.read_file(zones_path, layer="zonas")
    stats = zonal_stats(
        zones,
        ndwi_path,
        stats=["min", "mean", "max", "std"],
        nodata=NODATA,
    )
    stats_df = pd.DataFrame(stats).add_prefix("ndwi_")
    result = zones.join(stats_df)

    csv_path = OUTPUTS_DIR / "zonas_ndwi_stats.csv"
    gpkg_path = OUTPUTS_DIR / "zonas_ndwi_stats.gpkg"
    result.drop(columns="geometry").to_csv(csv_path, index=False)
    result.to_file(gpkg_path, layer="zonas_ndwi", driver="GPKG")

    print("Analisis NDWI completado:")
    print(f"- Raster NDWI: {ndwi_path}")
    print(f"- Tabla CSV:   {csv_path}")
    print(f"- Capa GPKG:   {gpkg_path}")
    print("\nResumen:")
    print(result[["zona", "uso", "ndwi_min", "ndwi_mean", "ndwi_max", "ndwi_std"]])


if __name__ == "__main__":
    main()
