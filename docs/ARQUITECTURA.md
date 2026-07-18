# Arquitectura del MVP demostrativo

```text
OSM + Copernicus GLO-90 -> adquisición y procedencia -> geometry.py
geometry.py -> capas GeoJSON/CSV -> app.py (Streamlit + Folium)
knowledge_base.json -> rag.py -> asistente local TF-IDF
tests/test_mvp.py -> geometría, procedencia y escenarios
```

WGS84 se usa en APIs y GeoJSON, Web Mercator en el lienzo y UTM 19S en distancias. La rama científica multitemporal se integra recién en v10.