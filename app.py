from __future__ import annotations

import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path
from urllib.parse import quote

import folium
import streamlit as st
from folium.plugins import Fullscreen, MeasureControl, MiniMap
from streamlit_folium import st_folium


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from coastvision.geometry import (  # noqa: E402
    BASE_YEAR,
    CENTER_LAT,
    CENTER_LON,
    DEFAULT_RETREAT_RATE,
    RISK_STYLE,
    build_demo_layers,
    evaluate_location,
)
try:
    from coastvision.scientific import (  # noqa: E402
        assess_nearest_infrastructure,
        scientific_pipeline_ready,
    )
    SCIENTIFIC_MODULE_ERROR: str | None = None
except ModuleNotFoundError as exc:  # permite arrancar copias antiguas incompletas en modo demo
    SCIENTIFIC_MODULE_ERROR = (
        "Falta src/coastvision/scientific.py. Extrae el ZIP v10 completo o copia ese archivo "
        f"junto a app.py ({exc})."
    )

    def scientific_pipeline_ready(*args, **kwargs):  # type: ignore[no-untyped-def]
        return False, [SCIENTIFIC_MODULE_ERROR]

    def assess_nearest_infrastructure(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError(SCIENTIFIC_MODULE_ERROR)
from coastvision.visual_features import (  # noqa: E402
    interpolate_shorelines,
    shoreline_displacement_m,
)


st.set_page_config(page_title="CoastVision MVP", page_icon="🌊", layout="wide")
st.markdown(
    """
    <style>
      /* Presentación limpia: ocultar controles de alojamiento propios de Streamlit. */
      .stAppDeployButton,
      [data-testid="stToolbarActions"],
      [data-testid="stDecoration"],
      [data-testid="stStatusWidget"],
      #MainMenu,
      footer {display:none !important; visibility:hidden !important;}
      [data-testid="stToolbar"] {background:transparent !important;}
      /* La franja mínima conserva los controles de cerrar y reabrir el panel lateral. */
      header[data-testid="stHeader"] {
        height:3rem !important;
        min-height:3rem !important;
        background:transparent !important;
      }
      [data-testid="stSidebarCollapseButton"],
      [data-testid="stSidebarCollapseButton"] button,
      [data-testid="stExpandSidebarButton"],
      [data-testid="stExpandSidebarButton"] button,
      [data-testid="stSidebarCollapsedControl"],
      [data-testid="stSidebarCollapsedControl"] button {
        display:flex !important;
        visibility:visible !important;
        opacity:1 !important;
        pointer-events:auto !important;
        z-index:1000001 !important;
      }
      .block-container {padding-top: 1.1rem; padding-bottom: 2rem;}
      [data-testid="stMetric"] {border:1px solid rgba(128,128,128,.28); border-radius:12px; padding:12px;}
      .cv-card {border:1px solid rgba(128,128,128,.28); border-radius:12px; padding:16px; margin-bottom:12px;}
      .cv-note {border-left:4px solid #b97512; padding:10px 14px; border-radius:6px; background:rgba(185,117,18,.08);}
      .cv-title {font-size:2.2rem; font-weight:800; letter-spacing:-0.03em;}
      .cv-subtitle {opacity:.72; margin-top:-10px;}
    </style>
    """,
    unsafe_allow_html=True,
)


def maps_url(lat: float, lon: float, mode: str) -> str:
    if mode == "street":
        return f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={lat:.6f}%2C{lon:.6f}"
    if mode == "satellite":
        return (
            "https://www.google.com/maps/@?api=1&map_action=map&"
            f"center={lat:.6f}%2C{lon:.6f}&zoom=18&basemap=satellite"
        )
    return f"https://earth.google.com/web/search/{quote(f'{lat:.6f},{lon:.6f}')}"


def format_elevation(value: float | None) -> str:
    return "Sin dato" if value is None else f"{value:.0f} m s.n.m."


def load_json_artifact(path: Path) -> tuple[dict[str, object], str | None]:
    """Lee un artefacto JSON sin convertir su mera existencia en evidencia positiva."""
    if not path.exists():
        return {}, "archivo ausente"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, f"archivo no legible ({exc.__class__.__name__})"
    if not isinstance(payload, dict):
        return {}, "contenido JSON no es un objeto"
    return payload, None


def load_csv_artifact(path: Path) -> tuple[list[dict[str, str]], str | None]:
    """Lee filas CSV conservando un error verificable cuando el archivo no sirve."""
    if not path.exists():
        return [], "archivo ausente"
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle)), None
    except (OSError, UnicodeError, csv.Error) as exc:
        return [], f"archivo no legible ({exc.__class__.__name__})"


def load_geojson_feature_collection(path: Path) -> dict[str, object] | None:
    """Carga una capa OSM ya evaluada sin convertir su ausencia en datos demo."""
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
        return None
    return payload


def load_scientific_bundle() -> dict[str, object]:
    """Carga la cadena científica y habilita el semáforo solo si es trazable."""

    paths = {
        "pipeline": ROOT / "outputs" / "multitemporal" / "pipeline_summary.json",
        "shorelines": ROOT / "outputs" / "multitemporal" / "shorelines_2016_2026_fes2014.geojson",
        "rates": ROOT / "outputs" / "multitemporal" / "transect_rates.geojson",
        "tides": ROOT / "outputs" / "multitemporal" / "tide_corrections.csv",
        "storm": ROOT / "outputs" / "multitemporal" / "storm_correlation.json",
        "infrastructure": ROOT / "outputs" / "infrastructure_risk" / "summary.json",
        "buildings": ROOT / "outputs" / "infrastructure_risk" / "buildings_risk.geojson",
        "roads": ROOT / "outputs" / "infrastructure_risk" / "roads_risk.geojson",
    }
    pipeline, pipeline_error = load_json_artifact(paths["pipeline"])
    infrastructure, infrastructure_error = load_json_artifact(paths["infrastructure"])
    storm, storm_error = load_json_artifact(paths["storm"])
    shorelines = load_geojson_feature_collection(paths["shorelines"])
    rates = load_geojson_feature_collection(paths["rates"])
    buildings = load_geojson_feature_collection(paths["buildings"])
    roads = load_geojson_feature_collection(paths["roads"])
    tide_rows, tide_error = load_csv_artifact(paths["tides"])
    ready, problems = scientific_pipeline_ready(
        pipeline,
        infrastructure,
        shorelines_exist=bool(shorelines),
        rates_exist=bool(rates),
        buildings_exist=bool(buildings),
        roads_exist=bool(roads),
    )
    valid_rates = [
        feature
        for feature in (rates or {}).get("features", [])
        if feature.get("properties", {}).get("lrr_m_per_year") is not None
    ]
    corrected_years = sorted(
        int(year) for year in pipeline.get("fes2014_corrected_years", []) if str(year).isdigit()
    )
    risk_counts = {"critico": 0, "moderado": 0, "bajo": 0, "sin_clasificar": 0}
    for collection in (buildings, roads):
        for feature in (collection or {}).get("features", []):
            level = str(feature.get("properties", {}).get("risk_level") or "sin_clasificar")
            risk_counts[level] = risk_counts.get(level, 0) + 1
    return {
        "ready": ready,
        "problems": problems,
        "paths": paths,
        "pipeline": pipeline,
        "infrastructure_summary": infrastructure,
        "storm": storm,
        "shorelines": shorelines,
        "rates": rates,
        "tides": tide_rows,
        "buildings": buildings,
        "roads": roads,
        "corrected_years": corrected_years,
        "valid_rate_count": len(valid_rates),
        "risk_counts": risk_counts,
        "errors": {
            key: value
            for key, value in {
                "pipeline": pipeline_error,
                "infrastructure": infrastructure_error,
                "storm": storm_error,
                "tides": tide_error,
            }.items()
            if value
        },
    }


def risk_color(value: object) -> str:
    normalized = str(value or "").casefold()
    if not normalized:
        return "#62727D"
    if "crit" in normalized:
        return "#B42318"
    if "moder" in normalized or "precauc" in normalized:
        return "#B97512"
    if "baj" in normalized or "low" in normalized:
        return "#2E7D55"
    return "#62727D"

def add_cartographic_elements(fmap: folium.Map, layers: dict[str, object]) -> None:
    """Agrega al lienzo los siete elementos cartográficos exigidos por la pauta."""
    provenance = layers.get("provenance", {})
    map_date = str(provenance.get("generated_at") or provenance.get("created_at") or "2026-07-16")[:10]
    scientific_mode = bool(layers.get("scientific_mode"))
    scenario_year = int(layers.get("display_year", layers["year"]))
    map_title = (
        f"Cambio costero Sentinel-2/FES2014 · Playa Grande · línea {scenario_year}"
        if scientific_mode
        else f"Erosión y riesgo costero · Playa Grande de Cartagena · escenario {scenario_year}"
    )
    legend_lines = (
        f"""
      <span class="cv-chip" style="background:#0E7EA2"></span>Línea FES2014 2016<br>
      <span class="cv-chip" style="background:#B42318"></span>Línea FES2014 {scenario_year}<br>
      <span class="cv-chip" style="background:#64748B"></span>Otros años corregidos<br>
      <span class="cv-chip" style="background:#7C3AED"></span>Transectos/LRR<br>
      <span class="cv-chip cv-dot" style="background:#C93131"></span>OSM crítico (&lt;10 años)<br>
      <span class="cv-chip cv-dot" style="background:#E3A008"></span>OSM precaución (10–30 años)<br>
      <span class="cv-chip cv-dot" style="background:#2E8B57"></span>OSM bajo (&gt;30 años o LRR≤0)<br>
        """
        if scientific_mode
        else f"""
      <span class="cv-chip" style="background:#B97512"></span>Línea base OSM 2026<br>
      <span class="cv-chip" style="background:#B42318"></span>Línea proyectada {scenario_year}<br>
      <span class="cv-chip cv-dot" style="background:#C93131"></span>Riesgo crítico<br>
      <span class="cv-chip cv-dot" style="background:#E3A008"></span>Precaución<br>
      <span class="cv-chip cv-dot" style="background:#2E8B57"></span>Riesgo bajo<br>
      <span class="cv-chip" style="background:#355F8A"></span>Transectos<br>
      <span class="cv-chip" style="background:#6B7280"></span>Inventario OSM sin clasificar<br>
        """
    )
    source_line = (
        "Sentinel-2; FES2014b; OSM · Equipo CoastVision USACH"
        if scientific_mode
        else "OSM; Copernicus GLO-90 · Equipo CoastVision USACH"
    )
    controls = f"""
    <style>
      .cv-map-box {{
        position: fixed; z-index: 9998; background: rgba(255,255,255,.96);
        border: 1px solid rgba(23,63,95,.25); border-radius: 7px;
        box-shadow: 0 1px 5px rgba(0,0,0,.28); color: #173F5F;
        font-family: Arial, sans-serif;
      }}
      .cv-map-title {{top: 10px; left: 50%; transform: translateX(-50%); padding: 8px 14px;
        font-size: 14px; font-weight: 800; text-align: center; white-space: nowrap;}}
      .cv-map-north {{top: 72px; right: 10px; width: 38px; padding: 5px 2px;
        font-size: 12px; font-weight: 800; text-align: center; line-height: 1;}}
      .cv-map-north span {{font-size: 25px; display: block; line-height: 23px;}}
      .cv-map-legend {{right: 10px; bottom: 24px; width: 220px; padding: 9px 10px;
        font-size: 10px; line-height: 1.35;}}
      .cv-chip {{display:inline-block; width:12px; height:3px; margin-right:5px;
        vertical-align:middle; border-radius:2px;}}
      .cv-dot {{height:8px; border-radius:50%;}}
    </style>
    <div class="cv-map-box cv-map-title">
      {map_title}
    </div>
    <div class="cv-map-box cv-map-north" aria-label="Norte"><span>↑</span>N</div>
    <div class="cv-map-box cv-map-legend">
      <b>Leyenda</b><br>
      {legend_lines}
      <hr style="margin:5px 0;border:0;border-top:1px solid #d7dee2">
      <b>Fuente/autor:</b> {source_line}<br>
      <b>CRS/Proyección:</b> mapa EPSG:3857; análisis UTM 19S (EPSG:32719)<br>
      <b>Fecha:</b> {map_date}
    </div>
    """
    fmap.get_root().html.add_child(folium.Element(controls))


def make_scientific_map(
    layers: dict[str, object],
    selected: tuple[float, float],
    visibility: dict[str, bool],
) -> folium.Map:
    """Mapa cuyo semáforo consume exclusivamente artefactos del pipeline."""

    fmap = folium.Map(location=[CENTER_LAT, CENTER_LON], zoom_start=15, tiles=None, control_scale=True)
    folium.TileLayer("OpenStreetMap", name="Calles OSM", show=True).add_to(fmap)
    folium.TileLayer(
        tiles=(
            "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/"
            "MapServer/tile/{z}/{y}/{x}"
        ),
        attr="Esri, Maxar, Earthstar Geographics",
        name="Satélite",
        show=False,
    ).add_to(fmap)

    study_area = layers["study_area"].geometry.iloc[0]
    folium.GeoJson(
        study_area.__geo_interface__,
        name="Área de medición",
        style_function=lambda _: {
            "fillColor": "#2F5964", "color": "#2F5964", "weight": 2,
            "dashArray": "8 6", "fillOpacity": 0.025,
        },
    ).add_to(fmap)

    scientific = layers["scientific"]
    selected_year = int(layers["display_year"])
    shorelines = scientific.get("shorelines") or {}
    if visibility.get("scientific_shorelines", True):
        shoreline_group = folium.FeatureGroup(
            name="Líneas costeras Sentinel-2 corregidas FES2014",
            show=True,
        )
        for feature in shorelines.get("features", []):
            properties = feature.get("properties", {})
            feature_year = int(properties.get("year", 0))
            if feature_year == selected_year:
                color, weight, opacity = "#B42318", 6, 1.0
            elif feature_year == 2016:
                color, weight, opacity = "#0E7EA2", 5, 0.95
            elif feature_year == 2026:
                color, weight, opacity = "#B97512", 5, 0.95
            else:
                color, weight, opacity = "#64748B", 2, 0.48
            tooltip = (
                f"Costa {feature_year} · {properties.get('scene_count', 0)} escena(s) · "
                f"{properties.get('processing_level', 'sin nivel')} · FES2014"
            )
            folium.GeoJson(
                feature,
                tooltip=tooltip,
                style_function=lambda _, color=color, weight=weight, opacity=opacity: {
                    "color": color, "weight": weight, "opacity": opacity,
                },
            ).add_to(shoreline_group)
        shoreline_group.add_to(fmap)

    rates = scientific.get("rates") or {}
    if visibility.get("scientific_rates", True) and rates.get("features"):
        rate_group = folium.FeatureGroup(name="Transectos y tasas LRR", show=True)
        for feature in rates.get("features", []):
            properties = feature.get("properties", {})
            rate = properties.get("lrr_m_per_year")
            if rate is None:
                color, opacity = "#9CA3AF", 0.35
                rate_label = "sin LRR"
            else:
                rate = float(rate)
                color, opacity = ("#B42318", 0.95) if rate > 0 else ("#2563EB", 0.78)
                rate_label = f"{rate:+.3f} m/año"
            tooltip = (
                f"{properties.get('transect_id', 'sin ID')} · LRR {rate_label} · "
                f"n={properties.get('n_observations', 0)}/11 · "
                f"R²={properties.get('lrr_r2') if properties.get('lrr_r2') is not None else 's/d'}"
            )
            folium.GeoJson(
                feature,
                tooltip=tooltip,
                style_function=lambda _, color=color, opacity=opacity: {
                    "color": color, "weight": 2, "opacity": opacity,
                },
            ).add_to(rate_group)
        rate_group.add_to(fmap)

    if visibility.get("real_infrastructure", True):
        for kind, label in (
            ("buildings", "Semáforo pipeline: edificaciones OSM"),
            ("roads", "Semáforo pipeline: caminos OSM"),
        ):
            feature_collection = scientific.get(kind)
            if not feature_collection or not feature_collection.get("features"):
                continue
            group = folium.FeatureGroup(name=label, show=True)
            folium.GeoJson(
                feature_collection,
                style_function=lambda feature, feature_kind=kind: {
                    "color": risk_color(feature.get("properties", {}).get("risk_level")),
                    "weight": 4 if feature_kind == "roads" else 1,
                    "fillColor": risk_color(feature.get("properties", {}).get("risk_level")),
                    "fillOpacity": 0.72 if feature_kind == "buildings" else 0.0,
                    "opacity": 0.88,
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=[
                        "risk_level", "distance_to_shoreline_m", "erosion_rate_m_per_year",
                        "nearest_transect_id", "years_to_impact",
                    ],
                    aliases=[
                        "Semáforo", "Distancia a costa 2026 (m)", "LRR local (m/año)",
                        "Transecto", "Años hasta impacto",
                    ],
                    localize=True,
                    sticky=False,
                ),
            ).add_to(group)
            group.add_to(fmap)

    if visibility.get("elevation", False):
        sample_group = folium.FeatureGroup(name="Muestras de elevación DEM", show=True)
        sample_colors = {50: "#90BE6D", 150: "#43AA8B", 250: "#277DA1"}
        for _, row in layers["elevation_samples"].iterrows():
            folium.CircleMarker(
                location=[row.geometry.y, row.geometry.x],
                radius=4,
                color=sample_colors[int(row["offset_m"])],
                fill=True,
                fill_opacity=0.9,
                tooltip=f"{row['station_id']} · {row['offset_m']} m · {format_elevation(row['elevation_m'])}",
            ).add_to(sample_group)
        sample_group.add_to(fmap)

    folium.Marker(
        location=list(selected),
        tooltip="Clic de consulta; el panel devuelve la infraestructura evaluada más cercana",
        icon=folium.Icon(color="darkblue", icon="info-sign"),
    ).add_to(fmap)
    fmap.fit_bounds(layers["coverage"]["bounds"], padding=(22, 22), max_zoom=16)
    folium.LayerControl(collapsed=True).add_to(fmap)
    Fullscreen(position="topleft", title="Pantalla completa").add_to(fmap)
    MeasureControl(position="topleft", primary_length_unit="meters").add_to(fmap)
    MiniMap(toggle_display=True).add_to(fmap)
    add_cartographic_elements(fmap, layers)
    return fmap


def make_map(
    layers: dict[str, object],
    selected: tuple[float, float],
    *,
    show_layers: dict[str, bool] | None = None,
    animation_line=None,
    animation_year: int | None = None,
    animation_progress: float | None = None,
) -> folium.Map:
    visibility = {
        "shorelines": True,
        "buildings": True,
        "transects": True,
        "elevation": False,
        "animation": True,
        "infrastructure_inventory": True,
        "real_infrastructure": True,
        "scientific_shorelines": True,
        "scientific_rates": True,
    }
    if show_layers:
        visibility.update(show_layers)
    if layers.get("scientific_mode"):
        return make_scientific_map(layers, selected, visibility)
    fmap = folium.Map(location=[CENTER_LAT, CENTER_LON], zoom_start=15, tiles=None, control_scale=True)
    folium.TileLayer("OpenStreetMap", name="Calles OSM", show=True).add_to(fmap)
    folium.TileLayer(
        tiles=(
            "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/"
            "MapServer/tile/{z}/{y}/{x}"
        ),
        attr="Esri, Maxar, Earthstar Geographics",
        name="Satélite",
        show=False,
    ).add_to(fmap)

    study_area = layers["study_area"].geometry.iloc[0]
    folium.GeoJson(
        study_area.__geo_interface__,
        name="Límite del área de medición",
        style_function=lambda _: {
            "fillColor": "#2F5964",
            "color": "#2F5964",
            "weight": 2,
            "dashArray": "8 6",
            "fillOpacity": 0.025,
        },
    ).add_to(fmap)

    band_colors = {key: value[1] for key, value in RISK_STYLE.items()}
    band_opacity = {"critico": 0.40, "precaucion": 0.32, "bajo": 0.19}
    for _, row in layers["risk_bands"].iterrows():
        level = row["nivel"]
        folium.GeoJson(
            row.geometry.__geo_interface__,
            name=row["label"],
            tooltip=row["label"],
            style_function=lambda _, color=band_colors[level], opacity=band_opacity[level]: {
                "fillColor": color,
                "color": color,
                "weight": 2,
                "fillOpacity": opacity,
            },
        ).add_to(fmap)

    impact_geometry = layers["impact_zone"].geometry.iloc[0]
    if not impact_geometry.is_empty:
        impact_name = layers["impact_zone"].iloc[0]["name"]
        folium.GeoJson(
            impact_geometry.__geo_interface__,
            name=impact_name,
            tooltip=f"{impact_name}: {layers['retreat_m']:.1f} m",
            style_function=lambda _: {
                "fillColor": "#6F0018",
                "color": "#6F0018",
                "weight": 2,
                "fillOpacity": 0.62,
            },
        ).add_to(fmap)

    comparison_group = folium.FeatureGroup(name="Comparación del límite de 60 m", show=True)
    for _, row in layers["risk_boundaries"].iterrows():
        is_base = row["type"] == "base"
        label = (
            "Límite de precaución 2026"
            if is_base
            else f"Límite de precaución {layers['year']}"
        )
        folium.GeoJson(
            row.geometry.__geo_interface__,
            tooltip=label,
            style_function=lambda _, is_base=is_base: {
                "color": "#4E5968" if is_base else "#B42318",
                "weight": 3,
                "dashArray": "8 6" if is_base else None,
                "opacity": 0.95,
            },
        ).add_to(comparison_group)
    comparison_group.add_to(fmap)

    line_styles = {
        "historica": ("#0E7EA2", "Referencia histórica 2017 (demo)", "7 5"),
        "actual": ("#B97512", "Referencia base OSM (año cero 2026)", None),
        "proyectada": ("#B42318", f"Línea proyectada {layers['year']}", "5 4"),
    }
    shoreline_group = folium.FeatureGroup(name="Líneas de costa comparadas", show=True)
    for _, row in layers["shorelines"].iterrows():
        color, name, dash = line_styles[row["type"]]
        style = {"color": color, "weight": 4}
        if dash:
            style["dashArray"] = dash
        folium.GeoJson(
            row.geometry.__geo_interface__,
            name=name,
            style_function=lambda _, style=style: style,
        ).add_to(shoreline_group)
    if animation_line is not None and visibility["animation"]:
        label_year = animation_year if animation_year is not None else 2026
        label_progress = (
            f" ({animation_progress * 100:.0f}% desde 2017)"
            if animation_progress is not None
            else ""
        )
        folium.GeoJson(
            animation_line.__geo_interface__,
            name=f"Interpolación demostrativa {label_year}",
            style_function=lambda _: {"color": "#F97316", "weight": 7, "opacity": 1.0},
            tooltip=f"Interpolación demostrativa {label_year}{label_progress}",
        ).add_to(shoreline_group)
    if visibility["shorelines"]:
        shoreline_group.add_to(fmap)

    transect_group = folium.FeatureGroup(name="Transectos de medición", show=True)
    for _, row in layers["transects"].iterrows():
        popup = (
            f"<b>{row['station_id']}</b><br>Progresiva desde el norte: {row['alongshore_m']:.0f} m"
            f"<br>50 m mar adentro + 260 m tierra adentro"
            f"<br>Longitud total: {row['length_m']:.0f} m"
        )
        folium.GeoJson(
            row.geometry.__geo_interface__,
            style_function=lambda _: {"color": "#355F8A", "weight": 2, "opacity": 0.82},
            tooltip=f"Transecto {row['station_id']}",
            popup=folium.Popup(popup, max_width=300),
        ).add_to(transect_group)
    if visibility["transects"]:
        transect_group.add_to(fmap)

    sample_group = folium.FeatureGroup(name="Muestras de elevación DEM", show=False)
    sample_colors = {50: "#90BE6D", 150: "#43AA8B", 250: "#277DA1"}
    for _, row in layers["elevation_samples"].iterrows():
        elevation = format_elevation(row["elevation_m"])
        folium.CircleMarker(
            location=[row.geometry.y, row.geometry.x],
            radius=4,
            color=sample_colors[int(row["offset_m"])],
            fill=True,
            fill_opacity=0.9,
            tooltip=f"{row['station_id']} · {row['offset_m']} m · {elevation}",
        ).add_to(sample_group)
    if visibility["elevation"]:
        sample_group.add_to(fmap)

    buildings = folium.FeatureGroup(name="Edificaciones demostrativas", show=False)
    for _, row in layers["buildings"].iterrows():
        popup = (
            f"<b>{row['predio_id']}</b><br>Riesgo: {row['riesgo']}"
            f"<br>Margen firmado: {row['margen_firmado_m']:+.1f} m"
            f"<br>Alcanzado: {'sí' if row['alcanzado'] else 'no'}"
        )
        folium.GeoJson(
            row.geometry.__geo_interface__,
            style_function=lambda _, color=row["color"]: {
                "fillColor": color,
                "color": "#ffffff",
                "weight": 1,
                "fillOpacity": 0.84,
            },
            tooltip=row["predio_id"],
            popup=folium.Popup(popup, max_width=280),
        ).add_to(buildings)
    if visibility["buildings"]:
        buildings.add_to(fmap)

    real_infrastructure = layers.get("infrastructure_real", {})
    for kind, label, color in (
        ("buildings", "Edificaciones OSM evaluadas", "#7C3AED"),
        ("roads", "Caminos OSM evaluados", "#0F766E"),
    ):
        feature_collection = real_infrastructure.get(kind)
        if not visibility["real_infrastructure"] or not feature_collection:
            continue
        features = feature_collection.get("features", [])
        if not features:
            continue
        group = folium.FeatureGroup(name=label, show=False)
        folium.GeoJson(
            feature_collection,
            style_function=lambda feature, default_color=color, feature_kind=kind: {
                "color": risk_color(feature.get("properties", {}).get("risk_level"))
                if feature.get("properties", {}).get("risk_level")
                else default_color,
                "weight": 3 if feature_kind == "roads" else 1,
                "fillColor": risk_color(feature.get("properties", {}).get("risk_level")),
                "fillOpacity": 0.65 if feature_kind == "buildings" else 0.0,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=["risk_level", "distance_to_shoreline_m", "years_to_impact"],
                aliases=["Riesgo", "Distancia a costa (m)", "Años hasta impacto"],
                localize=True,
                sticky=False,
            ),
        ).add_to(group)
        group.add_to(fmap)

    infrastructure_inventory = layers.get("infrastructure_inventory", {})
    for kind, label, color, tooltip_fields, tooltip_aliases in (
        (
            "buildings",
            "Inventario OSM: edificaciones (sin riesgo)",
            "#6B7280",
            ["osm_id", "name", "building"],
            ["OSM ID", "Nombre", "Tipo de edificio"],
        ),
        (
            "roads",
            "Inventario OSM: caminos (sin riesgo)",
            "#475569",
            ["osm_id", "name", "highway", "surface"],
            ["OSM ID", "Nombre", "Tipo de vía", "Superficie"],
        ),
    ):
        feature_collection = infrastructure_inventory.get(kind)
        if not visibility["infrastructure_inventory"] or not feature_collection:
            continue
        if not feature_collection.get("features", []):
            continue
        group = folium.FeatureGroup(name=label, show=False)
        folium.GeoJson(
            feature_collection,
            style_function=lambda _, feature_kind=kind, default_color=color: {
                "color": default_color,
                "weight": 2 if feature_kind == "roads" else 1,
                "fillColor": default_color,
                "fillOpacity": 0.32 if feature_kind == "buildings" else 0.0,
                "dashArray": "5 4" if feature_kind == "roads" else None,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=tooltip_fields,
                aliases=tooltip_aliases,
                localize=True,
                sticky=False,
            ),
        ).add_to(group)
        group.add_to(fmap)

    station_group = folium.FeatureGroup(name="Estaciones principales", show=True)
    for _, row in layers["stations"].iterrows():
        slope = "Sin dato" if row["slope_pct_50_250"] is None else f"{row['slope_pct_50_250']:.1f}%"
        popup = (
            f"<b>Estación {row['station_id']}</b>"
            f"<br>Latitud: {row['latitude']:.6f}"
            f"<br>Longitud: {row['longitude']:.6f}"
            f"<br>Progresiva N→S: {row['alongshore_m']:.0f} m"
            f"<br>Cota a 50 m: {format_elevation(row['elevation_50m'])}"
            f"<br>Cota a 150 m: {format_elevation(row['elevation_150m'])}"
            f"<br>Cota a 250 m: {format_elevation(row['elevation_250m'])}"
            f"<br>Pendiente DEM 50-250 m: {slope}"
        )
        folium.Marker(
            location=[row.geometry.y, row.geometry.x],
            tooltip=f"{row['station_id']} · lat {row['latitude']:.6f}",
            popup=folium.Popup(popup, max_width=320),
            icon=folium.DivIcon(
                icon_size=(34, 24),
                icon_anchor=(17, 12),
                html=(
                    "<div style='background:#173F5F;color:white;border:2px solid white;"
                    "border-radius:12px;text-align:center;font:700 11px/20px sans-serif;"
                    "width:34px;height:22px;box-shadow:0 1px 3px rgba(0,0,0,.35)'>"
                    f"{row['station_id']}</div>"
                ),
            ),
        ).add_to(station_group)
    station_group.add_to(fmap)

    folium.Marker(
        location=list(selected),
        tooltip="Punto evaluado",
        icon=folium.Icon(color="darkblue", icon="info-sign"),
    ).add_to(fmap)

    fmap.fit_bounds(layers["coverage"]["bounds"], padding=(22, 22), max_zoom=16)
    folium.LayerControl(collapsed=True).add_to(fmap)
    Fullscreen(position="topleft", title="Pantalla completa").add_to(fmap)
    MeasureControl(position="topleft", primary_length_unit="meters").add_to(fmap)
    MiniMap(toggle_display=True).add_to(fmap)
    add_cartographic_elements(fmap, layers)
    return fmap


real_infrastructure_paths = {
    "buildings": ROOT / "outputs" / "infrastructure_risk" / "buildings_risk.geojson",
    "roads": ROOT / "outputs" / "infrastructure_risk" / "roads_risk.geojson",
}
real_infrastructure_available = all(path.exists() for path in real_infrastructure_paths.values())
infrastructure_inventory_paths = {
    "buildings": ROOT / "data" / "infrastructure" / "buildings_osm.geojson",
    "roads": ROOT / "data" / "infrastructure" / "roads_osm.geojson",
}
infrastructure_inventory_available = all(
    path.exists() for path in infrastructure_inventory_paths.values()
)
scientific_bundle = load_scientific_bundle()

st.markdown('<div class="cv-title">CoastVision</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="cv-subtitle">Red de medición costera para Playa Grande de Cartagena</div>',
    unsafe_allow_html=True,
)
with st.sidebar:
    st.header("Modo de análisis")
    mode_options = []
    if scientific_bundle["ready"]:
        mode_options.append("Científico FES2014 + LRR")
    mode_options.append("Escenario exploratorio manual")
    selected_mode = st.radio("Fuente del semáforo", mode_options, index=0)
    scientific_mode = selected_mode.startswith("Científico")

    if scientific_mode:
        years = scientific_bundle["corrected_years"]
        year = st.select_slider(
            "Línea costera destacada",
            options=years,
            value=max(years),
            help="Cada opción es una línea anual observada por Sentinel-2 y corregida con FES2014.",
        )
        retreat_rate = float(DEFAULT_RETREAT_RATE)
        comparison_year = year
        show_shorelines = st.checkbox("11 líneas costeras FES2014", value=True)
        show_transects = st.checkbox("Transectos con LRR", value=True)
        show_elevation = st.checkbox("Muestras DEM", value=False)
        show_real_infrastructure = st.checkbox("Semáforo OSM conectado", value=True)
        show_buildings = False
        show_infrastructure_inventory = False
        show_animation = False
        counts = scientific_bundle["risk_counts"]
        st.markdown("**Resultado del screening a 30 años**")
        st.caption(
            f"Crítico: {counts.get('critico', 0)} · Precaución: {counts.get('moderado', 0)} · "
            f"Bajo: {counts.get('bajo', 0)}."
        )
    else:
        year = st.slider("Año de evaluación", BASE_YEAR, 2040, 2035, 1)
        retreat_rate = st.slider(
            "Tasa de retroceso demostrativa (m/año)",
            min_value=0.5,
            max_value=3.0,
            value=float(DEFAULT_RETREAT_RATE),
            step=0.1,
            help="Supuesto editable; no proviene del pipeline científico.",
        )
        retreat_preview = max(0, year - BASE_YEAR) * retreat_rate
        st.caption(
            f"Demo: {retreat_preview:.1f} m alcanzados · rojo hasta {retreat_preview + 25:.1f} m · "
            f"ámbar hasta {retreat_preview + 60:.1f} m."
        )
        show_shorelines = st.checkbox("Líneas demostrativas", value=True)
        show_buildings = st.checkbox("Edificaciones demostrativas", value=False)
        show_transects = st.checkbox("Transectos de medición", value=True)
        show_elevation = st.checkbox("Muestras DEM", value=False)
        show_infrastructure_inventory = st.checkbox(
            "Inventario OSM sin clasificar",
            value=False,
            disabled=not infrastructure_inventory_available,
        )
        show_real_infrastructure = st.checkbox(
            "Infraestructura evaluada por pipeline",
            value=False,
            disabled=not real_infrastructure_available,
        )
        show_animation = st.checkbox("Interpolación demostrativa", value=True)
        comparison_year = st.slider(
            "Año dentro de la comparación demo",
            min_value=2017,
            max_value=2026,
            value=2021,
            step=1,
            disabled=not show_animation,
        )
        st.warning("Este modo no se usa para afirmar riesgo real; conserva el ejercicio didáctico original.")

demo_layer_year = year if not scientific_mode else 2035
layers = build_demo_layers(demo_layer_year, retreat_rate)
layers["scientific_mode"] = scientific_mode
layers["scientific"] = scientific_bundle
layers["display_year"] = year
layers["infrastructure_real"] = {
    key: load_geojson_feature_collection(path)
    for key, path in real_infrastructure_paths.items()
}
layers["infrastructure_inventory"] = {
    key: load_geojson_feature_collection(path)
    for key, path in infrastructure_inventory_paths.items()
}
historical_line = layers["shorelines"].query("type == 'historica'").geometry.iloc[0]
current_line = layers["shorelines"].query("type == 'actual'").geometry.iloc[0]
comparison_progress = (comparison_year - 2017) / 9.0
animation_line = (
    interpolate_shorelines(historical_line, current_line, comparison_progress)
    if show_animation and not scientific_mode
    else None
)
comparison_displacement_m = (
    shoreline_displacement_m(historical_line, animation_line)
    if animation_line is not None
    else 0.0
)
map_visibility = {
    "shorelines": show_shorelines,
    "buildings": show_buildings,
    "transects": show_transects,
    "elevation": show_elevation,
    "animation": show_animation,
    "infrastructure_inventory": show_infrastructure_inventory,
    "real_infrastructure": show_real_infrastructure,
    "scientific_shorelines": show_shorelines,
    "scientific_rates": show_transects,
}
default_50 = layers["elevation_samples"].query("station_id == 'E06' and offset_m == 50").iloc[0]
default_150 = layers["elevation_samples"].query("station_id == 'E06' and offset_m == 150").iloc[0]
default_fraction = (68.0 - 50.0) / (150.0 - 50.0)
default_location = (
    default_50.geometry.y + (default_150.geometry.y - default_50.geometry.y) * default_fraction,
    default_50.geometry.x + (default_150.geometry.x - default_50.geometry.x) * default_fraction,
)
south, west = layers["coverage"]["bounds"][0]
north, east = layers["coverage"]["bounds"][1]
if (
    st.session_state.get("measurement_model_version") != "signed-risk-v2"
    or "selected_location" not in st.session_state
):
    st.session_state.selected_location = default_location
    st.session_state.measurement_model_version = "signed-risk-v2"
else:
    selected_lat, selected_lon = st.session_state.selected_location
    if not (south <= selected_lat <= north and west <= selected_lon <= east):
        st.session_state.selected_location = default_location

main_view = st.container()

with main_view:
    coverage = layers["coverage"]
    area_metrics = layers["area_metrics"]
    if scientific_mode:
        summary_a, summary_b, summary_c, summary_d, summary_e = st.columns(5)
        pipeline = scientific_bundle["pipeline"]
        infrastructure_summary = scientific_bundle["infrastructure_summary"]
        storm = scientific_bundle["storm"]
        summary_a.metric("Líneas Sentinel/NDWI", len(scientific_bundle["corrected_years"]))
        summary_b.metric("Escenas NDWI corregidas", len(scientific_bundle["tides"]))
        summary_c.metric("LRR válidas", scientific_bundle["valid_rate_count"])
        summary_d.metric("Años correlacionados", int(storm.get("n", 0) or 0))
        summary_e.metric(
            "Infraestructura evaluada",
            int(infrastructure_summary.get("building_count", 0))
            + int(infrastructure_summary.get("road_segment_count", 0)),
        )
    else:
        summary_a, summary_b, summary_c, summary_d = st.columns(4)
        summary_a.metric("Costa cubierta", f"{coverage['length_m'] / 1000:.2f} km")
        summary_b.metric(
            "Retroceso acumulado",
            f"{layers['retreat_m']:.1f} m",
            f"desde año cero {BASE_YEAR}",
        )
        summary_c.metric("Área alcanzada", f"{area_metrics['impact_area_ha']:.2f} ha")
        summary_d.metric(
            "Límite crítico desde referencia base",
            f"{area_metrics['critical_limit_from_2026_m']:.1f} m",
        )

    map_col, result_col = st.columns([2.45, 1], gap="large")
    with map_col:
        fmap = make_map(
            layers,
            st.session_state.selected_location,
            show_layers=map_visibility,
            animation_line=animation_line,
            animation_year=comparison_year,
            animation_progress=comparison_progress,
        )
        map_state = st_folium(
            fmap,
            height=690,
            use_container_width=True,
            returned_objects=["last_clicked"],
            key=(
                f"coast-map-{selected_mode}-{year}-{retreat_rate}-{comparison_year}-"
                f"{int(show_shorelines)}-{int(show_buildings)}-{int(show_transects)}-"
                f"{int(show_elevation)}-{int(show_infrastructure_inventory)}-"
                f"{int(show_real_infrastructure)}-{int(show_animation)}"
            ),
        )
        if map_state and map_state.get("last_clicked"):
            clicked = map_state["last_clicked"]
            location = (float(clicked["lat"]), float(clicked["lng"]))
            if location != st.session_state.selected_location:
                st.session_state.selected_location = location
                st.rerun()
        if scientific_mode:
            st.caption(
                f"Línea roja: costa {year} · Transectos rojos: retroceso · Azules: acreción."
            )
        else:
            st.caption(
                "E01 marca el extremo norte y E11 el extremo sur. Cada línea azul es un transecto normal "
                "a la costa. La línea gris punteada es el límite de 60 m del año cero 2026; la roja sólida es el "
                f"límite equivalente en {year}. La línea naranja representa {comparison_year} "
                f"({comparison_progress * 100:.0f}% desde 2017; desplazamiento medio aproximado "
                f"{comparison_displacement_m:.1f} m). Es una interpolación visual, no una observación anual."
            )

    with result_col:
        lat, lon = st.session_state.selected_location
        measurement = evaluate_location(lat, lon, 2035, float(DEFAULT_RETREAT_RATE))
        if scientific_mode:
            assessment = assess_nearest_infrastructure(
                lat,
                lon,
                scientific_bundle["paths"]["buildings"],
                scientific_bundle["paths"]["roads"],
            )
            feature_label = "Edificación" if assessment.feature_type == "building" else "Camino"
            st.subheader("Semáforo pipeline")
            st.markdown(
                f"<div class='cv-card'><div style='color:{assessment.color};font-size:1.4rem;font-weight:800'>"
                f"{assessment.risk_label}</div><p style='margin-bottom:0'>{assessment.explanation}</p></div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"**{feature_label} OSM más cercano:** {assessment.name or assessment.osm_id}  \n"
                f"**Transecto LRR:** {assessment.nearest_transect_id}"
            )
            st.metric("Distancia del elemento a costa 2026", f"{assessment.distance_to_shoreline_m:.1f} m")
            st.metric("LRR local", f"{assessment.erosion_rate_m_per_year:+.3f} m/año")
            impact_label = (
                f"{assessment.years_to_impact:.1f} años"
                if assessment.years_to_impact is not None
                else "No estimado (LRR ≤ 0)"
            )
            st.write(f"Tiempo hasta impacto: **{impact_label}**")
            st.caption(
                f"Clic a {assessment.click_distance_to_feature_m:.1f} m del elemento evaluado."
            )
        else:
            assessment = evaluate_location(lat, lon, year, retreat_rate)
            st.subheader("Punto evaluado (demo)")
            st.markdown(
                f"<div class='cv-card'><div style='color:{assessment.color};font-size:1.4rem;font-weight:800'>"
                f"{assessment.label}</div><p style='margin-bottom:0'>{assessment.recommendation}</p></div>",
                unsafe_allow_html=True,
            )
            margin_delta = assessment.signed_margin_m - assessment.baseline_margin_m
            st.metric(
                "Margen al frente proyectado",
                f"{assessment.signed_margin_m:+.1f} m",
                f"{margin_delta:+.1f} m respecto de 2026",
            )
            if assessment.reached_by_projection:
                st.error(
                    f"La proyección {year} ya supera este punto por {assessment.distance_m:.1f} m."
                )
            st.caption("Resultado del escenario manual; no es la clasificación científica.")

        st.metric("Cota DEM aproximada", format_elevation(measurement.elevation_m))
        st.markdown(f"**Estación DEM más cercana:** {measurement.nearest_station_id}")
        st.write(f"Progresiva desde el norte: **{measurement.alongshore_m:.0f} m**")
        if measurement.elevation_sample_distance_m is not None:
            st.write(
                f"Muestra DEM: **{measurement.elevation_offset_m} m tierra adentro**, "
                f"a {measurement.elevation_sample_distance_m:.0f} m del clic"
            )
        st.code(f"Lat {lat:.6f}\nLon {lon:.6f}", language=None)
        st.caption(
            f"DEM orientativo · resolución {measurement.elevation_resolution_m} m."
        )
        st.link_button("Abrir Street View", maps_url(lat, lon, "street"), width="stretch")
        st.link_button("Abrir mapa satelital", maps_url(lat, lon, "satellite"), width="stretch")
        st.link_button("Abrir Google Earth", maps_url(lat, lon, "earth"), width="stretch")

    st.divider()
    profile = layers["elevation_profile"].copy()
    profile_chart = profile.rename(
        columns={
            "latitude": "Latitud",
            "elevation_50m": "Cota a 50 m",
            "elevation_150m": "Cota a 150 m",
            "elevation_250m": "Cota a 250 m",
        }
    )
    st.subheader("Perfil de elevación norte-sur")
    st.caption("Cotas DEM a 50, 150 y 250 m tierra adentro.")
    st.line_chart(
        profile_chart,
        x="Latitud",
        y=["Cota a 50 m", "Cota a 150 m", "Cota a 250 m"],
        y_label="Cota DEM (m s.n.m.)",
        height=300,
    )
    profile_table = profile[
        [
            "station_id",
            "latitude",
            "longitude",
            "alongshore_m",
            "elevation_50m",
            "elevation_150m",
            "elevation_250m",
            "slope_pct_50_250",
        ]
    ].rename(
        columns={
            "station_id": "Estación",
            "latitude": "Latitud",
            "longitude": "Longitud",
            "alongshore_m": "Progresiva (m)",
            "elevation_50m": "Cota 50 m",
            "elevation_150m": "Cota 150 m",
            "elevation_250m": "Cota 250 m",
            "slope_pct_50_250": "Pendiente (%)",
        }
    )
    st.dataframe(profile_table, hide_index=True, width="stretch")
    st.subheader("Exportar resultados de la exploración")
    export_col_a, export_col_b, export_col_c = st.columns(3)
    with export_col_a:
        st.download_button(
            "Descargar perfil CSV",
            profile_table.to_csv(index=False).encode("utf-8"),
            file_name=f"coastvision_perfil_{year}.csv",
            mime="text/csv",
            width="stretch",
        )
    with export_col_b:
        transect_payload = (
            json.dumps(scientific_bundle["rates"], ensure_ascii=False).encode("utf-8")
            if scientific_mode
            else layers["transects"].to_json().encode("utf-8")
        )
        st.download_button(
            "Descargar transectos + LRR" if scientific_mode else "Descargar transectos GeoJSON",
            transect_payload,
            file_name="coastvision_transectos_lrr.geojson" if scientific_mode else "coastvision_transectos.geojson",
            mime="application/geo+json",
            width="stretch",
        )
    with export_col_c:
        st.download_button(
            "Descargar evaluación JSON",
            json.dumps(asdict(assessment), ensure_ascii=False, indent=2).encode("utf-8"),
            file_name="coastvision_punto_evaluado.json",
            mime="application/json",
            width="stretch",
        )
