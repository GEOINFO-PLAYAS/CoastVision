# Matriz de cumplimiento - Evaluación 2 TAVI

Esta matriz se concentra en el **proyecto y la demostración**. No sustituye el informe ni asigna una nota; vincula cada criterio con evidencia ejecutable.

## Avance del proyecto

| Criterio | Peso | Evidencia actual | Cobertura | Acción restante |
|---|---:|---|---|---|
| Evidencias de avance | 35 | Visor, 10 ZIP, Sentinel/NDWI/FES 2016–2026, tasas, marejadas y screening OSM | Fuerte y verificable | QA visual reforzado de 2016 y catálogo oficial de eventos |
| Diseño arquitectural | 20 | Pipeline por módulos, contratos por artefacto, CRS explícitos y modo demo aislado | Fuerte | Mantener trazabilidad y separación científico/demo |
| Uso de tecnologías | 15 | Python, GeoPandas, Rasterio, Shapely, PyProj, Streamlit, Folium, STAC, pyTMD/FES2014, TF-IDF y LLM opcional | Fuerte | Mantener RAG desacoplado de los cálculos |
| Demo funcional | 30 | Mapa completo, estaciones, elevación, escenarios, capas reales, cumplimiento, RAG, exportaciones y preflight | Fuerte | Ensayar 5 min y conservar captura offline |

## Evidencia de mayor valor incorporada

- **Sentinel/NDWI:** 28 escenas aceptadas y once líneas anuales 2016–2026.
- **FES2014:** predicción numérica validada; 28 correcciones por fecha y once líneas anuales a MSL.
- **DSAS equivalente:** 39 transectos, 336 intersecciones y 38 LRR válidas sobre 2016–2026.
- **Marejadas:** correlación punto-biserial ejecutada con n=11, r=-0,405 y p=0,216; no concluyente por catálogo parcial.
- **Infraestructura:** 38 edificios y 252 tramos OSM; screening exportado y conectado al semáforo del visor.
- **Mapa:** siete elementos cartográficos y capas separadas para inventario sin clasificar versus riesgo evaluado.
- **IA:** RAG local TF-IDF con LLM opcional y evidencia recuperable; la IA no modifica geometrías ni clases.

## Secuencia recomendada para la demo

1. Ejecutar `python scripts/12_demo_preflight.py` y mostrar `demo_ready: true`.
2. Abrir el mapa y explicar cobertura, E01-E11, progresiva, latitud y cotas.
3. Mostrar los siete elementos cartográficos y el control de capas.
4. Activar/desactivar el semáforo OSM conectado y consultar un elemento mediante clic.
5. Abrir Cumplimiento obligatorio y mostrar los once años, 28 correcciones FES y 38 LRR.
6. Mostrar que marejadas fue calculada, pero queda parcial por catálogo oficial incompleto.
7. Consultar el RAG local y cerrar con la trazabilidad del backlog.

## Riesgos de evaluación controlados

- **Sobreafirmar cumplimiento:** controlado por estados derivados y `strict_completion: false`.
- **Confundir escenario con observación:** controlado por etiquetas y ramas separadas.
- **Demo dependiente de internet:** controlado por bundles locales y preflight.
- **No evidenciar metodología:** controlado por backlog/SRS, arquitectura, pruebas y salidas persistidas.
- **Mostrar infraestructura ficticia:** controlado por capas separadas y recibo OSM real.
