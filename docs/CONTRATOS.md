# Contrato de Configuración y Especificación de Outputs (Strandline)

Este documento detalla los contratos de interfaces acordados para la unificación del proyecto, sirviendo como especificación técnica para los desarrolladores.

---

## 1. Contrato de Configuración (Desarrollo: Pablo)

El archivo centralizado de configuración se encuentra en:
👉 [`data/config/sites.json`](file:///c:/Users/emirx/Desktop/geoinformatica/ProyectoRealGeo/CoastVision/data/config/sites.json)

### Esquema JSON (Schema Contract)
Cada sitio/playa en el sistema debe registrarse bajo una clave única (slug identificador) y contener obligatoriamente los siguientes 8 campos:

| Campo | Tipo | Descripción | Ejemplo |
| :--- | :--- | :--- | :--- |
| `identificador` | `string` | Slug único en minúsculas. | `"renaca"` |
| `nombre` | `string` | Nombre formal de la playa de estudio. | `"Reñaca"` |
| `comuna` | `string` | Nombre de la comuna a la que pertenece. | `"Viña del Mar"` |
| `AOI` | `list[float]` | Bounding box en WGS84: `[West, South, East, North]`. | `[-71.552, -32.975, -71.538, -32.960]` |
| `CRS` | `string` | Sistema de referencia métrico de proyección local. | `"EPSG:32719"` |
| `fuente` | `string` | Fuente de los datos base utilizados. | `"OpenStreetMap / Sentinel-2 / Copernicus DEM"` |
| `parametros` | `dict` | Diccionario con variables de control numérico. | `{ "station_count": 38, "default_retreat_rate": 1.5, "center": [-32.9694, -71.545] }` |
| `directorio_de_salida` | `string` | Ruta relativa desde el workspace root para los outputs. | `"outputs/renaca"` |

### Reglas de Validaciones y Control de Errores
- Si un sitio no está registrado en `sites.json`, el backend levantará un `ValueError: El sitio 'X' no está registrado en la configuración`.
- Si las coordenadas de `AOI` son nulas o iguales a cero (`[0.0, 0.0, 0.0, 0.0]`), se levantará un `ValueError: El sitio 'X' tiene coordenadas de AOI inválidas o nulas`.

---

## 2. Especificación de Output para Strandline (Desarrollo: Daniel)

El resultado del procesamiento multitemporal (líneas de costa anuales corregidas por marea) se exporta en formato **GeoJSON** para cada playa en:
👉 `outputs/<identificador>/multitemporal/shorelines_2016_2026_fes2014.geojson` *(Cartagena conserva por compatibilidad la carpeta `outputs/multitemporal/`)*.

### Estructura de Datos
- **Tipo de archivo**: GeoJSON (`FeatureCollection`)
- **Proyección**: WGS84 (`EPSG:4326`)
- **Tipo de Geometría**: `LineString`

### Esquema de Atributos (Properties)

Cada feature (línea costera anual) contiene los siguientes atributos dentro del objeto `properties`:

| Atributo | Tipo | Descripción | Ejemplo |
| :--- | :--- | :--- | :--- |
| `year` | `integer` | Año de la observación (2016 al 2026). | `2024` |
| `scene_count` | `integer` | Cantidad de escenas satelitales utilizadas para el consenso. | `3` |
| `processing_level` | `string` | Nivel de procesamiento del sensor Sentinel-2. | `"L2A_FES2014"` |

### Ejemplo de Feature
```json
{
  "type": "Feature",
  "properties": {
    "year": 2024,
    "scene_count": 3,
    "processing_level": "L2A_FES2014"
  },
  "geometry": {
    "type": "LineString",
    "coordinates": [
      [-71.5469834, -32.9629697],
      [-71.5467462, -32.9638486],
      [-71.546509, -32.9647276]
    ]
  }
}
```
