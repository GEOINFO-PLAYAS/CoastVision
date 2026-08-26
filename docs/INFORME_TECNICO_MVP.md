# Informe técnico complementario — CoastVision MVP

**Corte de integración verificado:** 26 de agosto de 2026, sobre la base `e6ad572`.

## Resumen ejecutivo

CoastVision es un piloto geoinformático para explorar exposición costera y avanzar hacia una evaluación multitemporal reproducible. El visor Streamlit/Folium permite seleccionar Cartagena, Reñaca, Santo Domingo, Algarrobo y Caleta Portales y mantiene separado el escenario demostrativo de los artefactos científicos persistidos.

Para Cartagena existen 31 intentos de escena, 28 recibos procesados, 11 líneas anuales NDWI/FES2014 entre 2016 y 2026, 39 transectos, 336 intersecciones y 38 LRR válidas. También están persistidos la correlación exploratoria con marejadas y el screening de 38 edificios y 252 tramos viales. Estos artefactos permiten una demo científica reproducible, pero no constituyen un estudio oficial de amenaza ni una recomendación de inversión.

Las otras cuatro playas cuentan con configuración, geometría base y artefactos de integración visual. Sus series almacenadas todavía no incluyen catálogos y recibos Sentinel suficientes: contienen identificadores `dummy_scene_*`, fechas ausentes y valores repetidos. Por ello no se certifican como cuatro cadenas científicas reales. El estado se mantiene en `MVP_UNIFICADO_CON_PENDIENTES_DE_DATOS`, con `strict_completion: false`; el preflight de Cartagena queda en 9/10, con el puerto local como control opcional.

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
- selector dinámico para cinco playas, con salidas aisladas por sitio.

### 2.2 Pipeline científico implementado

- catálogo Sentinel-2 estival para los once años 2016–2026;
- NDWI con B03/B08, máscara SCL, alineación de grillas y vectorización;
- predicción/corrección de marea mediante pyTMD y FES2014;
- NSM, EPR, LRR, R², error estándar e IC95 en transectos fijos;
- unión temporal y correlación punto-biserial con marejadas;
- descarga OSM y evaluación de edificios/caminos mediante distancia y LRR local;
- generación automática del estado obligatorio desde artefactos.
- adaptador reproducible para el motor Rust `strandline`, con preparación, pruebas y benchmark.

### 2.3 Pendientes de cierre

- catálogos, recibos, fechas y QA Sentinel/FES2014 reales para las cuatro playas añadidas;
- conciliación cuantitativa de intersecciones y tasas entre Python y Strandline;
- inventario oficial de marejadas 2016–2026 completo;
- eliminación de rutas absolutas históricas en artefactos regenerados;
- despliegue accesible sin depender del computador de un integrante;
- revisión visual final de cada playa y cierre de la evidencia de entrega.

## 3. Datos utilizados

| Clase | Dato | Fuente | Condición de uso |
|---|---|---|---|
| Referencia cartográfica | Borde derivado de polígono de playa | OpenStreetMap `way 300607261`, ODbL | Real como geometría de referencia; no es línea de agua 2026 |
| Elevación | 33 cotas GLO-90 | Copernicus DEM vía Open-Meteo | Real, resolución 90 m; solo orientación regional |
| Satélite Cartagena | 31 intentos y 28 escenas procesadas Sentinel-2 | Catálogos STAC / Earth Search | Cobertura anual 2016–2026; 2016 usa fallback de una escena y requiere QA visual explícito |
| Observación procesada Cartagena | 11 líneas anuales NDWI | B03, B08 y SCL Sentinel-2 | Artefactos reales persistidos; no equivalen por sí solos a validación de terreno |
| Marea Cartagena | 34 NetCDF FES2014b externos y 28 predicciones | FES2014 mediante pyTMD | Validación numérica ejecutada y 11 líneas anuales corregidas |
| Marejadas | 16 avisos oficiales | Armada/SERVIMET, metadatos SHOA/DMC | Inventario parcial; años sin filas no indican ausencia |
| Infraestructura Cartagena | 38 edificios y 252 tramos viales | OpenStreetMap | Screening ejecutado; requiere validación de campo |
| Extensión multisitio | Configuración, OSM/DEM y outputs de cuatro playas | Archivos del repositorio | Integración visual; procedencia Sentinel/FES2014 todavía no certificada |
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

`scripts/06_build_sentinel_catalog.py` genera el catálogo anual. La evidencia persistida de Cartagena registra 31 intentos, 28 escenas aceptadas y cobertura 2016–2026. En 2016 se utiliza una escena L1C como fallback; desde 2017 se procesan escenas L2A públicas con B03, B08 y SCL.

`scripts/07_process_multitemporal.py` aplica:

```text
NDWI = (B03 - B08) / (B03 + B08)
```

El proceso alinea grillas, enmascara con SCL, segmenta agua, vectoriza, aplica consenso cuando existen escenas suficientes y selecciona la línea compatible con la playa. Se persistieron 11 líneas anuales para Cartagena. La salida de 2016 conserva la advertencia `single_scene_fallback`; todas las líneas requieren revisión visual antes de una interpretación científica externa.

### 4.5 Corrección FES2014

`src/coastvision/tides.py` predice marea para la fecha de cada escena y desplaza la línea según pendiente y orientación para referirla a nivel medio del mar. La evidencia de Cartagena registra 34/34 constituyentes válidos, 28 predicciones numéricas y 11 años corregidos. Los modelos permanecen externos al repositorio y las rutas absolutas históricas de los resúmenes deben regenerarse antes de una entrega portable.

### 4.6 Tasas tipo DSAS

`src/coastvision/change_analysis.py` intersecta líneas fechadas con transectos fijos y calcula:

- movimiento neto de la línea de costa (NSM);
- tasa de punto extremo (EPR);
- regresión lineal (LRR);
- R², error estándar e intervalo de confianza del 95 %.

El cálculo persistido de Cartagena contiene 39 transectos, 336 intersecciones y 38 LRR válidas. La integración de Strandline ejecuta `intersect` y `rates` mediante un adaptador reproducible; todavía debe conciliarse que ambos motores trabajen sobre exactamente las mismas intersecciones y fijar un umbral de aceptación cuantitativo.

### 4.7 Marejadas

`src/coastvision/storms.py` vincula fechas satelitales con ventanas de eventos y calcula anomalías/correlación punto-biserial. La corrida persistida entrega `n=11`, `r=-0,405369` y `p=0,216139`. El catálogo reúne 16 avisos y mantiene `catalog_complete: false`; por ello el resultado es exploratorio y no permite inferir causalidad.

### 4.8 Infraestructura

`scripts/08_refresh_osm_infrastructure.py` descarga edificios y caminos del AOI. `scripts/10_assess_infrastructure.py` cruza cada activo con distancia a la línea más reciente y LRR local. Para Cartagena existen 38 edificios y 252 tramos viales evaluados, sin elementos críticos en el screening persistido. El estado `SCREENING_REQUIRES_FIELD_VALIDATION` impide interpretarlo como catastro oficial.

### 4.9 Auditoría de cumplimiento

`scripts/11_build_requirement_status.py` inspecciona archivos presentes y genera `outputs/requirement_status.json`. `scripts/12_demo_preflight.py` comprueba la cadena persistida de Cartagena y la conexión del semáforo con la aplicación; no certifica la procedencia científica completa de las otras cuatro playas. La aplicación muestra el diagnóstico en la pestaña **Cumplimiento obligatorio**.

## 5. Arquitectura y tecnologías

La arquitectura separa adquisición, configuración multisitio, geometría demostrativa, procesamiento raster, marea, análisis de cambio, eventos, infraestructura, auditoría, RAG, interfaz y exportación. Se utilizan Python, Streamlit, Folium, GeoPandas, Rasterio, Shapely, PyProj, Requests, catálogos STAC, pyTMD/FES2014, SciPy, scikit-learn y el motor Rust Strandline mediante un adaptador explícito.

La rama demostrativa consume bundles preparados para que la demo no dependa de internet. La aplicación carga el bundle científico según `selected_site_slug`; esa conexión no convierte automáticamente un output presente en evidencia científica certificada. El detalle de contratos está en [Arquitectura](ARQUITECTURA.md) y las reglas de integración en `AGENTS.md`.

## 6. Resultados al corte

| Resultado | Evidencia | Estado |
|---|---|---|
| Cobertura y red | 1,87 km, 11 estaciones, 11 transectos, 33 cotas | Operativo |
| Escenario 2035/1,5 m-año | 13,5 m y capas exportadas | Demostrativo |
| Siete elementos cartográficos | Título, leyenda, escala, norte, fuente/autor, CRS y fecha | Completo |
| Cartagena Sentinel/NDWI | 31 intentos, 28 recibos y 11 líneas anuales | Ejecutado; QA visual aún obligatorio |
| Cartagena FES2014 | 34/34 constituyentes, 28 predicciones y 11 años corregidos | Ejecutado |
| Cartagena cambio costero | 39 transectos, 336 intersecciones y 38 LRR válidas | Ejecutado |
| Strandline | Adaptador, dos pruebas, setup y benchmark reproducibles | Integrado; comparación final pendiente |
| Marejadas | `n=11`, `r=-0,405369`, `p=0,216139` | Ejecutado, catálogo oficial incompleto |
| Infraestructura Cartagena | 38 edificios y 252 tramos viales | Screening ejecutado; requiere terreno |
| Reñaca, Santo Domingo, Algarrobo y Caleta Portales | Selector, configuración y artefactos visuales | Integración demo; ciencia no certificada |
| Estado obligatorio | `strict_completion: false` | Pendientes de datos |

La interfaz permite comprobar que las franjas del escenario cambian con año y tasa y que la línea histórica demo no cambia al editar el futuro. Esa coherencia interna no valida el escenario como dinámica costera real.

## 7. Verificación y evidencia

La verificación global del 26 de agosto de 2026 terminó con **58 pruebas aprobadas de 58** en 9,90 s y actualizó `outputs/coastvision_mvp/pytest.xml`. Incluye geometría, temporalidad, clic, DEM, adquisición, procedencia, Sentinel, FES2014, cambio costero, infraestructura, configuración multisitio y adaptador Strandline.

El preflight actualizado terminó con código 0, `demo_ready: true` y 9/10 controles; el único control negativo fue el puerto 8501, que es opcional cuando la aplicación no está iniciada. `scientific_requirements_complete` permanece falso y la revisión visual final del mapa debe repetirse en navegador antes de presentar.

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
- 2016 utiliza una sola escena como fallback y necesita QA visual;
- las cuatro playas añadidas no poseen aún catálogos y recibos multitemporales suficientes;
- la corrección FES2014 depende de fecha, orientación y pendiente y usa modelos externos;
- Strandline y Python deben compararse sobre las mismas intersecciones antes de declarar equivalencia;
- el inventario de marejadas no es completo;
- el screening OSM no reemplaza catastro ni validación de campo;
- algunos artefactos conservan rutas absolutas históricas y no prueban una ejecución fresca;
- todavía no existe un despliegue accesible independiente del computador local;
- correlación no implica causalidad.

Por estas razones se mantienen las etiquetas `DEMO_DATA_NOT_FOR_INVESTMENT_DECISIONS` y `PARTIAL_DO_NOT_USE_FOR_DECISIONS`.

## 9. Trabajo prioritario

1. Pablo valida `sites.json`, AOI, CRS y rutas relativas de las cinco playas.
2. Emir reemplaza los outputs demostrativos de las cuatro playas por catálogos, recibos y escenas reales con QA.
3. Sebastián ejecuta FES2014, tasas y Strandline sobre esas entradas y concilia ambos motores.
4. Daniel completa marejadas, infraestructura y el despliegue portable.
5. Nicolás actualiza hashes, preflight, pruebas, evidencias e informe después de recibir los artefactos aceptados.
6. El equipo realiza revisión visual, prueba la URL de despliegue y aprueba el diff final.

## 10. Distribución de tareas y uso de IA

| Paquete de trabajo | Evidencia | Responsable |
|---|---|---|
| Reglas, pruebas, procedencia, integración e informe | `AGENTS.md`, manifiesto, pytest, preflight e informe | Nicolás (`xshift007`) |
| Configuración de sitios y aplicación dinámica | `sites.json`, rutas y selector | Pablo Macuada |
| Datos, delimitación y Sentinel de playas | Catálogos, snapshots, recibos y QA | Emir Silva |
| FES2014, cambio costero y Strandline | Correcciones, intersecciones, tasas y benchmark | Sebastián Figueroa Retamal |
| Marejadas, infraestructura y despliegue | Catálogo oficial, capas y acceso portable | Daniel Eguiuluz |

Se utilizó Codex para inspeccionar archivos, integrar código, documentar el pipeline y ampliar verificaciones. La IA no es una fuente geográfica y no sustituye la revisión del equipo. Las fuentes, fechas y supuestos deben conservarse en cada artefacto; los responsables consignados deben revisar y aprobar su evidencia antes de la entrega.

## 11. Conclusión

CoastVision ofrece un MVP multisitio útil para reconocer dónde se mide, explorar escenarios y comunicar sus límites. Para Cartagena existe una cadena persistida Sentinel-2 2016–2026, NDWI, FES2014, cambio tipo DSAS, correlación exploratoria e infraestructura, además de una integración reproducible con Strandline.

La conclusión debe permanecer prudente. `strict_completion` sigue falso por la cobertura incompleta de marejadas, el QA pendiente, la ausencia de despliegue y la procedencia aún no certificada de Reñaca, Santo Domingo, Algarrobo y Caleta Portales. Esas cuatro extensiones se consideran integración demostrativa hasta regenerarlas con fuentes trazables. Ningún resultado debe usarse como estudio oficial de amenaza o recomendación de inversión.

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
