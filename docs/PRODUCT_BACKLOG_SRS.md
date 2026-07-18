# Product Backlog y SRS trazable

**Producto:** CoastVision  
**Caso piloto:** Playa Grande de Cartagena  
**Corte verificable:** 16 de julio de 2026  
**Regla de estado:** una historia solo queda terminada si existe salida persistida y verificable; tener una función en el código no basta.

## Visión del MVP

CoastVision permite explorar la zona de medición de Playa Grande, consultar latitud, longitud, progresiva y elevación, comparar escenarios y revisar evidencia científica de cambio costero. El MVP separa el visor demostrativo del pipeline científico para no convertir supuestos en observaciones reales.

## Actores

- **Analista costero:** ejecuta NDWI, FES2014 y tasas tipo DSAS.
- **Planificador o evaluador territorial:** consulta exposición de edificios y caminos.
- **Equipo docente:** verifica arquitectura, evidencia, pruebas y demo.
- **Usuario de la demo:** explora estaciones, capas, perfil y estado de cumplimiento.

## Product Backlog priorizado

| ID | Historia de usuario | Prioridad | Estado verificable | Criterio de aceptación | Evidencia |
|---|---|---:|---|---|---|
| US-01 | Como usuario quiero ver toda Playa Grande para no evaluar solo un tramo. | P0 | Terminado | Cobertura costera entre 1,80 y 1,95 km, encuadre completo y AOI ampliada. | `outputs/coastvision_mvp/resumen.json`, `tests/test_mvp.py` |
| US-02 | Como usuario quiero estaciones ordenadas norte-sur con coordenadas para saber dónde se mide. | P0 | Terminado | 11 estaciones equiespaciadas, latitud/longitud, progresiva y popup. | `outputs/coastvision_mvp/estaciones_medicion.geojson`, app |
| US-03 | Como usuario quiero cotas a varias distancias para reconocer sectores bajos. | P0 | Terminado | 33 muestras GLO-90 a 50/150/250 m y perfil exportable. | `perfil_elevacion.csv`, app, pruebas |
| US-04 | Como evaluador quiero los siete elementos cartográficos obligatorios. | P0 | Terminado | Título, leyenda, escala, norte, fuente/autor, CRS/proyección y fecha visibles. | `app.py`, `scripts/12_demo_preflight.py` |
| US-05 | Como analista quiero catalogar Sentinel-2 2016-2026. | P0 | Terminado | Existe al menos una escena candidata por cada año y recibos trazables. | 31 escenas; ningún año ausente |
| US-06 | Como analista quiero extraer líneas de agua con NDWI robusto. | P0 | Terminado | B03/B08, SCL cuando existe, grillas alineadas y consenso estricto. | 28 escenas y 11 líneas anuales |
| US-07 | Como analista quiero corregir cada escena con FES2014 antes de calcular tendencias. | P0 | Terminado | Predicción numérica válida y corrección por fecha previa a la mediana anual. | 34/34; 28 correcciones; 2016–2026 |
| US-08 | Como analista quiero tasas NSM/EPR/LRR por transecto. | P0 | Terminado | Tasas, R², error e IC95 exportados desde la serie corregida. | 39 transectos, 336 intersecciones, 38 LRR válidas |
| US-09 | Como analista quiero correlacionar cambio con marejadas oficiales. | P0 | Parcial | Unión temporal persistida, coeficiente, p-valor, n y cobertura de catálogo. | n=11, r=-0,405, p=0,216; catálogo oficial incompleto |
| US-10 | Como planificador quiero ver edificios y caminos reales del AOI. | P0 | Terminado | Snapshot OSM con fecha, consulta, hashes y conteos. | 38 edificios y 252 tramos en `data/infrastructure/` |
| US-11 | Como planificador quiero un screening de infraestructura expuesta. | P0 | Parcial ejecutado | Distancia a línea 2026, LRR local, horizonte y clase exportados. | `outputs/infrastructure_risk/`; requiere serie completa y validación de campo |
| US-12 | Como usuario quiero distinguir datos reales, demo y pendientes. | P0 | Terminado | La app no presenta escenarios como resultados satelitales y muestra estado derivado. | Pestaña Cumplimiento, `requirement_status.json` |
| US-13 | Como usuario quiero consultar evidencia con RAG aunque no exista API externa. | P1 | Terminado | Recuperación TF-IDF local y LLM opcional que no modifica cálculos. | `src/coastvision/rag.py`, pruebas |
| US-14 | Como presentador quiero una demo reproducible sin descargas en vivo. | P0 | Terminado | Arranque local, bundle preparado, guion de 5 min y preflight automático. | `scripts/run_mvp.py`, `scripts/12_demo_preflight.py`, `docs/DEMO_5_MIN.md` |
| US-15 | Como equipo quiero versiones incrementales verificables. | P1 | Terminado | 10 ZIP, manifiesto y SHA-256 sin FES2014 ni secretos. | `versiones_incrementales/` |

## SRS - requisitos funcionales

| ID | Requisito funcional | Entrada | Salida | Verificación |
|---|---|---|---|---|
| RF-01 | Delimitar el arco costero completo desde OSM way 300607261. | XML/GeoJSON OSM | Línea WGS84 orientada norte-sur | Longitud, vértices, extremos y tests geométricos |
| RF-02 | Construir red de estaciones y transectos en UTM 19S. | Línea base | Estaciones, progresivas y transectos | EPSG:32719, espaciado y orientación |
| RF-03 | Calcular NDWI = (B03-B08)/(B03+B08) con máscara SCL. | COG Sentinel-2 L2A | Raster NDWI, agua y línea | Conteos de píxeles, CRS y recibos por escena |
| RF-04 | Combinar escenas del mismo año por mayoría estricta. | Dos o más extracciones válidas | Línea anual y metadatos de variabilidad | `scene_count`, método y CV de área |
| RF-05 | Predecir marea FES2014 en fecha/hora UTC. | Latitud, longitud, fecha y modelo externo | Altura de marea en metros | Predicción finita y 34/34 constituyentes |
| RF-06 | Corregir cada línea de agua a MSL antes de la agregación anual. | Línea, altura de marea y pendiente | Línea corregida y desplazamiento horizontal | CSV de 28 correcciones y GeoJSON anual 2016–2026 |
| RF-07 | Calcular equivalente DSAS en transectos fijos. | Líneas corregidas | NSM, EPR, LRR, R², SE e IC95 | CSV/GeoJSON y pruebas unitarias |
| RF-08 | Asociar escenas con eventos oficiales y calcular correlación. | Fechas, anomalías y catálogo | Unión, r, p, n y estado | No declarar resultado con muestra insuficiente |
| RF-09 | Descargar infraestructura OSM del AOI. | BBOX derivada de buffer UTM | Edificios, caminos y recibo | Conteos y SHA-256 |
| RF-10 | Evaluar infraestructura contra línea reciente y LRR local. | OSM, costa 2026 y tasas | Capas de screening y resumen | Estado `SCREENING_REQUIRES_FIELD_VALIDATION` |
| RF-11 | Presentar mapa interactivo con controles y exportaciones. | Bundles preparados | Streamlit/Folium | Preflight, salud HTTP y QA visual |
| RF-12 | Auditar requisitos desde artefactos persistidos. | Outputs reales | Matriz de estado | `strict_completion` solo true con serie completa |

## SRS - requisitos no funcionales

- **RNF-01 Reproducibilidad:** cada descarga conserva proveedor, URL/consulta, fecha y hash cuando corresponde.
- **RNF-02 Exactitud espacial:** distancias y áreas se calculan en EPSG:32719; WGS84 se usa para intercambio y EPSG:3857 para visualización web.
- **RNF-03 Transparencia:** los escenarios demostrativos, resultados exploratorios y resultados completos usan etiquetas distintas.
- **RNF-04 Operación offline de la demo:** la interacción principal no depende de descargar Sentinel, OSM o FES durante la presentación.
- **RNF-05 Seguridad:** FES2014, claves, entornos y caches no entran en ZIP ni control de versiones.
- **RNF-06 Testabilidad:** geometría, NDWI, mareas, cambio, infraestructura, marejadas, RAG y funciones visuales tienen pruebas automatizadas.
- **RNF-07 Rendimiento:** la app consume artefactos preparados; las tareas pesadas se ejecutan en scripts separados.
- **RNF-08 Usabilidad:** el mapa cubre la playa completa, permite capas selectivas y explica latitud, elevación, marea y riesgo sin mezclarlas.

## Definición de terminado

Un requisito científico se considera terminado solamente cuando:

1. el código existe y tiene pruebas;
2. la ejecución usa datos reales trazables;
3. la salida se persiste con CRS, fecha, parámetros y procedencia;
4. la cobertura temporal exigida está completa;
5. el control visual y las limitaciones están documentados;
6. `outputs/requirement_status.json` puede derivar el estado sin edición manual.

Por esta definición, el MVP está listo para demostración, pero el pipeline científico obligatorio aún no está terminado para 2016-2026.
