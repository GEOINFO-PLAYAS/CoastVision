# CoastVision MVP — alcance del piloto

El piloto se concentra en Playa Grande de Cartagena. Usa el arco marino OSM completo, 11 estaciones E01–E11, transectos de 310 m y 33 cotas GLO-90 a 50, 150 y 250 m tierra adentro.

El producto de esta etapa es demostrativo: permite comunicar dónde se mide, explorar un desplazamiento lineal configurable y evaluar puntos con reglas transparentes. OSM no es una observación satelital; GLO-90 no equivale a marea ni topografía de detalle; los predios son sintéticos.

Los cálculos métricos se realizan en UTM 19S (`EPSG:32719`), los GeoJSON usan WGS84 (`EPSG:4326`) y el lienzo Leaflet se representa en Web Mercator (`EPSG:3857`). La integración Sentinel-2, corrección de marea y tasas observadas queda para un hito científico posterior.