# QA multisitio PEP2 — CoastVision

**Estado:** Completo — sin campos pendientes de llenar
**Corte de la evidencia técnica:** 26-08-2026
**Reverificación documental sobre el repositorio:** 27-08-2026
**Rama recomendada por la pauta:** `pep2/qa-comercial-sebastian` (no existe en el
repositorio; ver §7)
**Rama/commit de cierre:** `main` @ `ead672e3dc8f9ea0dcddcb79c0b90c236d75dc2e`
("Corrige procedencia LF, preflight por playa y define AGENTS.md", 26-08-2026),
árbol de trabajo limpio
**Responsable de consolidación:** Nicolás (`xshift007`)

> Este documento implementa la matriz solicitada en la pauta PEP2. Una fila o
> celda marcada como `DEMO`, `PARCIAL` o `BLOQUEADO` no puede presentarse como
> validación científica completa.

> **Regla de llenado aplicada:** ninguna celda se completó con un valor supuesto.
> Cada número, ruta y hash de este documento se leyó de un artefacto que existe
> en el repositorio; §7 lista los comandos exactos con que se reverificó. Lo que
> no está ejecutado se declara como no ejecutado, no como aprobado.

## 1. Objetivo y criterio de aceptación

Validar la versión que se presentará de CoastVision para las cinco playas y
separar claramente la integración visual, los outputs reproducibles y la
procedencia científica certificada.

Una playa queda **científicamente validada** solo cuando:

1. su configuración, AOI, CRS y rutas son correctos y relativos al repositorio;
2. el pipeline ejecutado tiene catálogo, recibos, fechas, parámetros y QA;
3. los outputs esperados existen y corresponden a esa playa;
4. el mapa y el selector muestran la playa correcta;
5. las métricas se pueden rastrear hasta sus artefactos;
6. la procedencia diferencia datos reales, demostrativos y parciales;
7. los outputs están aislados de los demás sitios;
8. las descargas generan archivos que se pueden abrir y atribuir al sitio;
9. se conserva el comando, resultado, fecha, responsable y evidencia visual.

`demo_ready: true` no equivale a `strict_completion: true`. El preflight
persistido comprueba la cadena científica de Cartagena y advierte explícitamente
que no certifica las otras cuatro playas
(`evaluated_scientific_scope: "cartagena_persisted_outputs"`).

## 2. Resumen verificable al corte

- `data/config/sites.json` contiene los cinco identificadores válidos:
  `cartagena`, `renaca`, `santo_domingo`, `algarrobo` y `caleta_portales`. Una
  sexta clave, `playa_invalida`, es un *fixture* deliberado con AOI `[0,0,0,0]`
  que `src/coastvision/geometry.py:52` rechaza; no se muestra como playa.
- Todas las configuraciones declaran `EPSG:32719`, AOI, fuente y directorio
  de salida relativo (`outputs`, `outputs/renaca`, `outputs/santo_domingo`,
  `outputs/algarrobo`, `outputs/caleta_portales`).
- Cartagena tiene la cadena persistida de Sentinel-2/NDWI, FES2014 y cambio
  costero: 31 intentos de escena (28 `candidate_cache_success` y 3 `failed` por
  cobertura NDWI insuficiente), 28 recibos procesados, 11 años, 39 transectos,
  429 pares transecto-año de los cuales 336 encontraron intersección y 38 LRR
  válidas.
- Cartagena tiene un screening persistido de 38 edificios y 252 tramos viales,
  con 0 elementos críticos y `SCREENING_REQUIRES_FIELD_VALIDATION`.
- El estado obligatorio persistido es `MVP_UNIFICADO_CON_PENDIENTES_DE_DATOS`,
  con `strict_completion: false`.
- El propio `pipeline_summary.json` de Cartagena se autodeclara
  `status: PARTIAL_DO_NOT_USE_FOR_DECISIONS`, con
  `storm_requirement_complete: false` y `pipeline_complete_2016_2026: false`.
- El preflight persistido registra `demo_ready: true`, 9/10 controles y un
  único control negativo, que además es opcional: el puerto local 8501.
- Reñaca, Santo Domingo, Algarrobo y Caleta Portales tienen configuración,
  geometrías y outputs de integración, pero sus salidas multitemporales
  contienen `dummy_scene_*`, valores repetidos de marea y no tienen catálogos
  ni recibos Sentinel: sus `pipeline_summary.json` traen `scene_attempts` y
  `scene_receipts` vacíos (0 y 0, contra 31 y 28 en Cartagena).
- **Prueba dura de que esas cuatro salidas no son observaciones independientes:**
  sus `tide_corrections.csv` son idénticos byte a byte entre sí
  (`sha256 affc8aff…`), igual que sus `storm_correlation.json`
  (`sha256 335f5aa1…`, con el mismo `r=-0.25` y `p=0.45` en las cuatro playas).
  Dos playas separadas por 70 km no pueden compartir la misma serie de mareas.
- La suite persistida terminó con **58/58 pruebas aprobadas**, 0 fallos, 0
  errores y 0 omitidas en 4,880 s
  (`outputs/coastvision_mvp/pytest.xml`, 26-08-2026 15:22:53-04:00). El árbol
  actual sigue declarando exactamente 58 funciones `test_*`, de modo que el
  conteo del log corresponde a la suite vigente.

## 3. Matriz por playa

### 3.1 Matriz de aceptación

| Playa | Configuración | Pipeline | Outputs | Mapa | Métricas | Procedencia | Aislamiento | Descarga | Estado global | Responsable principal |
|---|---|---|---|---|---|---|---|---|---|---|
| Cartagena | `OK` — AOI y `EPSG:32719` en `data/config/sites.json`; salida histórica `outputs/` | `PARCIAL` — NDWI/FES/LRR persistidos con 28 recibos; catálogo oficial de marejadas incompleto (faltan 2022, 2023 y 2025) | `OK` — 22 artefactos en `outputs/multitemporal/` + riesgo + MVP | `OK` — 7 elementos cartográficos en `app.py:add_cartographic_elements` | `OK` con limitaciones: 39 transectos, 336 intersecciones, 38 LRR; marejadas `n=11` | `PARCIAL` — fuentes y recibos presentes; 2016 usa fallback L1C, FES externo y 5 artefactos con rutas absolutas (QA-006) | `PARCIAL` — usa la ruta histórica `outputs/`, documentada como excepción en §3.2 | `OK` — CSV y GeoJSON descargados correctamente | `VALIDADA CON LIMITACIONES` | Emir / Sebastián; cierre Nicolás |
| Reñaca | `OK` — `outputs/renaca/` y `EPSG:32719` | `DEMO` — el resumen declara 11 años, pero trae 0 intentos y 0 recibos de escena | `OK` como integración: 8 artefactos (pipeline, shoreline, tide, rates e infraestructura) | `OK` en selector; 114 muestras DEM propias (38 estaciones × 3 offsets) | `PARCIAL` — screening: 142 edificios, 312 tramos; 0 críticos; 10,7 m² expuestos | `BLOQUEADO` — `dummy_scene_*`, marea constante y archivo idéntico al de las otras 3 playas | `OK` — ruta bajo `outputs/renaca/`; shoreline y rates sí son propios (hashes distintos) | `OK` — CSV y GeoJSON descargados correctamente | `DEMO — NO CIENTÍFICA` | Emir (insumos); Nicolás (procedencia) |
| Santo Domingo | `OK` — `outputs/santo_domingo/` y `EPSG:32719` | `DEMO` — 0 intentos y 0 recibos de escena | `OK` como integración; 8 artefactos aislados | `OK` en selector; 114 muestras DEM propias | `PARCIAL` — screening: 39 edificios, 151 tramos, 2 tramos críticos y 702,7 m expuestos | `BLOQUEADO` — `dummy_scene_*`, marea constante y archivo idéntico al de las otras 3 playas | `OK` — ruta bajo `outputs/santo_domingo/` | `OK` — CSV y GeoJSON descargados correctamente | `DEMO — NO CIENTÍFICA` | Emir (insumos); Nicolás (procedencia) |
| Algarrobo | `OK` — `outputs/algarrobo/` y `EPSG:32719` | `DEMO` — 0 intentos y 0 recibos de escena | `OK` como integración; 8 artefactos aislados | `OK` en selector; 114 muestras DEM propias | `PARCIAL` — screening: 380 edificios, 412 tramos, 1 edificio y 6 tramos críticos | `BLOQUEADO` — `dummy_scene_*`, marea constante y archivo idéntico al de las otras 3 playas | `OK` — ruta bajo `outputs/algarrobo/` | `OK` — CSV y GeoJSON descargados correctamente | `DEMO — NO CIENTÍFICA` | Emir (insumos); Nicolás (procedencia) |
| Caleta Portales | `OK` — `outputs/caleta_portales/` y `EPSG:32719` | `DEMO` — 0 intentos y 0 recibos de escena | `OK` como integración; 8 artefactos aislados | `OK` en selector; 114 muestras DEM propias | `PARCIAL` — screening: 319 edificios, 422 tramos, 1 edificio y 10 tramos críticos | `BLOQUEADO` — `dummy_scene_*`, marea constante y archivo idéntico al de las otras 3 playas | `OK` — ruta bajo `outputs/caleta_portales/` | `OK` — CSV y GeoJSON descargados correctamente | `DEMO — NO CIENTÍFICA` | Emir (insumos); Nicolás (procedencia) |

### 3.2 Detalle de evidencia por playa

Fichas completadas con los artefactos presentes en el repositorio al 27-08-2026.
Todas las rutas son relativas a la raíz del repositorio `CoastVision/`.

#### Cartagena

- **Configuración:** `data/config/sites.json`, clave `cartagena`; AOI
  `[-71.6273102, -33.5196197, -71.6046611, -33.4970742]`; `EPSG:32719`;
  11 estaciones; centro `[-33.5083, -71.6154]`.
- **Pipeline:** `outputs/multitemporal/pipeline_summary.json`;
  Sentinel-2 2016–2026, 31 intentos, 28 escenas procesadas con recibo
  individual y 11 años corregidos con FES2014b. Método anual:
  `strict_majority_consensus_with_single_scene_fallback` (máx. 3 escenas/año,
  mínimo 2 para consenso).
- **Marea:** `outputs/fes2014_validation.json` — FES2014b `ocean_tide`, 34/34
  constituyentes, 0 faltantes, 0 cabeceras HDF5 inválidas,
  `numeric_prediction_validated: true`, 28 predicciones numéricas y 11 años
  corregidos. `outputs/multitemporal/tide_corrections.csv` trae 28 filas con
  `acquired_at_utc`, `tide_height_m`, `beach_slope`, `horizontal_shift_m`,
  datum MSL y la convención de signo explícita.
- **Outputs:** `outputs/multitemporal/` (22 archivos, incluidas
  `water_2016.geojson` … `water_2026.geojson`),
  `outputs/infrastructure_risk/` y `outputs/coastvision_mvp/`.
- **Mapa:** siete elementos cartográficos documentados en `app.py`
  (`add_cartographic_elements`), verificados por el control `seven_map_elements`
  del preflight.
- **Métricas:** 39 transectos y 429 pares transecto-año, de los cuales 336
  registran intersección; 38 LRR válidas (37 `ok` y 1
  `ok_without_lrr_uncertainty`) y 1 transecto `insufficient_observations`.
  LRR entre −6,983 y +0,042 m/año, media −3,033 m/año; con la convención
  declarada (`positive = landward_retreat`) la media negativa indica acreción
  neta en la serie 2016–2026, no retroceso.
- **Marejadas:** `outputs/multitemporal/storm_correlation.json` — punto-biserial,
  `n=11` (2 años con evento y 9 sin evento), `r=-0.405369`, `p=0.216139`,
  `catalog_scope: partial_verified_official_notices`, sin registros verificados
  para 2022, 2023 y 2025, `decision_status: EXPLORATORY_NOT_VALID_FOR_DECISIONS`.
- **Infraestructura:** `outputs/infrastructure_risk/summary.json` — 38 edificios,
  252 tramos, 0 críticos, 0,0 m de camino y 0,0 m² de edificación expuestos,
  horizonte 30 años, `SCREENING_REQUIRES_FIELD_VALIDATION`.
- **Excepción de aislamiento (criterio 7):** Cartagena escribe en `outputs/`
  y no en `outputs/cartagena/` porque es la ruta histórica del MVP; la
  bifurcación está en `app.py:170` y en `src/coastvision/geometry.py:54`. No
  hay colisión con los otros sitios, que sí cuelgan de `outputs/<site>/`, pero
  la excepción queda registrada aquí en vez de corregirse antes de la entrega.
- **Limitaciones:** catálogo de marejadas parcial, QA visual de 2016 pendiente,
  fallback L1C en 2016 (`radiometric_warning` explícito en el propio resumen),
  modelo FES2014 externo no versionado y rutas absolutas heredadas (QA-006).

#### Reñaca

- **Configuración:** clave `renaca`; AOI `[-71.552, -32.975, -71.538, -32.960]`;
  `outputs/renaca/`; `EPSG:32719`; 38 estaciones.
- **Pipeline almacenado:** `outputs/renaca/multitemporal/` (5 archivos) e
  `outputs/renaca/infrastructure_risk/` (3 archivos).
- **Evidencia que bloquea la certificación:**
  `outputs/renaca/multitemporal/tide_corrections.csv` tiene 28 filas del tipo
  `2016,dummy_scene_2016_0,0.12,2.4`, con `tide_m` y `correction_m` constantes;
  el archivo es idéntico byte a byte al de Santo Domingo, Algarrobo y Caleta
  Portales (`sha256 affc8aff…`). `pipeline_summary.json` declara 11 años
  corregidos pero no incluye `scene_attempts` ni `scene_receipts`.
  `storm_correlation.json` también es el mismo archivo en las cuatro playas.
- **Datos que sí son propios del sitio:** `shorelines_2016_2026_fes2014.geojson`
  y `transect_rates.geojson` tienen hash distinto por playa, y
  `data/renaca_elevation_profile_open_meteo.json` trae 114 muestras DEM propias.
- **Infraestructura almacenada:** 142 edificios, 312 tramos, 0 críticos,
  0,0 m de camino y 10,7 m² de edificación expuestos.
- **Clasificación para la presentación:** integración visual/demo; no afirmar
  Sentinel-2/FES2014 científico hasta regenerar y auditar los insumos.

#### Santo Domingo

- **Configuración:** clave `santo_domingo`; AOI
  `[-71.645, -33.645, -71.625, -33.630]`; `outputs/santo_domingo/`;
  `EPSG:32719`; 38 estaciones.
- **Pipeline almacenado:** `outputs/santo_domingo/multitemporal/`.
- **Evidencia que bloquea la certificación:** 28 filas `dummy_scene_*` con
  `0.12` m de marea y `2.4` m de corrección repetidos; archivo idéntico al de
  las otras tres playas demo; 0 intentos y 0 recibos de escena.
- **Infraestructura almacenada:** 39 edificios, 151 tramos, 0 edificios y 2
  tramos críticos, 702,7 m de camino expuestos y 0,0 m² de edificación.
- **Clasificación para la presentación:** integración visual/demo; no afirmar
  resultado científico.

#### Algarrobo

- **Configuración:** clave `algarrobo`; AOI
  `[-71.675, -33.375, -71.655, -33.355]`; `outputs/algarrobo/`; `EPSG:32719`;
  38 estaciones.
- **Pipeline almacenado:** `outputs/algarrobo/multitemporal/`.
- **Evidencia que bloquea la certificación:** 28 filas `dummy_scene_*` con
  `0.12` m y `2.4` m repetidos; archivo idéntico al de las otras tres playas
  demo; 0 intentos y 0 recibos de escena.
- **Infraestructura almacenada:** 380 edificios, 412 tramos, 1 edificio y 6
  tramos críticos, 2.197,3 m expuestos y 979,9 m² de área expuesta.
- **Clasificación para la presentación:** integración visual/demo; no afirmar
  resultado científico.

#### Caleta Portales

- **Configuración:** clave `caleta_portales`; AOI
  `[-71.615, -33.035, -71.595, -33.020]`; `outputs/caleta_portales/`;
  `EPSG:32719`; 38 estaciones.
- **Pipeline almacenado:** `outputs/caleta_portales/multitemporal/`.
- **Evidencia que bloquea la certificación:** 28 filas `dummy_scene_*` con
  `0.12` m y `2.4` m repetidos; archivo idéntico al de las otras tres playas
  demo; 0 intentos y 0 recibos de escena.
- **Infraestructura almacenada:** 319 edificios, 422 tramos, 1 edificio y 10
  tramos críticos, 1.183,5 m expuestos y 2.607,9 m² de área expuesta.
- **Clasificación para la presentación:** integración visual/demo; no afirmar
  resultado científico.

## 4. Registro de fallas, discrepancias y observaciones

Una discrepancia de integridad también se registra aunque no produzca un
crash. El mensaje se copia literalmente cuando existe. Para una falla visual se
adjunta captura sanitizada; para una falla de consola se conserva el log y se
escribe `N/A — consola` en la columna de captura, según la propia regla de esta
sección.

| ID | Playa/modo | Comando, URL o acción exacta | Resultado/mensaje completo | Captura o log | Severidad | Responsable | Estado |
|---|---|---|---|---|---|---|---|
| QA-001 | Reñaca, Santo Domingo, Algarrobo y Caleta Portales / modo científico | Abrir el visor y seleccionar cada playa; revisar `app.py:845` y `src/coastvision/scientific.py:41` | **Discrepancia confirmada por lectura de código y de datos:** `scientific_pipeline_ready()` solo valida cobertura de años y existencia de archivos, no la autenticidad de las escenas, de modo que devuelve `ready` para las cuatro playas demo y `app.py:845` ofrece el modo `Científico FES2014 + LRR` sobre outputs que contienen `dummy_scene_*` y mareas constantes. No es un crash: es una sobreafirmación de procedencia. | `outputs/<site>/multitemporal/tide_corrections.csv` (idénticos, `sha256 affc8aff…`) y `outputs/<site>/multitemporal/storm_correlation.json` (idénticos, `sha256 335f5aa1…`) | **P1 — bloquea presentación científica** | Emir (regenerar insumos); Nicolás (endurecer el gate y cerrar procedencia) | ABIERTO — mitigación acordada: presentar esas playas rotuladas como demo y no abrir el modo científico en ellas durante la exposición |
| QA-002 | Cualquier playa / gráficos del visor | Abrir la URL desplegada y revisar la consola del navegador | `WARN Infinite extent for field "Latitud": [Infinity, -Infinity]` y `WARN Infinite extent for field "value -- streamlit-generated": [Infinity, -Infinity]` | `N/A — consola`; código en `app.py:1125` (`st.line_chart`) | P3 — cosmética, sin impacto funcional | Nicolás (cierre documental) | CERRADO — 27-08-2026. Advertencia de Vega-Lite en el pase de render sin datos del rerun de Streamlit. Se descartó dato vacío: los cinco perfiles DEM tienen muestras (33 en Cartagena y 114 en cada una de las otras cuatro), por lo que el gráfico sí tiene dominio finito una vez cargado. No altera la figura ni las métricas. |
| QA-003 | Cualquier playa / mapa y evaluación por clic | Hacer clic manualmente en el mapa, cambiar playa y repetir | En una automatización de revisión Lat/Lon no cambiaban tras el clic. | `N/A — consola`; código en `app.py:1016-1028` y `app.py:1105` | P3 — falso positivo de la automatización | Nicolás (cierre documental) | CERRADO — 27-08-2026. Revisión estática del flujo completo: `st_folium(..., returned_objects=["last_clicked"], key=f"coast-map-{selected_site_slug}")` guarda el clic en `st.session_state.selected_location` y fuerza `st.rerun()`; `app.py:1105` reimprime `Lat/Lon` desde ese estado. El síntoma se explica porque un cliente headless no genera el evento `last_clicked`, no por un defecto del visor. |
| QA-004 | Demo local / preflight | `python scripts/12_demo_preflight.py` | `streamlit_port_8501`: `passed: false`; evidencia `tcp://127.0.0.1:8501`; nota: `Si falla, iniciar con python scripts/run_mvp.py.` Es un control opcional (`required_for_demo: false`) y no impide `demo_ready`. | `outputs/demo_preflight.json` | P3 — opcional | Daniel (despliegue) | DOCUMENTADO |
| QA-005 | Cartagena / Sentinel-2 2016 | Revisar `outputs/multitemporal/pipeline_summary.json` y el recibo de `S2A_19HBC_20160204_0_L1C` | El recibo 2016 declara `processing_level: L1C`, `cloud_cover_pct: 35.42`, `scl_asset: null` y `data_status: public_l1c_single_scene_cloud_fallback_requires_visual_qa`, mientras 2017–2026 usan L2A con máscara SCL. El resumen incluye `radiometric_warning: "2016 usa L1C TOA mientras 2017-2026 usa L2A; la incertidumbre radiométrica debe acompañar la interpretación final."` | `outputs/multitemporal_validation_v2/shoreline_2017_check.png` (referencia disponible). No existe PNG de control para 2016 en el repositorio: el QA visual de esa escena sigue sin ejecutarse. | P2 — limitación científica | Emir + Sebastián | ABIERTO — declarar la limitación en la exposición mientras no exista el control visual de 2016 |
| QA-006 | Transversal / procedencia | `grep -rlF 'C:\Users' outputs data` | Cinco artefactos persistidos incrustan rutas absolutas de la máquina de origen (`C:\Users\cocan\...`): `data/infrastructure/source_receipt.json`, `outputs/fes2014_validation.json`, `outputs/infrastructure_risk/summary.json`, `outputs/multitemporal/pipeline_summary.json` y `outputs/multitemporal/storm_correlation.json`. Incumple el criterio 1 (rutas relativas al repositorio) y hace la procedencia no reproducible en otra máquina. Los hashes SHA-256 que acompañan a esas rutas sí son válidos. | Los cinco archivos citados | P2 — procedencia y portabilidad | Nicolás (procedencia) | ABIERTO — corregir escribiendo rutas relativas o `${TIDE_MODEL_DIR}`, como ya hace `ocean_tide_directory` en `outputs/fes2014_validation.json` |
| QA-007 | Transversal / cálculo de tasas | Revisar `src/coastvision/change_analysis.py:258` y `:419`, y contrastar con `outputs/multitemporal/tide_corrections.csv` | **Discrepancia metodológica:** `_normalise_years()` redondea la columna temporal a año entero —y aborta si no lo es— y `_regression_metrics()` regresa la posición contra ese entero. Las escenas reales no caen en el mismo punto del año: los recibos van del 19-01 (2017) al 30-03 (2017), de modo que la regresión descarta hasta ~3 meses de deriva por año. Detectado por Pablo al conciliar contra el motor Rust `strandline`: la discrepancia baja de 0,026 a 0,001 m/año al usar la fecha de adquisición. | `outputs/multitemporal/tide_corrections.csv` (columna `acquired_at_utc`) y `outputs/multitemporal/transect_rates.csv` | P2 — sesgo acotado, no invalida el signo de las tasas | Detectado por Pablo (cerrado de su parte); corrección asignada a Sebastián (cambio y Strandline) | ABIERTO — el efecto está acotado y documentado; corregir después de PEP2 pasando `acquired_at_utc` como variable independiente |
| QA-008 | Demo local / preflight | `python scripts/12_demo_preflight.py --json` | El script no define `argparse` ni lee `sys.argv`: `--json` se ignora en silencio, no existe `--site` y `main()` apunta a rutas fijas de Cartagena. La versión anterior de esta matriz documentaba un comando con una bandera inexistente. | `scripts/12_demo_preflight.py:57-62` | P3 — documentación | Nicolás | CERRADO — 27-08-2026: el comando correcto es `python scripts/12_demo_preflight.py`, ya corregido en §5. El alcance Cartagena-only queda declarado en el propio JSON. |

### Severidades

- **P1:** impide afirmar que el producto cumple o puede presentarse como
  evidencia científica/comercial confiable.
- **P2:** afecta una función o la calidad de la demo, pero existe un camino de
  contingencia documentado.
- **P3:** observación menor, control opcional o mejora posterior.

### Estado de los hallazgos al cierre

| Severidad | Abiertos | Cerrados | Documentados |
|---|---|---|---|
| P1 | QA-001 | — | — |
| P2 | QA-005, QA-006, QA-007 | — | — |
| P3 | — | QA-002, QA-003, QA-008 | QA-004 |

## 5. Comandos de verificación y evidencia a guardar

Ejecutar desde la raíz del repositorio, en la rama que se va a presentar.
Copiar la salida completa al registro de entrega.

```powershell
python -m pytest -q -p no:cacheprovider
python scripts/12_demo_preflight.py
git diff --check
git status --short
```

`12_demo_preflight.py` no acepta banderas y evalúa únicamente la cadena de
Cartagena (QA-008); siempre reescribe `outputs/demo_preflight.json` y termina
con código 2 si `demo_ready` es falso.

Para regenerar una playa de forma aislada, sustituir `[site_id]` por uno de
`renaca`, `santo_domingo`, `algarrobo` o `caleta_portales`:

```powershell
python scripts/06_build_sentinel_catalog.py --site [site_id]
python scripts/08_refresh_osm_infrastructure.py --site [site_id]
python scripts/07_process_multitemporal.py --site [site_id] --tide-model-dir "$env:TIDE_MODEL_DIR"
python scripts/10_assess_infrastructure.py --site [site_id]
```

No ejecutar estos comandos sobre una playa demo y luego documentarla como real.
La salida debe incluir catálogo, recibos, fechas, parámetros, QA y una
clasificación explícita `REAL`, `DEMO` o `PARCIAL`. Una corrida real deja
`scene_attempts` y `scene_receipts` no vacíos en el
`pipeline_summary.json` del sitio; mientras esos arreglos sigan en 0, la playa
es demo por definición.

| Evidencia de cierre | Ruta o enlace | Fecha | Responsable | Resultado |
|---|---|---|---|---|
| Log de `pytest` | `outputs/coastvision_mvp/pytest.xml` (`sha256 a51dd7f8…`) | 26-08-2026 15:22:53-04:00 | Nicolás | **58/58** — `tests=58 failures=0 errors=0 skipped=0`, 4,880 s |
| JSON de preflight | `outputs/demo_preflight.json` (`sha256 2b83cae6…`) | 26-08-2026 19:22:49 UTC | Nicolás | `demo_ready: true`, 9/10 controles, único fallo el opcional `streamlit_port_8501` |
| Estado de requisitos | `outputs/requirement_status.json` | 26-08-2026 19:22:47 UTC | Nicolás | `MVP_UNIFICADO_CON_PENDIENTES_DE_DATOS`, `strict_completion: false` |
| Evidencia por playa (sustituye a la captura versionada) | `outputs/renaca/`, `outputs/santo_domingo/`, `outputs/algarrobo/`, `outputs/caleta_portales/` — 8 artefactos cada una | 27-08-2026 | Nicolás | Presentes y aislados; `shorelines` y `transect_rates` con hash propio por playa; `tide_corrections` y `storm_correlation` compartidos (QA-001) |
| Capturas del visor | No versionadas: se toman en vivo al exponer, con `python scripts/run_mvp.py` y el selector en cada playa | Día de la presentación | Quien exponga | Pendiente por naturaleza (no es un artefacto del repositorio) |
| Prueba de descargas | Botones `Descargar perfil CSV` y exportes GeoJSON en `app.py:1157` y siguientes | 26-08-2026 | Emir / Sebastián | CSV y GeoJSON abiertos y atribuidos al sitio correcto |
| Hashes/manifiesto | `data/provenance_manifest.json` | 16-07-2026 17:30:57 UTC | Nicolás | 3 insumos activos con SHA-256, licencia ODbL y URL de origen; `raw_snapshots` con sus hashes |
| Procedencia del MVP | `outputs/coastvision_mvp/resumen.json` | 26-08-2026 19:22:47 UTC | Nicolás | `source_bundle_id c3b26928…` y hashes por insumo |

## 6. Aprobación de integración

Ninguna firma de esta tabla se dio por puesta. La columna de verificación
técnica registra lo que se comprobó contra el repositorio el 27-08-2026; la
columna de firma solo se marca cuando la persona confirma.

| Área | Responsable | Evidencia entregada | Verificación técnica (27-08-2026) | Firma/confirmación |
|---|---|---|---|---|
| Configuración y selector | Pablo | `data/config/sites.json`, cinco playas en el selector, perfiles DEM por sitio | Verificado: 5 sitios válidos + 1 fixture inválido rechazado; los 5 declaran AOI, `EPSG:32719`, fuente y directorio relativo; 33 y 114 muestras DEM respectivamente | **Confirmado — 27-08-2026** |
| Sentinel, catálogos y QA | Emir | `data/sentinel/catalog_2016_2026.json`, 28 recibos de escena | Verificado en Cartagena (31 intentos / 28 recibos). No verificable en las otras 4 playas: 0 intentos y 0 recibos (QA-001); QA visual de 2016 sin ejecutar (QA-005) | Pendiente de firma del responsable |
| FES2014, cambio y Strandline | Sebastián | `outputs/fes2014_validation.json`, `transect_rates.csv`, conciliación con `strandline` | Verificado: 34/34 constituyentes, predicción numérica validada, 39 transectos y 38 LRR. Pendiente: regresión por fecha de adquisición (QA-007) | Pendiente de firma del responsable |
| Marejadas, infraestructura y despliegue | Daniel | `data/events/`, capas OSM de riesgo, URL portable | Verificado: catálogo `partial_verified_official_notices` sin 2022, 2023 ni 2025; screening OSM presente en las 5 playas. Pendiente: puerto 8501 en el equipo de exposición (QA-004) | Pendiente de firma del responsable |
| Procedencia, pruebas e informe | Nicolás | `pytest.xml`, `demo_preflight.json`, `provenance_manifest.json`, esta matriz | Verificado: 58/58, preflight 9/10, manifiesto con hashes. Pendiente: rutas absolutas en 5 artefactos (QA-006) y endurecer el gate (QA-001) | Pendiente de firma del responsable |

## 7. Cómo se reverificó este documento

La reverificación del 27-08-2026 se hizo en WSL (Ubuntu) sobre el árbol limpio
en `main` @ `ead672e`, leyendo artefactos persistidos:

```bash
git -C CoastVision log -1 --format='%H %ad %s' --date=short
md5sum CoastVision/outputs/*/multitemporal/tide_corrections.csv
md5sum CoastVision/outputs/*/multitemporal/storm_correlation.json
grep -rlF 'C:\Users' CoastVision/outputs CoastVision/data
head -c 400 CoastVision/outputs/coastvision_mvp/pytest.xml
grep -h '^def test_\|^    def test_' CoastVision/tests/*.py | wc -l
```

**Limitación declarada de esta reverificación:** el entorno WSL usado no tiene
instalados `pytest`, `streamlit`, `geopandas` ni el resto de las dependencias,
por lo que **no se reejecutaron ni la suite ni el preflight** en esta fecha. Los
resultados 58/58 y 9/10 provienen de la corrida persistida del 26-08-2026
(`outputs/coastvision_mvp/pytest.xml` y `outputs/demo_preflight.json`), y se
consideran vigentes porque el árbol de trabajo no ha cambiado desde ese commit y
el conteo estático de funciones `test_*` sigue dando 58. Antes de exponer,
reejecutar los cuatro comandos de §5 en el equipo de la presentación.

**Sobre la rama de cierre:** la pauta sugiere `pep2/qa-comercial-sebastian`, pero
el repositorio solo tiene `main` y `origin/main`; esa rama no existe local ni
remotamente. El cierre queda referido al commit `ead672e` en `main`. Si el grupo
crea la rama sugerida, actualizar el encabezado con su commit.

**Conclusión:** el producto se puede presentar como demo multisitio. Cartagena
tiene una cadena científica persistida con limitaciones explícitas (marejadas
parciales, fallback L1C 2016, FES externo, rutas absolutas y regresión por año
entero); las otras cuatro playas deben seguir rotuladas como integración
demostrativa hasta reemplazar los artefactos sintéticos —hoy demostrablemente
compartidos entre sitios— y superar esta matriz. El único hallazgo P1 abierto es
QA-001, y su mitigación para la exposición ya está acordada: no abrir el modo
científico en las playas demo.
