# Plan B de la demo

Si falla X, enseñamos Y. Todo lo de la columna Y funciona sin red y sin claves.

| Si falla… | Enseñamos… | Cómo |
|---|---|---|
| APIs de motores (claves, cuota, red) | Modo kit con LLM fixture: mismo flujo completo con las respuestas sintéticas del kit | `LLM_PROVIDER=fixture uv run uvicorn posiq.interfaces.api.main:app` y `uv run python scripts/demo_kit.py` |
| DeepSeek (redacción de la propuesta) | `FixtureLLM`: propuesta con cifras reales del dominio | `LLM_PROVIDER=fixture` |
| Jev calibra mal o no responde | Informe de calibración (`docs/calibracion/`) y juez de fallback (LLM o detección determinista) | El juez cae solo al fallback por debajo de `JUDGE_CONFIDENCE_FALLBACK` |
| Calidad del plan (PlanGuard) sin clave | Cobertura de evidencia: hallazgos → `evaluation_ids`, acciones → `finding_ids` | `uv run python scripts/evaluate_system.py` |
| LibreOffice no instalado (PDF da 503) | Solo Word | `GET /studies/{id}/export?formato=docx`; ejemplo en `docs/ejemplos/` |
| La web no arranca | API + Word descargado, o la web con mocks MSW | `VITE_USE_MOCKS=true` en `apps/web/.env` y `npm run dev` |
| Todo lo anterior | Word de ejemplo e informe de evaluación ya generados | `docs/ejemplos/propuesta_alborada_ejemplo.docx`, `docs/evaluacion/` |

Cifras de referencia (Alborada, kit): 8.ª de 10 marcas; score 25,93 en `evaluate_system.py`
(25,87 por la API en modo fixture, ver `docs/estado/A.md`); proyección esperada 25,9 → 30,8.
