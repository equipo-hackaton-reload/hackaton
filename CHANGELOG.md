# Changelog

Formato [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versionado [SemVer](https://semver.org/lang/es/).

## [Unreleased]

## [0.3.0] - 2026-10-21

### Added
- Simulación del plan, calidad por acción y re-medición mock en la interfaz web (zona D); preparada para los campos opcionales de la API de C.
- README de arranque reproducible (zona C): requisitos, demo sin claves con la API y la web o con `scripts/demo_kit.py`, variables con claves, estimación de coste, tabla de la API, desarrollo y limitaciones.
- `JUDGE_PROVIDER=reglas` (zona C; campo aditivo en `settings.py` y `.env.example`): el juez de menciones y PlanGuard no llaman a ningún LLM aunque haya claves, para un estudio rápido con DeepSeek solo en intake, plan y redacción. `/estimate` lo refleja. La propuesta declara en sus limitaciones cuándo las menciones se evaluaron solo por reglas.
- Re-medición (zona C): `POST /studies/{id}/remeasure` crea un estudio nuevo con el brief y el mercado confirmado de un estudio completado (409 si no lo está), arranca en `prompts` y compara con la medición anterior; `GET /studies/{id}` expone `metrics_delta`.
- Demo canónica en pantalla (zona A, toca B/C): en fixture/kit el `FixtureJudge` devuelve las etiquetas humanas del kit donde existen (reglas en el resto), así la API muestra 25,93 → 30,8 como la deck; e2e en `tests/e2e/test_demo_canonica_api.py`.
- Ensayo de la demo en la web contra la API en fixture (zona A): `docs/demo/guion.md`, con un guion clic a clic de 3 min, tiempos medidos (15 s de máquina), cifras en pantalla, checklist previa y saltos al plan B; fallos por zona en `docs/estado/A.md`.
- Simulación del impacto y calidad del plan en el grafo (zona C): el nodo `plan` añade `simulacion` (`simulate_plan`) y `calidad_plan` (PlanGuard, solo con claves de juez; sin ellas queda en null y no bloquea), se recalculan si la persona edita el plan y se exponen en `GET /studies/{id}`. El checkpointer admite los modelos de `simulation_schemas` y `quality_schemas`.
- Cifras canónicas de la demo (zona A): score de Alborada 25,93 con etiquetas del kit (25,87 con el juez por reglas de la API en fixture), 8.ª de 10 y proyección 25,9 → 30,8, en `tests/golden/test_demo_canonico.py`; `posiq.db*` en `.gitignore`.
- Cierre e integración (zona A): `.claude/settings.json` con permisos de PR, push y uv; reglas de pre-commit, CHANGELOG por PR y protección de ramas en plan gratuito en CONTRIBUTING; `docs/estado/A–E.md` y `docs/plan-b.md`.
- Endpoints que consume la web (zona C): `GET /studies/{id}/evaluations?ids=` (evidencias con motor, prompt, respuesta truncada a 2.000 caracteres y fuentes), `GET /studies/{id}/traces` y `GET /estimate` (coste previo de motores y juez con los precios de `settings`; 0 en modo kit sin claves).
- Demo HTTP sin claves con `LLM_PROVIDER=fixture`, `FixtureLLM`, juez por detección, `ProposalDraft`, exportación real Word/PDF y `scripts/demo_kit.py`; subida multipart incluida (zona C, ADR 0005).
- Dominio puro (zona A): esquemas, cargador del kit, detección, preguntas del juez, score de citación, métricas, hallazgos, tests golden y ADR 0001.
- `Study` y `study_id` obligatorio en todos los resultados; `diff_metrics` para re-medición (ADR 0002).
- Adaptadores (zona B): firmas reales en `ports.py`, cliente LLM compatible con OpenAI, motor del kit, juez Jev con fallback LLM, caché en disco, presupuesto y calibración del juez (ADR 0003).
- Motores reales (zona B): ChatGPT, Gemini, Perplexity y Claude con búsqueda web, fuentes resueltas contra el catálogo, reintentos, caché, presupuesto, `build_engines` y `scripts/smoke_engines.py` (ADR 0006). Sin probar en real.
- Nivel 3 (zona A): simulación conservadora del impacto del plan sobre el Score de Citación, preguntas de calidad del plan y `PlanGuard`, cobertura de evidencia y `scripts/evaluate_system.py` (ADR 0007).
- PENDIENTE: calibración real con Jev y fallback (falta `TYPESAFE_API_KEY` y `DEEPSEEK_API_KEY`; ver `docs/calibracion/README.md`).
- Exportación de la propuesta (zona E): puerto `Exporter`, `AgencyBrandKit`, `DocxExporter` con plantilla reproducible, `PdfExporter` con LibreOffice, golden y ejemplo en `docs/ejemplos/` (ADR 0004).
- Prompts versionados v1 (`intake`, `market`, `prompts`, `plan`, `write`), `PromptSet` y `load_prompt`.
- Interfaz web (zona D): cinco pantallas del estudio con sondeo, revisiones editables, evidencias por hallazgo y trazas; mocks MSW con cifras del dominio sobre el kit; job `web` en CI.
- Orquestación (zona C): puerto `StudyRepo` y `SqlStudyRepo` (SQLModel), grafo LangGraph con revisiones humanas por `interrupt()` y checkpointer SQLite, API FastAPI (`/studies`, `/resume`, `/export`, `/health`) y e2e del modo kit sin APIs (ADR 0005).

### Changed
- Release 0.3.0 (zona A): `VERSION` 0.3.0 y tabla de los entregables del reto en `docs/estado/README.md`.
- Release por fast-forward `develop → main` (repo solo squash): CONTRIBUTING y `.claude/settings.json` con `git push origin develop:main` siempre con confirmación manual (zona A).
- `Finding.unidad` y `Proposal.marcas` (contract-change aditivo, zona E); `pyyaml` como dependencia directa.
- `GET /studies/{id}` devuelve `revision_pendiente: null` en lugar de `"none"` cuando no hay revisión pendiente (zona C; el estado interno del grafo no cambia).

### Fixed
- `CHANGELOG.md` sin los marcadores de conflicto que entraron con la #20; el CI (`check`) falla si hay marcadores `<<<<<<<`/`=======`/`>>>>>>>` en el repo (zona A).
- Un fallo de la API de PlanGuard ya no tumba el nodo `plan`: se anota y `calidad_plan` queda en null; solo `BudgetExceeded` para el estudio (zona C).
- Codificación del mensaje 409 de `/export` («la propuesta aún no está completada»).

## [0.1.0] - 2026-10-20

### Added
- Estructura del repositorio, convenciones y tooling.
