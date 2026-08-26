"""Adaptador reproducible entre CoastVision y el binario Rust ``strandline``.

El motor externo usa CSV en coordenadas proyectadas y mide el *chainage* desde
el extremo terrestre hacia el mar. CoastVision, en cambio, conserva GeoJSON
en WGS84 y expresa la posición firmada desde la línea base, positiva hacia
tierra. Este módulo concentra ambas conversiones y deja los archivos
intermedios para que la integración pueda auditarse y repetirse.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence


class StrandlineError(RuntimeError):
    """Error con contexto de una ejecución del motor Rust."""


@dataclass(frozen=True)
class StrandlineRun:
    """Resultado serializable de una ejecución de ``intersect`` + ``rates``."""

    status: str
    engine: str
    binary: str
    binary_version: str
    output_dir: str
    transects_input: str
    shorelines_input: str
    dates_input: str
    intersections_raw: str
    rates_raw: str
    intersections_coastvision: str
    rates_coastvision: str
    manifest: str
    elapsed_seconds: float
    transect_count: int
    shoreline_count: int
    intersection_count: int
    rate_count: int
    along_dist_m: float
    min_valid: int
    comparison: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _command(binary: str | Path | Sequence[str | Path]) -> list[str]:
    if isinstance(binary, (str, Path)):
        value = str(binary)
        if isinstance(binary, Path) and not binary.is_file():
            raise FileNotFoundError(f"No existe el binario strandline: {binary}")
        if isinstance(binary, str) and (os.sep in binary or (os.altsep and os.altsep in binary)):
            if not Path(binary).is_file():
                raise FileNotFoundError(f"No existe el binario strandline: {binary}")
        if not (os.sep in value or (os.altsep and os.altsep in value)) and shutil.which(value) is None:
            raise FileNotFoundError(
                f"No se encontró '{value}' en PATH. Usa --strandline-bin o STRANDLINE_BIN."
            )
        return [value]
    result = [str(part) for part in binary]
    if not result:
        raise ValueError("El comando strandline no puede estar vacío.")
    return result


def _run(command: Sequence[str], *, cwd: Path | None = None, timeout: int = 300) -> tuple[str, str, float]:
    started = time.perf_counter()
    completed = subprocess.run(
        list(command),
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    elapsed = time.perf_counter() - started
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "sin salida").strip()
        raise StrandlineError(
            f"strandline falló con código {completed.returncode}: {' '.join(command)}\n{detail}"
        )
    return completed.stdout.strip(), completed.stderr.strip(), elapsed


def _geojson_features(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise FileNotFoundError(f"No se pudo leer {path}: {exc}") from exc
    if payload.get("type") != "FeatureCollection":
        raise ValueError(f"{path} no es un FeatureCollection GeoJSON.")
    features = payload.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError(f"{path} no contiene features.")
    return features


def _line_coordinates(feature: dict[str, Any], path: Path) -> list[list[float]]:
    geometry = feature.get("geometry") or {}
    coordinates = geometry.get("coordinates")
    if geometry.get("type") == "LineString":
        result = coordinates
    elif geometry.get("type") == "MultiLineString":
        result = [point for segment in coordinates for point in segment]
    else:
        raise ValueError(f"{path} contiene una geometría no lineal: {geometry.get('type')}")
    if not isinstance(result, list) or len(result) < 2:
        raise ValueError(f"{path} contiene una línea con menos de dos vértices.")
    return result


def _transformer():
    try:
        from pyproj import Transformer
    except ImportError as exc:  # pragma: no cover - depende del entorno de ejecución
        raise StrandlineError(
            "La integración requiere pyproj, incluido en requirements.txt."
        ) from exc
    return Transformer.from_crs("EPSG:4326", "EPSG:32719", always_xy=True)


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fieldnames), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def prepare_inputs(
    transects_geojson: str | Path,
    shorelines_geojson: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Convierte los artefactos de CoastVision al contrato CSV de strandline."""

    transects_path = Path(transects_geojson)
    shorelines_path = Path(shorelines_geojson)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    transformer = _transformer()

    transect_rows: list[dict[str, Any]] = []
    transect_offsets: dict[str, float] = {}
    transect_chainages: dict[str, float] = {}
    for feature in _geojson_features(transects_path):
        properties = feature.get("properties") or {}
        name = str(properties.get("transect_id") or "").strip()
        if not name or name in transect_offsets:
            raise ValueError(f"Transecto inválido o duplicado en {transects_path}: {name!r}")
        baseline_e = _finite(properties.get("baseline_x"))
        baseline_n = _finite(properties.get("baseline_y"))
        if baseline_e is None or baseline_n is None:
            raise ValueError(f"{name} no tiene baseline_x/baseline_y métricos.")
        coordinates = _line_coordinates(feature, transects_path)
        projected = [transformer.transform(float(point[0]), float(point[1])) for point in coordinates]
        first, last = projected[0], projected[-1]
        first_distance = math.hypot(first[0] - baseline_e, first[1] - baseline_n)
        last_distance = math.hypot(last[0] - baseline_e, last[1] - baseline_n)
        # strandline exige origin=tierra y end=mar. Elegimos por distancia a
        # la línea base, evitando depender del orden accidental del GeoJSON.
        origin, end = (first, last) if first_distance >= last_distance else (last, first)
        baseline_offset = math.hypot(origin[0] - baseline_e, origin[1] - baseline_n)
        transect_rows.append({
            "name": name,
            "origin_e": f"{origin[0]:.6f}",
            "origin_n": f"{origin[1]:.6f}",
            "end_e": f"{end[0]:.6f}",
            "end_n": f"{end[1]:.6f}",
        })
        transect_offsets[name] = baseline_offset
        transect_chainages[name] = float(properties.get("chainage_m") or 0.0)

    shoreline_rows: list[dict[str, Any]] = []
    date_rows: list[dict[str, Any]] = []
    shoreline_ids: list[str] = []
    seen_years: set[int] = set()
    for feature in _geojson_features(shorelines_path):
        properties = feature.get("properties") or {}
        try:
            year = int(properties["year"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Una shoreline de {shorelines_path} no tiene year válido.") from exc
        if year in seen_years:
            raise ValueError(
                f"{shorelines_path} contiene más de una shoreline para {year}; "
                "consolida las líneas antes de integrar strandline."
            )
        seen_years.add(year)
        shoreline_id = f"Y{year}"
        shoreline_ids.append(shoreline_id)
        acquired_at = str(properties.get("acquired_at") or f"{year}-01-01T00:00:00Z")
        date_rows.append({"shoreline_id": shoreline_id, "date": acquired_at})
        for point in _line_coordinates(feature, shorelines_path):
            easting, northing = transformer.transform(float(point[0]), float(point[1]))
            shoreline_rows.append({
                "shoreline_id": shoreline_id,
                "easting": f"{easting:.6f}",
                "northing": f"{northing:.6f}",
            })

    transects_csv = out / "transects.csv"
    shorelines_csv = out / "shorelines.csv"
    dates_csv = out / "dates.csv"
    _write_csv(transects_csv, ("name", "origin_e", "origin_n", "end_e", "end_n"), transect_rows)
    _write_csv(shorelines_csv, ("shoreline_id", "easting", "northing"), shoreline_rows)
    _write_csv(dates_csv, ("shoreline_id", "date"), date_rows)
    metadata = {
        "crs": "EPSG:32719",
        "transect_count": len(transect_rows),
        "shoreline_count": len(shoreline_ids),
        "shoreline_ids": shoreline_ids,
        "transect_offsets_from_landward_origin_m": transect_offsets,
        "transect_chainage_m": transect_chainages,
        "position_conversion": "coastvision_position_m = baseline_offset_m - strandline_chainage_m",
    }
    (out / "input_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {
        "transects_csv": transects_csv,
        "shorelines_csv": shorelines_csv,
        "dates_csv": dates_csv,
        "metadata": metadata,
    }


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _normalise_outputs(
    raw_intersections: Path,
    raw_rates: Path,
    output_dir: Path,
    metadata: dict[str, Any],
) -> tuple[Path, Path, int, int]:
    ids_to_year = {
        shoreline_id: int(shoreline_id[1:])
        for shoreline_id in metadata["shoreline_ids"]
    }
    offsets = {str(key): float(value) for key, value in metadata["transect_offsets_from_landward_origin_m"].items()}
    chainages = {str(key): float(value) for key, value in metadata["transect_chainage_m"].items()}

    intersections: list[dict[str, Any]] = []
    for row in _read_rows(raw_intersections):
        transect = str(row.get("transect") or "")
        shoreline_id = str(row.get("shoreline_id") or "")
        chainage = _finite(row.get("chainage_m"))
        if transect not in offsets or shoreline_id not in ids_to_year or chainage is None:
            continue
        intersections.append({
            "transect_id": transect,
            "year": ids_to_year[shoreline_id],
            "position_m": f"{offsets[transect] - chainage:.6f}",
            "intersection_found": "True",
            "source": "strandline",
        })
    intersections_path = output_dir / "transect_intersections_strandline.csv"
    _write_csv(
        intersections_path,
        ("transect_id", "year", "position_m", "intersection_found", "source"),
        intersections,
    )

    rates: list[dict[str, Any]] = []
    for row in _read_rows(raw_rates):
        transect = str(row.get("transect") or "")
        if transect not in chainages:
            continue
        n_valid = _finite(row.get("n_valid"))
        raw_nsm = _finite(row.get("NSM_m"))
        raw_epr = _finite(row.get("EPR_m_yr"))
        raw_sce = _finite(row.get("SCE_m"))
        raw_lrr = _finite(row.get("LRR_m_yr"))
        raw_r2 = _finite(row.get("LRR_r2"))
        ci95 = _finite(row.get("LRR_ci95"))
        raw_wlr = _finite(row.get("WLR_m_yr"))
        raw_wlr_ci95 = _finite(row.get("WLR_ci95"))
        years = _finite(row.get("years"))
        n_int = int(n_valid) if n_valid is not None else 0
        lrr = -raw_lrr if raw_lrr is not None else None
        rates.append({
            "transect_id": transect,
            "chainage_m": f"{chainages[transect]:.6f}",
            "n_observations": n_int,
            "n_expected_years": len(ids_to_year),
            "temporal_completeness_pct": f"{100.0 * n_int / len(ids_to_year):.6f}",
            "years": f"{years:.6f}" if years is not None else "",
            "nsm_m": f"{-raw_nsm:.6f}" if raw_nsm is not None else "",
            "sce_m": f"{raw_sce:.6f}" if raw_sce is not None else "",
            "epr_m_per_year": f"{-raw_epr:.6f}" if raw_epr is not None else "",
            "lrr_m_per_year": f"{lrr:.6f}" if lrr is not None else "",
            "lrr_r2": f"{raw_r2:.6f}" if raw_r2 is not None else "",
            "lrr_ci95_low_m_per_year": f"{lrr - ci95:.6f}" if lrr is not None and ci95 is not None else "",
            "lrr_ci95_high_m_per_year": f"{lrr + ci95:.6f}" if lrr is not None and ci95 is not None else "",
            "wlr_m_per_year": f"{-raw_wlr:.6f}" if raw_wlr is not None else "",
            "wlr_ci95_m_per_year": f"{raw_wlr_ci95:.6f}" if raw_wlr_ci95 is not None else "",
            "sign_convention": "positive=landward_retreat; negative=seaward_accretion",
            "source": "strandline",
        })
    rates_path = output_dir / "transect_rates_strandline.csv"
    _write_csv(rates_path, tuple(rates[0].keys()) if rates else (
        "transect_id", "chainage_m", "n_observations", "n_expected_years",
        "temporal_completeness_pct", "years", "nsm_m", "sce_m", "epr_m_per_year",
        "lrr_m_per_year", "lrr_r2", "lrr_ci95_low_m_per_year",
        "lrr_ci95_high_m_per_year", "wlr_m_per_year", "wlr_ci95_m_per_year",
        "sign_convention", "source",
    ), rates)
    return intersections_path, rates_path, len(intersections), len(rates)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _compare_rates(native_path: Path | None, rust_path: Path) -> dict[str, Any]:
    if native_path is None or not native_path.is_file():
        return {"status": "NOT_REQUESTED"}
    if native_path.suffix.lower() in {".geojson", ".json"}:
        payload = json.loads(native_path.read_text(encoding="utf-8"))
        native_rows = [feature.get("properties", {}) for feature in payload.get("features", [])]
    else:
        native_rows = _read_rows(native_path)
    native = {row.get("transect_id", ""): _finite(row.get("lrr_m_per_year")) for row in native_rows}
    rust = {row.get("transect_id", ""): _finite(row.get("lrr_m_per_year")) for row in _read_rows(rust_path)}
    pairs = [(native[key], rust[key]) for key in native.keys() & rust.keys() if native[key] is not None and rust[key] is not None]
    if not pairs:
        return {"status": "NO_OVERLAPPING_FINITE_LRR"}
    differences = [rust_value - native_value for native_value, rust_value in pairs]
    rmse = math.sqrt(sum(diff * diff for diff in differences) / len(differences))
    mean_abs = sum(abs(diff) for diff in differences) / len(differences)
    return {
        "status": "OK",
        "paired_lrr_count": len(pairs),
        "rmse_m_per_year": rmse,
        "mean_absolute_difference_m_per_year": mean_abs,
        "native_rate_count": sum(value is not None for value in native.values()),
        "strandline_rate_count": sum(value is not None for value in rust.values()),
    }


def run_strandline(
    *,
    binary: str | Path | Sequence[str | Path],
    transects_geojson: str | Path,
    shorelines_geojson: str | Path,
    output_dir: str | Path,
    native_rates_csv: str | Path | None = None,
    along_dist_m: float = 25.0,
    min_valid: int = 3,
    timeout_seconds: int = 300,
) -> StrandlineRun:
    """Ejecuta ``strandline intersect`` y ``strandline rates`` sobre un sitio."""

    if along_dist_m <= 0 or not math.isfinite(along_dist_m):
        raise ValueError("along_dist_m debe ser positivo y finito.")
    if min_valid < 2:
        raise ValueError("min_valid debe ser al menos 2.")
    command = _command(binary)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    inputs = prepare_inputs(transects_geojson, shorelines_geojson, out / "inputs")
    raw_intersections = out / "intersections_strandline_raw.csv"
    raw_rates = out / "rates_strandline_raw.csv"

    version_stdout, version_stderr, _ = _run([*command, "--version"], timeout=timeout_seconds)
    version = (version_stdout or version_stderr or "desconocida").splitlines()[0].strip()
    intersect_command = [
        *command,
        "--strict",
        "intersect",
        "--transects", str(inputs["transects_csv"]),
        "--shorelines", str(inputs["shorelines_csv"]),
        "--along-dist", str(along_dist_m),
        "--output", str(raw_intersections),
    ]
    rates_command = [
        *command,
        "--strict",
        "rates",
        "--intersections", str(raw_intersections),
        "--dates", str(inputs["dates_csv"]),
        "--min-valid", str(min_valid),
        "--output", str(raw_rates),
    ]
    _, intersect_stderr, intersect_elapsed = _run(intersect_command, timeout=timeout_seconds)
    _, rates_stderr, rates_elapsed = _run(rates_command, timeout=timeout_seconds)
    intersections_path, rates_path, intersection_count, rate_count = _normalise_outputs(
        raw_intersections, raw_rates, out, inputs["metadata"]
    )
    comparison = _compare_rates(Path(native_rates_csv) if native_rates_csv else None, rates_path)
    manifest = out / "manifest.json"
    manifest_payload = {
        "schema_version": 1,
        "engine": "strandline",
        "binary": command,
        "binary_version": version,
        "commands": {"intersect": intersect_command, "rates": rates_command},
        "command_stderr": {"intersect": intersect_stderr, "rates": rates_stderr},
        "elapsed_seconds": {"intersect": intersect_elapsed, "rates": rates_elapsed},
        "inputs": {
            "transects_geojson": str(Path(transects_geojson)),
            "shorelines_geojson": str(Path(shorelines_geojson)),
            "native_rates_csv": str(native_rates_csv) if native_rates_csv else None,
            "transects_csv_sha256": _sha256(inputs["transects_csv"]),
            "shorelines_csv_sha256": _sha256(inputs["shorelines_csv"]),
            "dates_csv_sha256": _sha256(inputs["dates_csv"]),
        },
        "contract": inputs["metadata"],
        "comparison": comparison,
    }
    manifest.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return StrandlineRun(
        status="OK",
        engine="strandline",
        binary=" ".join(command),
        binary_version=version,
        output_dir=str(out),
        transects_input=str(inputs["transects_csv"]),
        shorelines_input=str(inputs["shorelines_csv"]),
        dates_input=str(inputs["dates_csv"]),
        intersections_raw=str(raw_intersections),
        rates_raw=str(raw_rates),
        intersections_coastvision=str(intersections_path),
        rates_coastvision=str(rates_path),
        manifest=str(manifest),
        elapsed_seconds=round(intersect_elapsed + rates_elapsed, 6),
        transect_count=int(inputs["metadata"]["transect_count"]),
        shoreline_count=int(inputs["metadata"]["shoreline_count"]),
        intersection_count=intersection_count,
        rate_count=rate_count,
        along_dist_m=float(along_dist_m),
        min_valid=int(min_valid),
        comparison=comparison,
    )


__all__ = ["StrandlineError", "StrandlineRun", "prepare_inputs", "run_strandline"]
