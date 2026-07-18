# CoastVision MVP — alcance y trazabilidad

## Decisión de alcance

El proyecto se concentra en **Playa Grande de Cartagena** y se divide en dos productos relacionados, pero no equivalentes:

1. **Visor demostrativo:** cubre 1,87 km de costa, muestra estaciones, elevación y un escenario editable 2026–2040. Sus líneas 2017/futura, umbrales y predios son demostrativos.
2. **Pipeline científico 2016–2026:** cataloga Sentinel-2, extrae NDWI, prepara corrección FES2014, calcula cambio tipo DSAS, cruza marejadas e identifica infraestructura OSM en riesgo.

El visor ya es útil para explorar dónde se mide y comunicar supuestos. El pipeline científico está implementado por módulos, pero sus salidas finales siguen incompletas y todavía **no alimentan el semáforo visible**.

## Delimitación y red de medición

- Referencia cartográfica: arco marino derivado del polígono OSM de Playa Grande (`way 300607261`), no una línea de agua observada.
- Cobertura: 1.868,9 m entre latitudes aproximadas `-33.5017` y `-33.5150`.
- Área satelital: envolvente de 500 m alrededor de la playa; bbox WGS84 aproximada `[-71.6273102, -33.5196197, -71.6046611, -33.4970742]`.
- Red: 11 estaciones E01–E11, 11 transectos de 310 m y 33 cotas GLO-90 a 50, 150 y 250 m hacia tierra.
- Cálculos métricos: UTM 19S (`EPSG:32719`); datos/GeoJSON: WGS84 (`EPSG:4326`); lienzo Leaflet: Web Mercator (`EPSG:3857`).

## Funciones del visor

| ID | Historia de usuario | Evidencia | Estado |
|---|---|---|---|
| HU-01 | Ajusto el año y observo un escenario de desplazamiento. | Slider y líneas de escenario. | Terminado, demostrativo |
| HU-02 | Selecciono un punto y recibo nivel, margen firmado y recomendación. | Clic y cálculo en UTM 19S. | Terminado, demostrativo |
| HU-03 | Reconozco dónde se mide a lo largo de toda la playa. | E01–E11 y transectos. | Terminado |
| HU-04 | Comparo latitud y elevación del terreno. | Perfil y tabla DEM a 50/150/250 m. | Terminado |
| HU-05 | Abro Street View, satélite o Google Earth. | Enlaces externos sin clave API. | Terminado |
| HU-06 | Consulto evidencia local. | TF-IDF y LLM opcional. | Terminado |
| HU-07 | Regenero las capas del escenario fuera del notebook. | `scripts/04_build_coastvision_mvp.py`. | Terminado |
| HU-08 | Reconstruyo las fuentes base con trazabilidad. | `scripts/00_refresh_source_data.py`, snapshots y SHA-256. | Terminado |
| HU-09 | Verifico los siete elementos obligatorios del mapa. | Título, leyenda, escala, norte, fuente/autor, CRS y fecha en Folium. | Terminado |
| HU-10 | Reviso el cumplimiento científico sin confundir código con resultados. | Pestaña **Cumplimiento obligatorio** y `outputs/requirement_status.json`. | Terminado |

## Requisitos científicos obligatorios

| Requisito | Implementación | Evidencia disponible | Estado real |
|---|---|---|---|
| Línea costera Sentinel-2 2016–2026 | scripts 06–07 | 31 escenas catalogadas, 28 aceptadas y 11 líneas anuales | Completo con QA reforzado de 2016 |
| NDWI o MNDWI | NDWI B03/B08, SCL cuando existe, mayoría anual y vectorización guiada | Raster, agua y líneas 2016–2026 | Completo |
| DSAS o equivalente Python | `src/coastvision/change_analysis.py` | 39 transectos, 336 intersecciones y 38 LRR válidas | Completo |
| Correlación con marejadas SHOA/DMC | `src/coastvision/storms.py` integrado en script 07 | n=11, r=-0,405, p=0,216 | Ejecutado; catálogo oficial incompleto |
| Infraestructura en riesgo | scripts 08 y 10, edificios/caminos OSM, distancia y LRR local | 38 edificios, 252 caminos y capas clasificadas | Completo como screening |
| Corrección FES2014 | `src/coastvision/tides.py` y script 09 | 28 predicciones y once líneas 2016–2026 | Completo |
| Siete elementos del mapa | `app.py` | Auditoría interna: siete elementos presentes | Completo |

El estado se deriva desde artefactos con `scripts/11_build_requirement_status.py`. Al corte actual declara `MVP_UNIFICADO_CON_PENDIENTES_DE_DATOS` y `strict_completion: false`.

## Semáforo visible y sus límites

En el visor, 2026 es el cero matemático del escenario, no una observación Sentinel-2. La línea rotulada 2017 también es un offset demostrativo; no debe confundirse con las líneas NDWI/FES reales de 2017 y 2026 almacenadas en `outputs/multitemporal/`.

- Alcanzado/crítico: terreno entre la referencia OSM y la línea proyectada.
- Crítico: hasta 25 m tierra adentro de la línea proyectada.
- Precaución: entre 25 y 60 m tierra adentro.
- Bajo en este escenario: más de 60 m dentro del corredor analítico.

La cota DEM, la altura de marea y la distancia a la costa son variables distintas. GLO-90 sirve para orientación regional, no para decisiones prediales, de diseño u obras.

## Criterio de conexión a la aplicación

El pipeline científico solo debe reemplazar el escenario cuando existan:

1. once líneas 2016–2026 revisadas visualmente;
2. corrección FES2014 numérica por fecha;
3. tasas reales por transecto con incertidumbre;
4. catálogo de marejadas suficientemente completo y correlación reproducible;
5. capas de edificios y caminos evaluadas con las tasas reales.

## Riesgos restantes

| Riesgo | Severidad | Mitigación |
|---|---|---|
| Confundir OSM o la línea demo 2017 con una línea de agua observada | Alta | Etiquetas persistentes y separación de ramas |
| Interpretar 31 escenas catalogadas como 11 líneas terminadas | Alta | Estado derivado desde artefactos, no desde presencia de código |
| Confundir DEM con marea | Alta | Variables separadas; FES2014 por escena antes de calcular tasas |
| Usar resultados parciales en decisiones | Alta | `PARTIAL_DO_NOT_USE_FOR_DECISIONS` y `strict_completion: false` |
| Sesgo por inventario incompleto de marejadas | Alta | No tratar años sin filas como ausencia de eventos |
| Resolución vertical insuficiente | Alta | Validación posterior con RTK, dron o LiDAR |

La trazabilidad detallada está en [Pipeline y datos](PIPELINE_Y_DATOS.md), [Arquitectura](ARQUITECTURA.md) y [Evidencias de la rúbrica](EVIDENCIAS_RUBRICA.md).
