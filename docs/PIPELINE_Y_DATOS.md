# Pipeline y datos de CoastVision

## 1. Objetivo y alcance

CoastVision combina:

- un **visor demostrativo** para explorar exposición, estaciones y elevación en Playa Grande de Cartagena; y
- un **pipeline científico 2016–2026** que implementa los requisitos de Sentinel-2, NDWI, FES2014, cambio tipo DSAS, marejadas e infraestructura.

La aplicación actual no presenta una amenaza oficial. Sus líneas 2017/futura y sus franjas son escenarios. El pipeline científico aún no produce una serie final completa y, por diseño, no alimenta ese semáforo.

## 2. Delimitación de la playa

### 2.1 Referencia cartográfica

El `way 300607261` de OpenStreetMap es un polígono `natural=beach`. Se fijaron dos anclas auditadas:

- norte: longitud `-71.6214046`, latitud `-33.5017252`;
- sur: longitud `-71.6105658`, latitud `-33.5150018`.

Las anclas dividen el anillo en dos recorridos. El pipeline conserva el único arco simple dentro del rango validado de 1.800–1.950 m. El resultado tiene 69 vértices, mide 1.868,9 m y se orienta de norte a sur. OSM se usa para delimitar y guiar la extracción; **no es una línea de agua observada en 2026**.

### 2.2 Área analítica y área satelital

El visor usa un corredor de 50 m hacia el mar y 260 m hacia tierra. Para el catálogo Sentinel-2 se amplía la geometría con una envolvente de 500 m, cuya bbox WGS84 es aproximadamente:

```text
Oeste  -71.6273102
Sur    -33.5196197
Este   -71.6046611
Norte  -33.4970742
```

Esta ampliación cubre la playa completa y evita recortar agua o infraestructura cercana durante el procesamiento.

## 3. Fuentes y estado de los datos

| Dato | Fuente / descarga | Uso | Estado actual |
|---|---|---|---|
| Borde de Playa Grande | OpenStreetMap `way 300607261`, API v0.6, ODbL | Delimitación, red, AOI y referencia visual | Activo y trazable |
| Elevación | Copernicus DEM GLO-90 vía Open-Meteo | 33 cotas a 50/150/250 m | Activo; 90 m, uso indicativo |
| Sentinel-2 | Earth Search/AWS para L1C y L2A | NDWI y línea de agua por año | 31 escenas catalogadas; 28 aceptadas y 11 líneas anuales |
| FES2014b | Modelo externo usado con pyTMD | Marea por fecha y corrección a MSL | 34/34, predicción validada y 28 correcciones para 2016–2026 |
| Marejadas | 16 avisos oficiales Armada/SERVIMET, con metadatos SHOA/DMC | Unión temporal y correlación | Catálogo parcial, no continuo |
| Edificios y caminos | OpenStreetMap `building=*` y `highway=*` | Infraestructura expuesta | 38 edificios y 252 tramos; screening 2016–2026 conectado |
| Corpus metodológico | `data/knowledge_base.json` | RAG local | Activo; no altera cálculos |

La procedencia del bundle OSM/DEM está en `data/provenance_manifest.json` y sus snapshots en `data/raw/`.

## 4. Rama demostrativa

### 4.1 Adquisición base

```powershell
python scripts/00_refresh_source_data.py
python scripts/00_refresh_source_data.py --offline
```

La actualización valida el polígono OSM, selecciona el arco, genera 11 estaciones, consulta 33 cotas y publica los activos solo cuando el bundle completo es coherente. Los hashes SHA-256 permiten reconstruirlo y detectar cambios.

### 4.2 Red de medición

La línea se divide en diez intervalos para obtener E01–E11 cada 186,9 m aproximadamente. Cada transecto cubre 50 m hacia el mar y 260 m hacia tierra. Las distancias se calculan en UTM 19S (`EPSG:32719`); los GeoJSON y las coordenadas de entrada usan WGS84 (`EPSG:4326`) y Leaflet representa el lienzo en Web Mercator (`EPSG:3857`).

### 4.3 Escenario visible

```text
retroceso(y) = max(0, y - 2026) × tasa
```

2026 es el cero matemático del escenario. La línea rotulada 2017 es un offset fijo demostrativo y no es la línea NDWI real de 2017. El clic usa un margen firmado y la misma lógica que las franjas.

```powershell
python scripts/04_build_coastvision_mvp.py --year 2035 --retreat-rate 1.5
```

Las salidas se guardan en `outputs/coastvision_mvp/`: líneas, franjas, zona alcanzada, área de estudio, estaciones, transectos, muestras DEM, perfil CSV, predios demo, resumen y procedencia.

## 5. Catálogo Sentinel-2 2016–2026

```powershell
python scripts/06_build_sentinel_catalog.py
```

El catálogo `data/sentinel/catalog_2016_2026.json` contiene 31 escenas:

- 2016: una escena L1C pública con B03/B08, sin SCL y con QA visual reforzado;
- 2017–2026: tres escenas L2A públicas por año, con B03, B08 y SCL;

Cuando el procesamiento tiene dos o más escenas válidas para un año, `scripts/07_process_multitemporal.py` construye una máscara de agua por mayoría estricta sobre una grilla común UTM 19S antes de vectorizar la costa. Esto reduce el ruido de oleaje de una captura individual; si solo queda una escena, el resumen marca `single_scene_fallback`.

Si FES2014 está configurado, la marea se corrige ahora para cada escena antes de calcular la línea mediana anual; la fecha representativa solo se conserva como metadato del grupo, no como sustituto de las correcciones individuales.
- años faltantes en el catálogo: ninguno.

La selección usa la ventana estival definida por el proyecto y cobertura del AOI. “Catálogo completo” significa que hay candidatos para los once años; no significa que las once líneas estén extraídas o validadas.

## 6. NDWI y extracción de línea de agua

El script integrado aplica:

```text
NDWI = (B03 - B08) / (B03 + B08)
```

Para L2A, B08 y SCL se remuestrean a la grilla B03; la SCL enmascara clases no válidas. Después se umbraliza agua, se vectoriza y se selecciona el borde compatible con la referencia de playa. La pauta acepta NDWI **o** MNDWI, por lo que no es obligatorio implementar ambos.

La ejecución consolidada disponible corresponde a 2017 y 2026:

- 53.699 píxeles válidos;
- 24.995 píxeles de agua;
- hasta tres escenas por año; 28 escenas válidas en total;
- consenso anual por mayoría estricta en UTM 19S;
- `outputs/multitemporal/ndwi_*.tif`, `water_2017.geojson` y `water_2026.geojson`;
- `outputs/multitemporal/shorelines_raw_ndwi.geojson`;
- `pipeline_summary.json` con `PARTIAL_DO_NOT_USE_FOR_DECISIONS`.

Los metadatos registran un CV de área de agua de 1,25 % en 2017 y 0,11 % en 2026. Aun así, las dos líneas deben revisarse visualmente contra la imagen base antes de usarlas para decisiones.

```powershell
python scripts/07_process_multitemporal.py --years 2017 2026 --tide-model-dir "RUTA_EXTERNA_AL_MODELO" --output outputs\multitemporal
```

## 7. Corrección de marea FES2014

`src/coastvision/tides.py` predice la marea por fecha y desplaza la línea con una pendiente de playa declarada para aproximarla a nivel medio del mar. La corrección debe ocurrir **antes** de calcular tasas.

El modelo FES2014b se mantiene fuera del repositorio y de los ZIP: 34 NetCDF, aproximadamente 4,5 GB. `outputs/fes2014_validation.json` confirma estructura y predicción numérica válidas. `outputs/multitemporal/tide_corrections.csv` contiene 28 correcciones y la salida anual incluye 2016–2026.

```powershell
python scripts/09_validate_fes2014.py --model-dir "RUTA_EXTERNA_AL_MODELO"
python scripts/09_validate_fes2014.py --model-dir "RUTA_EXTERNA_AL_MODELO" --predict
```

La primera línea valida estructura; `--predict` reproduce la prueba numérica. El pipeline multitemporal requiere indicar el directorio externo y la pendiente usada.

## 8. Cambio costero tipo DSAS

`src/coastvision/change_analysis.py` implementa un equivalente en Python sobre transectos fijos:

- NSM: movimiento neto;
- EPR: tasa entre extremos;
- LRR: regresión lineal de posición contra tiempo;
- R², error estándar e intervalo de confianza al 95 %.

`scripts/07_process_multitemporal.py` generó `transect_intersections.*` y `transect_rates.*` con once líneas FES-corregidas: 39 transectos, 336 intersecciones y 38 LRR válidas. Cada salida conserva número de observaciones, completitud, R², error estándar e IC95.

## 9. Marejadas SHOA/DMC

`data/events/marejadas_oficiales_armada.csv` contiene 16 avisos oficiales verificados. `data/events/catalog_metadata.json` declara:

- `catalog_complete: false`;
- años con avisos verificados: 2016, 2017, 2018, 2019, 2020, 2021, 2024 y 2026;
- revisión sistemática pendiente: 2022, 2023 y 2025.

`src/coastvision/storms.py` y el script 07 ejecutaron la unión temporal y la correlación punto-biserial: n=11, r=-0,405 y p=0,216. Es exploratoria y no concluyente porque el catálogo oficial no certifica exhaustividad anual. Un año sin filas **no** equivale a un año sin marejadas.

## 10. Infraestructura costera en riesgo

```powershell
python scripts/08_refresh_osm_infrastructure.py
python scripts/10_assess_infrastructure.py
```

El primer script descarga y guarda edificios y caminos OSM dentro del AOI. El segundo requiere esas capas, la línea corregida más reciente y LRR reales. La clasificación combina distancia métrica a la costa con cambio local y exporta GeoJSON/resumen con hashes.

`data/infrastructure/` contiene 38 edificios y 252 tramos OSM con fecha y hashes. `outputs/infrastructure_risk/` materializa el screening usando costa FES2014 2026 y LRR 2016–2026: cero elementos críticos, cero longitud vial expuesta y cero superficie edificada expuesta con los datos actuales. El estado es `SCREENING_REQUIRES_FIELD_VALIDATION`; los `predios_demo.geojson` siguen siendo solo demostrativos.

## 11. Auditoría de requisitos

```powershell
python scripts/11_build_requirement_status.py
```

El script inspecciona artefactos y genera `outputs/requirement_status.json`. No ejecuta ni simula los pipelines. El estado actual es:

- `overall_status: MVP_UNIFICADO_CON_PENDIENTES_DE_DATOS`;
- `strict_completion: false`;
- seis requisitos: completos;
- marejadas: correlación ejecutada, pero parcial por catálogo oficial incompleto.

La pestaña **Cumplimiento obligatorio** de la app presenta este diagnóstico sin convertir presencia de código en cumplimiento científico.

## 12. Qué es real, demostrativo y pendiente

| Categoría | Contenido |
|---|---|
| Real y activo | OSM, 33 cotas GLO-90, catálogo de 31 escenas, NDWI/FES 2016–2026, 38 LRR, 16 avisos parciales y screening OSM conectado |
| Demostrativo | Línea visible 2017, línea futura, tasas editables, umbrales y predios del visor |
| Implementado con salida parcial | Corrección FES2014, tasas DSAS equivalentes, correlación de marejadas e infraestructura |
| Pendiente crítico | Procesar/revisar 2016 y 2018–2025, corregir once líneas, recalcular tendencias, completar eventos y validar infraestructura |
| Excluido | FES2014 dentro de Git/ZIP, resultados sintéticos del laboratorio tratados como observación real |

## 13. Validación

La suite global posterior a la integración registra **53 pruebas aprobadas en 8,04 s** y conserva JUnit en `outputs/coastvision_mvp/pytest.xml`. Cubre geometría, temporalidad, DEM, adquisición, consenso NDWI, FES2014, cambio, marejadas, infraestructura, conexión del semáforo, RAG y funciones visuales.

El control más importante no es solo unitario: cada línea satelital debe revisarse visualmente, cada corrección debe conservar fecha/modelo/pendiente y toda tasa debe quedar vinculada a las líneas que la generaron.
