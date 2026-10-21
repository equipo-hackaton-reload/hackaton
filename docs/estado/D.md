# Zona D · web (`apps/web/`)

## En develop
- React + Vite: nuevo estudio, competidores, diagnóstico, plan y propuesta; sondeo del estado,
  revisiones editables, evidencias por hallazgo y trazas. Mocks MSW con cifras del dominio. Job `web` en CI.
- Consume `/studies`, `/studies/{id}`, `/resume`, `/traces`, `/evaluations` y `GET /estimate`.

## Falta
- Mostrar simulación del plan y calidad del plan cuando C las exponga.
- Botón de re-medición cuando exista `POST /studies/{id}/remeasure`.

## Siguiente tarea
- `feature/D-simulacion`: tarjeta de proyección (actual → esperado por fase, rango mín–máx) primero
  con mock MSW y luego contra la API real.

## No tocar
- No calcular cifras en el front: se pintan las que da la API.
