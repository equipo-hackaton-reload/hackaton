# Zona A · dominio (`src/posiq/domain/`, `tests/domain/`, `tests/golden/`)

## En develop
- Dominio puro completo: esquemas, `kit_loader`, detección, `judge_questions`, score de citación,
  métricas, hallazgos, evidencias, `plan_questions`, `quality_schemas`, `simulation.simulate_plan`.
- Tests de dominio y golden de Alborada; `scripts/evaluate_system.py` (informe en `docs/evaluacion/`).
- `simulacion` y `calidad_plan` ya llegan a `GET /studies/{id}` (#11, zona C).

## Falta
- Que la web (D) y el Word (E) muestren la simulación. La calidad del plan solo existe con claves de juez.

## Ensayo de la demo (2026-10-21, `develop` en `59745d5`)

En `feature/A-ensayo-web`: la web contra la API en fixture, con Playwright headless y el brief de
Alborada en modo kit. Guion y tiempos en [`docs/demo/guion.md`](../demo/guion.md). Las 5 pantallas
funcionan de punta a punta en **15 s de máquina** y el Word se descarga (45 KB). En pantalla:
**25,87**, 8.ª de 10, a 39,97 del líder (Valdecruz, 65,84), y un plan de 22.000 € en 4 fases.

Fallos y rarezas por zona:

- **D (web):**
  - **No pinta `simulacion`**, aunque la API la devuelve: 25,87 → 30,71 (27,72–33,88). Tampoco pinta
    `calidad_plan`. Ni el plan ni la propuesta muestran la proyección.
  - KPI «Visibilidad espontánea en Barcelona» se muestra como «0,0 → 0,2»: redondea a un decimal una
    fracción (0,04). Debería salir «4 % → 20 %».
  - «Descargar PDF» está siempre visible: sin LibreOffice la API da 503 y sale un error.
  - El botón «Subir .md o .txt» está anidado dentro de su `<label>` (un botón dentro de otro control
    interactivo). Clicar el `<button>` lo intercepta el label; con ratón funciona.
  - Una vez, con `playwright-cli`, «Leyendo el brief» y «Midiendo» se quedaron sin avanzar hasta
    recargar. En 3 pasadas con Playwright programático no se reprodujo; si pasa en la demo, F5.
- **C (API/grafo):**
  - `calidad_plan` vale `null` en fixture (sin claves de juez; es lo diseñado). No hay alternativa
    determinista que se vea en la demo.
  - Los estudios del ensayo se quedan en `posiq.db` y salen en «Mediciones de esta marca». Hay que
    borrar `posiq.db` antes de la demo.
- **B (LLM fixture):** el resumen ejecutivo empieza con «DEMO SIN IA: textos y plan de ejemplo».
  Las trazas marcan 0 tokens y 0 ms.
- **E (export):** el Word no incluye la simulación ni la proyección. Mezcla 25,9 (diagnóstico) con
  25,87 (tabla de objetivos) y escribe el KPI de Barcelona como fracción (0,04 → 0,20).
- **A (dominio, propio):** los textos de `findings.py` usan formato inglés: `:.1f`/`:.2f` dan
  «25.9 frente a 65.8» y «1.00», y la fase sale como «decision», sin tilde.

## Siguiente tarea
- Hecho en `feature/A-score-canonico`: cifra canónica **25,93** (etiquetas del kit; 25,9 en la deck),
  8.ª de 10, proyección 25,9 → 30,8, fijadas en `tests/golden/test_demo_canonico.py`. Hecho en
  `feature/A-demo-canonica`: la API en fixture/kit también da 25,93 → 30,8 (el `FixtureJudge` usa
  las etiquetas del kit donde existen), fijado en `tests/e2e/test_demo_canonica_api.py`.
- Formato español en los textos de `findings.py`: coma decimal y nombres de fase con tilde (lo detectó el ensayo).
- Medir la cifra con Jev real cuando haya `TYPESAFE_API_KEY` y compararla con la canónica.
- Cierre de hito: CHANGELOG y `VERSION` por PR; luego `git push origin develop:main` (fast-forward, a mano) y tag.

## No tocar
- `schemas.py` y `ports.py` sin PR `contract-change`.
- Nada de I/O en `domain/`.
