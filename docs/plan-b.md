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

## Cifras de la demo (Alborada, kit)

Fijadas en `tests/golden/test_demo_canonico.py`.

- **Score de Citación: 25,93** (canónica, etiquetas del kit). En la deck: **25,9**.
- **Posición: 8.ª de 10** marcas.
- **Proyección del plan: 25,9 → 30,8** esperado tras la fase 3 (rango 27,8–34,0).

La API en modo fixture (kit) muestra estas mismas cifras: su juez devuelve las etiquetas humanas del
kit donde existen (`tests/e2e/test_demo_canonica_api.py`). Solo el juez por reglas puro daría 25,87
(no clasifica el tipo de fuente ni gradúa la fuerza); con un decimal ambas son 25,9.
