"""OpenStreetMap y exposición de edificios/caminos a la erosión local."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import requests
from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize, unary_union


OVERPASS_URL = "https://overpass-api.de/api/interpreter"
WGS84 = "EPSG:4326"
UTM_19S = "EPSG:32719"


@dataclass(frozen=True)
class InfrastructureRiskResult:
    buildings: gpd.GeoDataFrame
    roads: gpd.GeoDataFrame
    summary: dict[str, Any]


def build_overpass_query(bbox_wgs84: list[float]) -> str:
    if len(bbox_wgs84) != 4:
        raise ValueError("bbox debe tener [oeste,sur,este,norte].")
    west, south, east, north = map(float, bbox_wgs84)
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("bbox WGS84 inválido.")
    bbox = f"{south},{west},{north},{east}"
    return (
        "[out:json][timeout:90];("
        f"way[\"building\"]({bbox});relation[\"building\"]({bbox});"
        f"way[\"highway\"]({bbox});"
        ");out tags geom;"
    )


def download_overpass_snapshot(
    bbox_wgs84: list[float],
    *,
    endpoint: str = OVERPASS_URL,
    timeout: int = 120,
) -> dict[str, Any]:
    response = requests.post(
        endpoint,
        data={"data": build_overpass_query(bbox_wgs84)},
        timeout=timeout,
        headers={"User-Agent": "CoastVision-USACH/1.0 educational"},
    )
    response.raise_for_status()
    payload = response.json()
    if "elements" not in payload:
        raise ValueError("Overpass no devolvió elements.")
    return payload


def _coordinates(element: dict[str, Any]) -> list[tuple[float, float]]:
    return [
        (float(point["lon"]), float(point["lat"]))
        for point in element.get("geometry", [])
        if "lon" in point and "lat" in point
    ]


def _relation_building_geometry(element: dict[str, Any]):
    outer_lines: list[LineString] = []
    for member in element.get("members", []):
        if member.get("role", "outer") not in {"", "outer"}:
            continue
        coordinates = _coordinates(member)
        if len(coordinates) >= 2:
            outer_lines.append(LineString(coordinates))
    if not outer_lines:
        return None
    polygons = list(polygonize(unary_union(outer_lines)))
    if not polygons:
        return None
    geometry = unary_union(polygons).buffer(0)
    return geometry if geometry.is_valid and not geometry.is_empty else None


def parse_overpass_infrastructure(
    payload: dict[str, Any],
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    buildings: list[dict[str, Any]] = []
    roads: list[dict[str, Any]] = []
    for element in payload.get("elements", []):
        tags = element.get("tags", {})
        coordinates = _coordinates(element)
        osm_type = str(element.get("type", "unknown"))
        osm_id = str(element.get("id", ""))
        common = {
            "osm_id": f"{osm_type}/{osm_id}",
            "name": tags.get("name"),
            "source": "OpenStreetMap/Overpass",
        }
        if tags.get("building"):
            polygon = None
            if len(coordinates) >= 4:
                if coordinates[0] != coordinates[-1]:
                    coordinates.append(coordinates[0])
                candidate = Polygon(coordinates)
                if candidate.is_valid and not candidate.is_empty:
                    polygon = candidate
            elif osm_type == "relation":
                polygon = _relation_building_geometry(element)
            if polygon is not None:
                buildings.append({
                    **common,
                    "building": tags.get("building"),
                    "geometry": polygon,
                })
        if tags.get("highway") and len(coordinates) >= 2:
            roads.append({
                **common,
                "highway": tags.get("highway"),
                "surface": tags.get("surface"),
                "geometry": LineString(coordinates),
            })
    building_gdf = gpd.GeoDataFrame(
        buildings,
        columns=["osm_id", "name", "source", "building", "geometry"],
        geometry="geometry",
        crs=WGS84,
    )
    road_gdf = gpd.GeoDataFrame(
        roads,
        columns=["osm_id", "name", "source", "highway", "surface", "geometry"],
        geometry="geometry",
        crs=WGS84,
    )
    return building_gdf, road_gdf


def _risk_level(years_to_impact: float | None) -> tuple[str, str]:
    if years_to_impact is None or not np.isfinite(years_to_impact):
        return "bajo", "Sin avance erosivo positivo medido"
    if years_to_impact < 10:
        return "critico", "Impacto estimado en menos de 10 años"
    if years_to_impact <= 30:
        return "moderado", "Impacto estimado entre 10 y 30 años"
    return "bajo", "Impacto estimado después de 30 años"


def _nearest_rate(feature, rates_metric: gpd.GeoDataFrame, rate_column: str) -> tuple[str, float]:
    distances = rates_metric.geometry.distance(feature.centroid)
    index = distances.idxmin()
    row = rates_metric.loc[index]
    return str(row["transect_id"]), float(row[rate_column])


def _classify_features(
    features: gpd.GeoDataFrame,
    shoreline_metric,
    rates_metric: gpd.GeoDataFrame,
    *,
    kind: str,
    rate_column: str,
    horizon_years: int,
) -> gpd.GeoDataFrame:
    if features.empty:
        empty = features.copy()
        for column in (
            "feature_type", "nearest_transect_id", "erosion_rate_m_per_year",
            "distance_to_shoreline_m", "years_to_impact", "risk_level",
            "risk_explanation", "horizon_years", "exposed_length_m",
            "exposed_area_m2",
        ):
            empty[column] = None
        return empty
    records: list[dict[str, Any]] = []
    for _, row in features.iterrows():
        geometry = row.geometry
        transect_id, erosion_rate = _nearest_rate(geometry, rates_metric, rate_column)
        distance_m = float(geometry.distance(shoreline_metric))
        years_to_impact = distance_m / erosion_rate if erosion_rate > 0 else None
        risk, explanation = _risk_level(years_to_impact)
        projected_reach_m = max(0.0, erosion_rate * horizon_years)
        threat_zone = shoreline_metric.buffer(projected_reach_m)
        exposed = geometry.intersection(threat_zone)
        record = row.drop(labels=[features.geometry.name]).to_dict()
        record.update({
            "feature_type": kind,
            "nearest_transect_id": transect_id,
            "erosion_rate_m_per_year": round(erosion_rate, 3),
            "distance_to_shoreline_m": round(distance_m, 1),
            "years_to_impact": round(years_to_impact, 1) if years_to_impact is not None else None,
            "risk_level": risk,
            "risk_explanation": explanation,
            "horizon_years": horizon_years,
            "exposed_length_m": round(exposed.length, 1) if kind == "road" else None,
            "exposed_area_m2": round(exposed.area, 1) if kind == "building" else None,
            "geometry": geometry,
        })
        records.append(record)
    return gpd.GeoDataFrame(records, geometry="geometry", crs=features.crs)


def assess_infrastructure_risk(
    buildings_wgs84: gpd.GeoDataFrame,
    roads_wgs84: gpd.GeoDataFrame,
    shoreline_wgs84,
    transect_rates: gpd.GeoDataFrame,
    *,
    rate_column: str = "lrr_m_per_year",
    horizon_years: int = 30,
) -> InfrastructureRiskResult:
    if rate_column not in transect_rates.columns:
        raise ValueError(f"Falta la tasa '{rate_column}'.")
    if horizon_years <= 0:
        raise ValueError("horizon_years debe ser positivo.")
    rates = transect_rates.to_crs(UTM_19S).dropna(subset=[rate_column])
    if rates.empty:
        raise ValueError("No hay tasas válidas para clasificar infraestructura.")
    shoreline = gpd.GeoSeries([shoreline_wgs84], crs=WGS84).to_crs(UTM_19S).iloc[0]
    buildings_metric = buildings_wgs84.to_crs(UTM_19S)
    roads_metric = roads_wgs84.to_crs(UTM_19S)
    buildings = _classify_features(
        buildings_metric, shoreline, rates,
        kind="building", rate_column=rate_column, horizon_years=horizon_years,
    ).to_crs(WGS84)
    roads = _classify_features(
        roads_metric, shoreline, rates,
        kind="road", rate_column=rate_column, horizon_years=horizon_years,
    ).to_crs(WGS84)
    summary = {
        "building_count": int(len(buildings)),
        "road_segment_count": int(len(roads)),
        "critical_buildings": int((buildings["risk_level"] == "critico").sum()) if not buildings.empty else 0,
        "critical_roads": int((roads["risk_level"] == "critico").sum()) if not roads.empty else 0,
        "exposed_road_length_m": round(float(roads["exposed_length_m"].sum()), 1) if not roads.empty else 0.0,
        "exposed_building_area_m2": round(float(buildings["exposed_area_m2"].sum()), 1) if not buildings.empty else 0.0,
        "rate_source": rate_column,
        "horizon_years": horizon_years,
    }
    return InfrastructureRiskResult(buildings=buildings, roads=roads, summary=summary)


def save_overpass_snapshot(payload: dict[str, Any], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
