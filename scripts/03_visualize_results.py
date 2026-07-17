from __future__ import annotations

from pathlib import Path

import contextily as ctx
import folium
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.plot import plotting_extent


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"


def color_for_ndwi(value: float) -> str:
    if pd.isna(value):
        return "#9ca3af"
    if value >= 0.35:
        return "#2563eb"
    if value >= 0.05:
        return "#22c55e"
    return "#f97316"


def main() -> None:
    ndwi_path = OUTPUTS_DIR / "ndwi.tif"
    stats_path = OUTPUTS_DIR / "zonas_ndwi_stats.gpkg"

    if not ndwi_path.exists() or not stats_path.exists():
        raise FileNotFoundError(
            "Faltan resultados. Ejecuta primero: python scripts\\02_ndwi_zonal_stats.py"
        )

    zones = gpd.read_file(stats_path, layer="zonas_ndwi")

    with rasterio.open(ndwi_path) as src:
        ndwi = src.read(1)
        ndwi = np.where(ndwi == src.nodata, np.nan, ndwi)
        extent = plotting_extent(src)

    fig, ax = plt.subplots(figsize=(9, 6))
    image = ax.imshow(ndwi, extent=extent, cmap="BrBG", vmin=-1, vmax=1)
    zones.boundary.plot(ax=ax, color="black", linewidth=1.2)
    zones.plot(
        ax=ax,
        column="ndwi_mean",
        cmap="Blues",
        alpha=0.25,
        edgecolor="black",
        legend=True,
    )
    fig.colorbar(image, ax=ax, label="NDWI")
    ax.set_title("NDWI ficticio y zonas costeras")
    ax.set_xlabel("Este UTM 19S")
    ax.set_ylabel("Norte UTM 19S")
    fig.tight_layout()

    png_path = OUTPUTS_DIR / "mapa_ndwi_zonas.png"
    fig.savefig(png_path, dpi=160)
    plt.close(fig)

    # Contextily se usa aqui de forma opcional. Si falla por conexion, el flujo sigue.
    basemap_path = OUTPUTS_DIR / "zonas_contextily.png"
    try:
        web = zones.to_crs(epsg=3857)
        fig, ax = plt.subplots(figsize=(9, 6))
        web.plot(ax=ax, column="ndwi_mean", alpha=0.45, edgecolor="black", legend=True)
        ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik)
        ax.set_axis_off()
        ax.set_title("Zonas con mapa base")
        fig.tight_layout()
        fig.savefig(basemap_path, dpi=160)
        plt.close(fig)
        print(f"- Mapa con Contextily: {basemap_path}")
    except Exception as exc:
        print(f"- Contextily no pudo descargar mapa base: {exc}")

    zones_wgs84 = zones.to_crs(epsg=4326)
    center = zones_wgs84.geometry.union_all().centroid
    fmap = folium.Map(location=[center.y, center.x], zoom_start=13, tiles="OpenStreetMap")

    def style(feature: dict) -> dict:
        value = feature["properties"].get("ndwi_mean")
        return {
            "fillColor": color_for_ndwi(value),
            "color": "#111827",
            "weight": 1,
            "fillOpacity": 0.55,
        }

    folium.GeoJson(
        zones_wgs84,
        name="Zonas NDWI",
        style_function=style,
        tooltip=folium.GeoJsonTooltip(
            fields=["zona", "uso", "ndwi_mean", "ndwi_min", "ndwi_max"],
            aliases=["Zona", "Uso", "NDWI medio", "NDWI min", "NDWI max"],
            localize=True,
        ),
    ).add_to(fmap)
    folium.LayerControl().add_to(fmap)

    html_path = OUTPUTS_DIR / "mapa_interactivo.html"
    fmap.save(html_path)

    print("Visualizaciones creadas:")
    print(f"- Mapa PNG:  {png_path}")
    print(f"- Mapa HTML: {html_path}")


if __name__ == "__main__":
    main()
