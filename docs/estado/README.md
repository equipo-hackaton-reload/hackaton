# Estado por zona

Un fichero por zona (`A.md` … `E.md`). Antes de empezar una tarea, el agente lee el de su zona; en su
PR lo actualiza. Formato fijo: **En develop**, **Falta**, **Siguiente tarea**, **No tocar**.

Última revisión general: 2026-10-21, punta de `develop` = `68ff789` (PRs #1–#9 fusionadas,
288 tests en verde).

## Entregables del reto (release 0.3.0)

Según `data/kit/03_Documentacion/01_Reto_requisitos_y_evaluacion.md` (§6) y
`07_Plan_de_proyecto_BMC_y_tres_niveles.md` (§9). Revisado sobre el repo el 2026-10-21, punta de
`develop` = `59745d5` (PRs #1–#13).

| # | Entregable | Estado | Dónde |
|---|---|---|---|
| 1 | Prototipo funcional | Parcial | `src/posiq/` (API, grafo, dominio), `apps/web/`, `scripts/demo_kit.py`. Funciona de principio a fin en modo kit sin claves. Falta: instrucciones de instalación y ejecución en `README.md` (hoy solo en `CLAUDE.md` y `docs/plan-b.md`); motores reales sin probar (faltan `OPENAI_API_KEY`, `GEMINI_API_KEY`, `PERPLEXITY_API_KEY` y `ANTHROPIC_API_KEY`, ver `docs/adr/0006-motores-reales.md`). |
| 2 | Documento de arquitectura (1–2 págs.) | Parcial | ADRs en `docs/adr/0001`–`0007`. El documento de 1–2 páginas con diagrama, costes y limitaciones no está en el repo (hay un borrador fuera: `../arquitectura_copiloto_geo.md`). |
| 3 | Propuesta para Alborada | Hecho (modo kit) | `docs/ejemplos/propuesta_alborada_ejemplo.docx`; cifras fijadas en `tests/golden/test_demo_canonico.py`. Redacción con LLM real PENDIENTE (falta `DEEPSEEK_API_KEY`). PDF requiere LibreOffice. |
| 4 | Deck + demo | Parcial | Demo: `docs/plan-b.md` (guion de contingencia y cifras), capturas en `apps/web/docs/screenshots/`. Deck: PENDIENTE, no está en el repo. |
| 5 | Plantilla UFV | PENDIENTE | No está en el repo. La única plantilla es la de la propuesta Word (`src/posiq/adapters/export/templates/propuesta.docx`, generada por `scripts/build_docx_template.py`). |
| 6 | Calibración / evaluación | Parcial | Evaluación: `docs/evaluacion/2026-10-21.md` (cobertura de evidencia 100 %, simulación). Calibración del juez PENDIENTE (faltan `TYPESAFE_API_KEY` y `DEEPSEEK_API_KEY`; guía en `docs/calibracion/README.md`). PlanGuard PENDIENTE (falta `DEEPSEEK_API_KEY`). |
| 7 | CHANGELOG / VERSION | Hecho | `CHANGELOG.md` (`[0.3.0] - 2026-10-21`), `VERSION` = `0.3.0`. Falta el fast-forward a `main` y el tag `v0.3.0` (a mano, ver CONTRIBUTING → Versionado). |
