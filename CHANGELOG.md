# Changelog

Formato [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versionado [SemVer](https://semver.org/lang/es/).

## [Unreleased]

### Added
- Simulación del plan, calidad por acción y re-medición mock en la interfaz web (zona D); preparada para los campos opcionales de la API de C.
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
- `Finding.unidad` y `Proposal.marcas` (contract-change aditivo, zona E); `pyyaml` como dependencia directa.
- `GET /studies/{id}` devuelve `revision_pendiente: null` en lugar de `"none"` cuando no hay revisión pendiente (zona C; el estado interno del grafo no cambia).
### Fixed
- Codificación del mensaje 409 de `/export` («la propuesta aún no está completada»).

## [0.1.0] - 2026-10-20

### Added
- Estructura del repositorio, convenciones y tooling.
