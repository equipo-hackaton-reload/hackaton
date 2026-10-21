# Zona D · web (`apps/web/`)

## En develop
- React + Vite: nuevo estudio, competidores, diagnóstico, plan y propuesta; sondeo del estado,
  revisiones editables, evidencias por hallazgo y trazas. Mocks MSW con cifras del dominio. Job `web` en CI.
- Consume `/studies`, `/studies/{id}`, `/resume`, `/traces`, `/evaluations` y `GET /estimate`.
- La tarjeta de simulación y calidad del plan ya están conectadas a los campos opcionales de C;
  el mock incluye rangos por fase y calidad por acción.
- El diagnóstico ya ofrece re-medición mock y vista del delta; queda probarlo cuando C publique
  `POST /studies/{id}/remeasure`.

## Falta
- Probar la integración con la API de C usando `LLM_PROVIDER=fixture`.
- Pulir la interfaz, ejecutar build de producción y capturar la demo.

## Siguiente tarea
- `feature/D-simulacion`: mock implementado; pendiente validación contra la API real y capturas.

## No tocar
- No calcular cifras en el front: se pintan las que da la API.
