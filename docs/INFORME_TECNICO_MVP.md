# Informe técnico complementario — CoastVision MVP

## Resumen ejecutivo

CoastVision es un piloto geoinformático para explorar exposición costera en Playa Grande de Cartagena y avanzar hacia una evaluación multitemporal reproducible. El proyecto cubre 1,87 km de borde, instala 11 transectos con 33 consultas de elevación y ofrece un visor Streamlit/Folium con escenarios editables entre 2026 y 2040. Además, integra un pipeline científico para Sentinel-2 2016–2026, NDWI, corrección FES2014, cambio costero equivalente a DSAS, marejadas e infraestructura.

La distinción principal es metodológica: el **mapa visible sigue siendo demostrativo**. Su línea rotulada 2017, línea futura, tasa, umbrales y predios no son observaciones satelitales ni resultados de DSAS. El pipeline científico está implementado, pero solo existe una extracción NDWI real de 2017; no hay todavía una serie FES2014 corregida completa, tasas reales, correlación final de marejadas ni capas finales de infraestructura en riesgo.

El estado derivado desde artefactos es `MVP_UNIFICADO_CON_PENDIENTES_DE_DATOS` con `strict_completion: false`. De los siete requisitos obligatorios, los siete elementos cartográficos están completos; los seis requisitos científicos se encuentran parciales o pendientes de datos.

## 1. Problema, usuario y objetivo

Los mapas generales de riesgo suelen ocultar dónde se midió, qué dato es observado y qué supuesto produjo cada color. También pueden confundir tres variables distintas: distancia a la costa, elevación del terreno y altura de marea.

El objetivo es ofrecer una herramienta trazable que:

1. cubra toda Playa Grande y muestre exactamente dónde se mide;
2. permita explorar un escenario simple sin presentarlo como pronóstico;
3. extraiga líneas de agua de Sentinel-2 para 2016–2026;
4. corrija cada observación con FES2014 antes de estimar cambio;
5. calcule tasas por transecto con un equivalente DSAS en Python;
6. relacione el cambio con avisos oficiales de marejadas;
7. identifique edificios y caminos potencialmente expuestos;
8. comunique el estado real de cumplimiento en la propia aplicación.

## 2. Alcance funcional

### 2.1 Visor demostrativo operativo

- 1,8689 km de referencia costera;
- estaciones E01–E11 y 11 transectos;
- 33 cotas GLO-90 a 50, 150 y 250 m hacia tierra;
- escenario 2026–2040 y franjas acumulativas;
- evaluación por clic con margen firmado;
- exportación GeoJSON/CSV/JSON;
- TF-IDF local y LLM opcional, sin efecto sobre el riesgo;
- enlaces de verificación externa;
- siete elementos obligatorios del mapa;
- pestaña **Cumplimiento obligatorio**.

### 2.2 Pipeline científico implementado

- catálogo Sentinel-2 estival para los once años 2016–2026;
- NDWI con B03/B08, máscara SCL, alineación de grillas y vectorización;
- predicción/corrección de marea mediante pyTMD y FES2014;
- NSM, EPR, LRR, R², error estándar e IC95 en transectos fijos;
- unión temporal y correlación punto-biserial con marejadas;
- descarga OSM y evaluación de edificios/caminos mediante distancia y LRR local;
- generación automática del estado obligatorio desde artefactos.

### 2.3 Resultados aún no disponibles

- once líneas satelitales revisadas y aceptadas;
- once líneas corregidas por FES2014;
- tasas reales por transecto;
- correlación de marejadas defendible;
- edificios y caminos clasificados con las tasas reales;
- reemplazo del escenario demo por resultados científicos.

## 3. Datos utilizados

| Clase | Dato | Fuente | Condición de uso |
|---|---|---|---|
| Referencia cartográfica | Borde derivado de polígono de playa | OpenStreetMap `way 300607261`, ODbL | Real como geometría de referencia; no es línea de agua 2026 |
| Elevación | 33 cotas GLO-90 | Copernicus DEM vía Open-Meteo | Real, resolución 90 m; solo orientación regional |
| Satélite | 31 escenas Sentinel-2 | Catálogos STAC / Earth Search y Copernicus | 2016 L1C autenticado; 2017–2026 L2A público |
| Observación procesada | NDWI y línea de agua 2017 | B03, B08 y SCL Sentinel-2 | Real, pero preliminar y pendiente de nueva revisión |
| Marea | 34 NetCDF FES2014b externos | Modelo FES2014 usado con pyTMD | Estructura validada; predicción numérica pendiente |
| Marejadas | 16 avisos oficiales | Armada/SERVIMET, metadatos SHOA/DMC | Inventario parcial; años sin filas no indican ausencia |
| Infraestructura | `building=*` y `highway=*` | OpenStreetMap | Pipeline listo; snapshot y evaluación final pendientes |
| Evidencia local | Corpus metodológico | Fuentes curadas del proyecto | Solo RAG; no altera geometrías ni riesgo |
| Escenario | Línea 2017/futura, tasa y umbrales | Reglas del visor | Demostrativo, no observado |
| Sintético | Predios demo | Generación por código | No representan catastro |

Los hashes y recibos base se almacenan en `data/provenance_manifest.json`. El modelo FES2014 permanece fuera del repositorio y de los ZIP debido a su tamaño aproximado de 4,5 GB.

## 4. Metodología

### 4.1 Delimitación y sistema de coordenadas

El polígono OSM `natural=beach` se divide mediante dos anclas auditadas. Entre los dos recorridos se conserva el único arco simple de 1.800–1.950 m. El resultado tiene 69 vértices, mide 1.868,9 m y se orienta norte-sur.

El visor utiliza un corredor de 50 m hacia el mar y 260 m hacia tierra. Para Sentinel-2 se usa una envolvente de 500 m, con bbox WGS84 aproximada:

```text
[-71.6273102, -33.5196197, -71.6046611, -33.4970742]
```

WGS84 (`EPSG:4326`) se usa para APIs y GeoJSON; Leaflet representa el lienzo en Web Mercator (`EPSG:3857`); UTM 19S (`EPSG:32719`) se usa para distancias, offsets y tasas.

### 4.2 Red de medición y elevación

La progresiva se divide en diez intervalos para generar 11 estaciones separadas cerca de 186,9 m. Cada transecto cubre 310 m. Las cotas a 50, 150 y 250 m son consultas puntuales sobre el transecto, no una topografía continua ni altura de marea.

### 4.3 Escenario demostrativo

El visor calcula:

```text
retroceso(y) = max(0, y - 2026) × tasa
```

Para 2035 y 1,5 m/año, el resultado mostrado es 13,5 m. Este valor no describe retroceso observado. Los umbrales de 25 y 60 m son reglas de demostración, y un margen firmado negativo mantiene crítico un punto ya alcanzado.

### 4.4 Sentinel-2 y NDWI

`scripts/06_build_sentinel_catalog.py` genera el catálogo anual. Contiene 31 escenas: una L1C en 2016 y tres L2A por año desde 2017 hasta 2026. La escena L1C exige descarga autenticada; las L2A públicas aportan B03, B08 y SCL.

`scripts/07_process_multitemporal.py` aplica:

```text
NDWI = (B03 - B08) / (B03 + B08)
```

El proceso alinea grillas, enmascara con SCL, segmenta agua, vectoriza y selecciona la línea compatible con la playa. La corrida 2017 obtuvo 53.699 píxeles válidos y 24.995 de agua. El control gráfico muestra una separación importante en el tramo norte; por eso la línea aún no es definitiva.

### 4.5 Corrección FES2014

`src/coastvision/tides.py` predice marea para la fecha de cada escena y desplaza la línea según pendiente y orientación para referirla a nivel medio del mar. La validación estructural encontró 34/34 NetCDF y cabeceras válidas, pero la primera predicción no terminó dentro de la ventana de validación. En consecuencia, `fes2014_corrected_years` está vacío.

### 4.6 Tasas tipo DSAS

`src/coastvision/change_analysis.py` intersecta líneas fechadas con transectos fijos y calcula:

- movimiento neto de la línea de costa (NSM);
- tasa de punto extremo (EPR);
- regresión lineal (LRR);
- R², error estándar e intervalo de confianza del 95 %.

El método está implementado y probado con datos controlados. No hay tasas reales porque se requieren al menos dos líneas FES-corregidas y, para una serie defendible, conviene utilizar los once años disponibles.

### 4.7 Marejadas

`src/coastvision/storms.py` vincula fechas satelitales con ventanas de eventos y calcula anomalías/correlación punto-biserial. El archivo actual reúne 16 avisos oficiales, pero `catalog_complete` es falso. La correlación seguirá siendo exploratoria hasta completar el inventario 2016–2026 y generar tasas reales.

### 4.8 Infraestructura

`scripts/08_refresh_osm_infrastructure.py` descarga edificios y caminos del AOI. `scripts/10_assess_infrastructure.py` cruza cada activo con distancia a la línea más reciente y LRR local, y exporta resultados con hashes. Aún faltan el snapshot actual y las tasas reales, por lo que no existen capas finales de infraestructura en riesgo.

### 4.9 Auditoría de cumplimiento

`scripts/11_build_requirement_status.py` inspecciona archivos presentes y genera `outputs/requirement_status.json`. No ejecuta ni inventa resultados. La aplicación muestra ese diagnóstico en la pestaña **Cumplimiento obligatorio**.

## 5. Arquitectura y tecnologías

La arquitectura separa adquisición, geometría demostrativa, procesamiento raster, marea, análisis de cambio, eventos, infraestructura, auditoría, RAG, interfaz y exportación. Se utilizan Python, Streamlit, Folium, GeoPandas, Rasterio, Shapely, PyProj, Requests, catálogos STAC, pyTMD/FES2014, SciPy y scikit-learn.

La rama demostrativa consume un bundle preparado para que la demo no dependa de internet. La rama científica escribe artefactos separados y solo podrá conectarse al semáforo después de completar y revisar la serie. El detalle de contratos está en [Arquitectura](ARQUITECTURA.md).

## 6. Resultados al corte

| Resultado | Evidencia | Estado |
|---|---|---|
| Cobertura y red | 1,87 km, 11 estaciones, 11 transectos, 33 cotas | Operativo |
| Escenario 2035/1,5 m-año | 13,5 m y capas exportadas | Demostrativo |
| Siete elementos cartográficos | Título, leyenda, escala, norte, fuente/autor, CRS y fecha | Completo |
| Catálogo Sentinel-2 | 31 escenas y ningún año ausente | Completo como catálogo |
| Línea NDWI | Raster, agua, línea y control 2017 | Parcial |
| FES2014 | 34/34 archivos estructuralmente válidos | Parcial, sin predicción |
| Tasas tipo DSAS | Módulo y pruebas específicas | Implementado, sin tasas reales |
| Marejadas | 16 avisos y módulo de correlación | Parcial, sin resultado final |
| Infraestructura | Módulo y scripts reproducibles | Implementado, sin capas finales |
| Estado obligatorio | `strict_completion: false` | Pendientes de datos |

La interfaz permite comprobar que las franjas del escenario cambian con año y tasa y que la línea histórica demo no cambia al editar el futuro. Esa coherencia interna no valida el escenario como dinámica costera real.

## 7. Verificación y evidencia

La suite histórica del visor registra 18 pruebas aprobadas para geometría, temporalidad, clic, DEM, adquisición, hashes y RAG. Existen además pruebas específicas para Sentinel, FES y cambio costero. Después de la última unificación no quedó registrada una nueva ejecución global consolidada; por eso no se reporta un total actualizado superior.

En la aplicación se verificaron sintaxis, siete filas en la auditoría cartográfica, lectura de artefactos y respuesta HTTP 200 del endpoint de salud. La revisión visual final del mapa debe repetirse en navegador antes de presentar.

Las evidencias principales están en:

- [Pipeline y datos](PIPELINE_Y_DATOS.md);
- [Evidencias de la rúbrica](EVIDENCIAS_RUBRICA.md);
- [Guion de demo](DEMO_5_MIN.md);
- `outputs/requirement_status.json`;
- `outputs/multitemporal_validation_v2/`;
- `outputs/fes2014_validation.json`;
- `outputs/coastvision_mvp/pytest.xml`.

## 8. Discusión y limitaciones

El aporte inmediato es la trazabilidad: el usuario puede distinguir una referencia OSM, una observación Sentinel, una proyección demo y un resultado todavía ausente. Esta separación evita que la presencia de código sea presentada como evidencia científica.

Las limitaciones principales son:

- OSM orienta la red, pero no sustituye una línea de agua fechada;
- GLO-90 no resuelve topografía fina, inundación o decisiones prediales;
- 2016 usa L1C, mientras 2017–2026 usan L2A, lo que exige QA radiométrico;
- una sola extracción NDWI no permite estimar cambio;
- la corrección FES2014 depende de fecha, orientación y pendiente;
- el inventario de marejadas no es completo;
- los edificios/caminos solo pueden evaluarse cuando existan línea reciente y LRR reales;
- correlación no implica causalidad.

Por estas razones se mantienen las etiquetas `DEMO_DATA_NOT_FOR_INVESTMENT_DECISIONS` y `PARTIAL_DO_NOT_USE_FOR_DECISIONS`.

## 9. Trabajo prioritario

1. Descargar 2016 de forma autenticada y procesar 2018–2026.
2. Repetir 2017 y revisar visualmente las once líneas, en especial el tramo norte.
3. Completar la predicción FES2014 y corregir cada observación a MSL.
4. Generar intersecciones y tasas NSM/EPR/LRR con incertidumbre real.
5. Completar el inventario oficial de marejadas 2016–2026 y ejecutar la correlación.
6. Descargar el snapshot OSM del AOI y materializar edificios/caminos en riesgo.
7. Ejecutar la suite global y conservar evidencia JUnit actualizada.
8. Conectar resultados al visor solo cuando la auditoría estricta sea positiva.

## 10. Distribución de tareas y uso de IA

| Paquete de trabajo | Evidencia | Responsable |
|---|---|---|
| Problema y validación territorial | Informe PEP, selección y revisión visual | **Completar con nombre real** |
| Datos, delimitación y Sentinel | Snapshots, catálogo, QA de líneas | **Completar con nombre real** |
| FES2014 y cambio costero | Correcciones, intersecciones y tasas | **Completar con nombre real** |
| Marejadas e infraestructura | Catálogo oficial, cruce y capas finales | **Completar con nombre real** |
| App, pruebas y presentación | `app.py`, pruebas, evidencia y demo | **Completar con nombre real** |

Se utilizó Codex para inspeccionar archivos, integrar código, documentar el pipeline y ampliar verificaciones. La IA no es una fuente geográfica y no sustituye la revisión del equipo. Las fuentes, fechas y supuestos deben conservarse en cada artefacto, y los responsables reales deben completarse antes de la entrega.

## 11. Conclusión

CoastVision ya ofrece un MVP útil para explorar Playa Grande, reconocer dónde se mide y comunicar un escenario con sus límites. La unificación añade una ruta científica completa en arquitectura: Sentinel-2 2016–2026, NDWI, FES2014, cambio tipo DSAS, marejadas e infraestructura.

La conclusión debe permanecer prudente. A la fecha, esa ruta está **implementada pero incompleta en datos y resultados**. No existen aún tasas costeras reales, correlación final ni infraestructura clasificada; por lo tanto, el mapa visible continúa siendo demostrativo y no debe usarse como estudio oficial de amenaza o recomendación de inversión.

## Bibliografía y fuentes

- OpenStreetMap contributors. Playa Grande, `way 300607261`. <https://www.openstreetmap.org/way/300607261>. Datos ODbL.
- OpenStreetMap API v0.6. Respuesta completa del way. <https://api.openstreetmap.org/api/0.6/way/300607261/full>.
- Open-Meteo. Elevation API. <https://open-meteo.com/en/docs/elevation-api>.
- Copernicus Data Space Ecosystem. Sentinel-2. <https://dataspace.copernicus.eu/>.
- Element 84. Earth Search STAC. <https://earth-search.aws.element84.com/v1>.
- Vos, K. et al. CoastSat, repositorio oficial. <https://github.com/kvos/CoastSat>.
- pyTMD, documentación y código. <https://github.com/tsutterley/pyTMD>.
- Servicio Meteorológico de la Armada de Chile. <https://meteoarmada.directemar.cl/>.
- Dirección Meteorológica de Chile. <https://www.meteochile.gob.cl/>.
- EPSG Geodetic Parameter Dataset. WGS 84 / UTM zone 19S, EPSG:32719. <https://epsg.io/32719>.
