# Zona B · adaptadores (`adapters/engines`, `adapters/judge`, `adapters/llm`)

## En develop
- Motor del kit y motores reales ChatGPT, Gemini, Perplexity y Claude con búsqueda web, caché,
  reintentos y presupuesto (`scripts/smoke_engines.py`). **Sin probar en real.**
- Juez Jev con fallback LLM, calibración (`scripts/calibrate_judge.py`) y `PlanGuard`.
- Política del juez (ADR 0014): discrepancia reglas-juez → fallback y SIEMPRE revisión humana;
  `JEV_MODEL=jev-1.13` fijado (sin temperatura ni semilla en la API); la `Trace` guarda el modelo
  que respondió. Falta comprobar con clave que la API acepta `jev-1.13` (`client.models.list()`).
- LLM `openai_compat` (DeepSeek) y `FixtureLLM` para la demo sin claves.
- `FixtureLLM` (cambio de E, `intake.v2`): para Alborada añade posicionamiento y atributos
  deseados solo si aparecen tal cual en el brief recibido (`identidad_deseada_alborada`).
- `LLMOutputError.trace` (ADR 0018, cambio de C): tokens y coste de todos los intentos fallidos;
  si la API falla tras un intento cobrado, también sale como `LLMOutputError` con su traza.
  `MissingCredentialError` dice «falta X (ni en el entorno ni en .env)».
- Auditoría web (ADR 0019): `adapters/web/HttpxWebFetcher` (SSRF: destino `url_permitida`, IP
  `ip_permitida` en cada salto y conexión a la IP validada; 5 redirecciones; 2 MB tras
  descomprimir; 10 s totales; nunca lanza) y `FixtureWebFetcher` (CASO SINTÉTICO de
  `alboradavision.example`, respuestas en `adapters/web/fixtures/<dominio>/`). `crear_web_fetcher`
  aplica `off`/`fixture`/`real` (en modo kit, `real` → fixture). **Sin probar contra una web
  real**: solo con DNS y red falsos. `FixtureLLM` añade `A0-3` (`tecnico`) solo con hallazgos
  `F-web-*` técnicos.

## Falta
- Claves en `.env` local (`TYPESAFE_API_KEY`, `DEEPSEEK_API_KEY`, claves de motores). Nunca en el repo.
- Humo real de motores con pocos prompts y calibración real del juez (`docs/calibracion/`).
- `PlanGuard` sin `DEEPSEEK_API_KEY` no evalúa la calidad del plan.

- Auditoría web real: humo contra un dominio real propio (no `.example`) cuando C cablee el nodo
  `web_audit` y `Settings.web_audit`. No necesita claves.

## Siguiente tarea
- `feature/B-calibracion-real`: con claves, ejecutar `smoke_engines.py` y `calibrate_judge.py` y
  dejar el informe en `docs/calibracion/` (avisar a E, dueña de `docs/`).

## No tocar
- `domain/judge_questions.py` (zona A): las preguntas del juez se comparten, no se duplican.
- `ports.py` sin `contract-change`.
