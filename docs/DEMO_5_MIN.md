# Guion de demo — máximo 5 minutos

## Preparación

- Ejecutar `python scripts/12_demo_preflight.py`, iniciar con `python scripts/run_mvp.py` y dejar el modo **Científico FES2014 + LRR** precargado.
- No ejecutar descargas ni FES2014 durante la presentación: la app consume artefactos persistidos.
- Si fallan los tiles, continuar con las tablas y archivos locales.

## Guion cronometrado

1. **Problema y alcance — 25 s.** CoastVision evalúa el cambio de costa y la exposición de infraestructura en Playa Grande. Es un screening académico, no una zonificación oficial.
2. **Cartografía obligatoria — 35 s.** Señalar título, leyenda, escala, norte, fuente/autor, CRS/proyección y fecha.
3. **Serie multitemporal — 45 s.** Mover “Línea costera destacada” desde 2016 hasta 2026. Explicar que son once resultados Sentinel-2/NDWI corregidos a MSL con FES2014, no una interpolación.
4. **Tasas de cambio — 40 s.** Activar transectos LRR. Rojo indica LRR positiva (retroceso); azul, negativa (acreción). Mostrar que existen 39 transectos, 336 intersecciones y 38 LRR válidas.
5. **Semáforo conectado — 60 s.** Mostrar edificios y caminos coloreados. Hacer clic cerca de uno y explicar que el panel recupera la clase persistida, su distancia a la costa 2026, LRR local, transecto y años hasta impacto.
6. **Latitud y altura — 35 s.** Mostrar las coordenadas del clic y activar muestras DEM. Aclarar: elevación del terreno, marea y cambio costero son variables distintas.
7. **Resultados obligatorios — 60 s.** Volver a las cinco métricas superiores: líneas Sentinel/NDWI, escenas corregidas, LRR, años correlacionados e infraestructura. Explicar que marejadas se ejecutó con n=11, r=-0,405 y p=0,216, pero su interpretación permanece exploratoria por catálogo oficial incompleto.
8. **Cierre — 40 s.** Explicar por qué el bajo riesgo cambia poco: 37 de 38 LRR son negativas y la única positiva es aproximadamente +0,042 m/año; la infraestructura más cercana está a 55,3 m. El resultado es trazable, pero requiere QA de 2016, cobertura OSM y validación de terreno.

Total: **5 minutos**.

## Evidencia que sí puede afirmarse

- 31 escenas Sentinel-2 catalogadas y 28 escenas aceptadas en 2016–2026.
- Once líneas anuales NDWI corregidas con FES2014; 28 predicciones de marea por fecha UTC.
- 39 transectos, 336 intersecciones y 38 LRR válidas con R², error estándar e IC95.
- Correlación exploratoria de marejadas ejecutada con n=11; no significativa al 5 % y basada en catálogo parcial.
- 38 edificios y 252 tramos OSM clasificados; resultado actual: 290 bajos, 0 precaución y 0 críticos.
- Siete elementos cartográficos implementados.
- El modo científico no usa las franjas del escenario manual.

## Afirmaciones que deben evitarse

- “Riesgo bajo significa riesgo cero”: es un screening condicionado a LRR, horizonte, costa 2026 y cobertura OSM.
- “Las marejadas explican el cambio”: p=0,216 y catálogo oficial incompleto.
- “2016 tiene la misma calidad que los demás años”: usa una escena L1C sin SCL y requiere QA reforzado.
- “La elevación DEM corrige la marea”: la corrección viene de FES2014; el DEM solo aporta contexto topográfico.
- “El semáforo clasifica toda la playa”: clasifica edificios y caminos inventariados, no polígonos continuos de terreno.
