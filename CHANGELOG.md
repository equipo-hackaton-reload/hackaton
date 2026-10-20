# Changelog

Formato [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/); versionado [SemVer](https://semver.org/lang/es/).

## [Unreleased]

### Added
- Dominio puro (zona A): esquemas, cargador del kit, detección, preguntas del juez, score de citación, métricas, hallazgos, tests golden y ADR 0001.
- `Study` y `study_id` obligatorio en todos los resultados; `diff_metrics` para re-medición (ADR 0002).
- Adaptadores (zona B): firmas reales en `ports.py`, cliente LLM compatible con OpenAI, motor del kit, juez Jev con fallback LLM, caché en disco, presupuesto y calibración del juez (ADR 0003).
- Motores reales (zona B): ChatGPT, Gemini, Perplexity y Claude con búsqueda web, fuentes resueltas contra el catálogo, reintentos, caché, presupuesto, `build_engines` y `scripts/smoke_engines.py` (ADR 0006). Sin probar en real.
- Nivel 3 (zona A): simulación conservadora del impacto del plan sobre el Score de Citación, preguntas de calidad del plan y `PlanGuard`, cobertura de evidencia y `scripts/evaluate_system.py` (ADR 0007).
- PENDIENTE: calibración real con Jev y fallback (falta `TYPESAFE_API_KEY` y `DEEPSEEK_API_KEY`; ver `docs/calibracion/README.md`).
- Exportación de la propuesta (zona E): puerto `Exporter`, `AgencyBrandKit`, `DocxExporter` con plantilla reproducible, `PdfExporter` con LibreOffice, golden y ejemplo en `docs/ejemplos/` (ADR 0004).
- Prompts versionados v1 (`intake`, `market`, `prompts`, `plan`, `write`), `PromptSet` y `load_prompt`.
### Changed
- `Finding.unidad` y `Proposal.marcas` (contract-change aditivo, zona E); `pyyaml` como dependencia directa.
### Fixed

## [0.1.0] - 2026-10-20

### Added
- Estructura del repositorio, convenciones y tooling.
