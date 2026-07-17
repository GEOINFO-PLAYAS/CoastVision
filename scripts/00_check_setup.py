from __future__ import annotations

import importlib.metadata as metadata
import shutil
import subprocess
from pathlib import Path


PACKAGES = [
    "geopandas",
    "rasterio",
    "rasterstats",
    "matplotlib",
    "numpy",
    "pandas",
    "shapely",
    "folium",
    "contextily",
    "notebook",
]


def package_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "NO INSTALADO"


def find_surtgis() -> str | None:
    found = shutil.which("surtgis")
    if found:
        return found

    fallback = Path.home() / "tools" / "surtgis" / "surtgis.exe"
    if fallback.exists():
        return str(fallback)

    return None


def main() -> None:
    print("Chequeo del entorno geoinformatico\n")

    for package in PACKAGES:
        print(f"{package:12} {package_version(package)}")

    surtgis = find_surtgis()
    if surtgis:
        version = subprocess.run(
            [surtgis, "--version"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        print(f"\nSurtGIS      {version}")
        print(f"Ruta         {surtgis}")
    else:
        print("\nSurtGIS      NO ENCONTRADO")

    print("\nOK: si no ves 'NO INSTALADO', el entorno esta listo.")


if __name__ == "__main__":
    main()
