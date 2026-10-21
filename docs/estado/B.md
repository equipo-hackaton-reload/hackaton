# Zona B · adaptadores (`adapters/engines`, `adapters/judge`, `adapters/llm`)

## En develop
- Motor del kit y motores reales ChatGPT, Gemini, Perplexity y Claude con búsqueda web, caché,
  reintentos y presupuesto (`scripts/smoke_engines.py`). **Sin probar en real.**
- Juez Jev con fallback LLM, calibración (`scripts/calibrate_judge.py`) y `PlanGuard`.
- Política del juez (ADR 0014): discrepancia reglas-juez → fallback y SIEMPRE revisión humana;
  `JEV_MODEL=jev-1.13` fijado (sin temperatura ni semilla en la API); la `Trace` guarda el modelo
  que respondió. Falta comprobar con clave que la API acepta `jev-1.13` (`client.models.list()`).
- LLM `openai_compat` (DeepSeek) y `FixtureLLM` para la demo sin claves.
- `LLMOutputError.trace` (ADR 0018, cambio de C): tokens y coste de todos los intentos fallidos;
  si la API falla tras un intento cobrado, también sale como `LLMOutputError` con su traza.
  `MissingCredentialError` dice «falta X (ni en el entorno ni en .env)».

## Falta
- Claves en `.env` local (`TYPESAFE_API_KEY`, `DEEPSEEK_API_KEY`, claves de motores). Nunca en el repo.
- Humo real de motores con pocos prompts y calibración real del juez (`docs/calibracion/`).
- `PlanGuard` sin `DEEPSEEK_API_KEY` no evalúa la calidad del plan.

## Siguiente tarea
- `feature/B-calibracion-real`: con claves, ejecutar `smoke_engines.py` y `calibrate_judge.py` y
  dejar el informe en `docs/calibracion/` (avisar a E, dueña de `docs/`).

## No tocar
- `domain/judge_questions.py` (zona A): las preguntas del juez se comparten, no se duplican.
- `ports.py` sin `contract-change`.
