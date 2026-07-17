# CoastVision

Proyecto académico incremental de geoinformática costera para Playa Grande de Cartagena.

## Estado v07: Asistente local con evidencia

Se añade recuperación TF-IDF sobre una base local y una síntesis LLM opcional, manteniendo un fallback sin API.

Este snapshot es acumulativo y contiene los hitos anteriores necesarios para reproducir el avance del proyecto.

## Verificación de este hito

`powershell
python -c "import sys; sys.path.insert(0, 'src'); from coastvision.rag import retrieve; print(retrieve('marea y elevación', 1))"
`

Resultado esperado: respuesta recuperada sin OPENAI_API_KEY.
