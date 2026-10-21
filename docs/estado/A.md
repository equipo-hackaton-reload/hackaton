# Zona A · dominio (`src/posiq/domain/`, `tests/domain/`, `tests/golden/`)

## En develop
- Dominio puro completo: esquemas, `kit_loader`, detección, `judge_questions`, score de citación,
  métricas, hallazgos, evidencias, `plan_questions`, `quality_schemas`, `simulation.simulate_plan`.
- Tests de dominio y golden de Alborada; `scripts/evaluate_system.py` (informe en `docs/evaluacion/`).
- `simulacion` y `calidad_plan` ya llegan a `GET /studies/{id}` (#11, zona C).
- Contratos del diferencial (aditivos, sin `contract-change`): `stats_schemas`, `scenario_schemas`
  (`EscenarioPlan`, no `Escenario`, para no chocar con `simulation_schemas.Escenario`),
  `source_map_schemas` y `accuracy_schemas`. Las funciones llegan en `feature/A-rigor-estadistico`,
  `A-escenarios`, `A-mapa-fuentes` y `A-exactitud-marca` (ADR 0008–0011).

- Mapa de fuentes del sector (`feature/A-mapa-fuentes`, ADR 0010): `source_map.mapa_fuentes`,
  `cuota_por_tipo`, `oportunidades_fuente`, `hallazgo_web_propia` y `punto_de_partida`. Con el kit:
  - **Top 5 fuentes del sector:** (webs propias) 11,3 %, directoriomedico 8,6 %, diariosalud 8,5 %,
    comparaclinicas 8,3 % y saludactual 7,9 %.
  - **Web propia de Alborada:** 5,9 % de sus citas (33/564), frente al 3,3 % de media de sus
    competidores.
  - **Top 3 oportunidades de Alborada:** wikipedia.org (Media), comparaclinicas (Baja) y
    rankingclinicas (Baja). Las fuentes que acompañan a Alborada son casi las de la media de sus
    competidores: su problema es que aparece menos.
  - **Para que C lo enchufe:** falta `StudyRepo.list_by_sector`.

- Trazabilidad brief → propuesta (ADR 0013):
  - PR 1 (#29, en develop): contrato aditivo `Proposal.encargo` (`Encargo`, `PuntoBrief`),
    `BriefSummary.posicionamiento_deseado/atributos_deseados` y `ProposalDraft.cobertura_brief`.
  - PR 2: `domain/brief_coverage.py` con `puntos_del_brief`, `evaluar_cobertura` y `carencias`.
    Con el kit, sin enlaces del redactor solo quedan cubiertas las 2 restricciones y el presupuesto
    (22.000 € ≤ 27.000 €): 13 de 16 puntos pendientes. Con los enlaces del golden, 16 de 16.
  - PR 3: cableado en `write` (con un reintento y limitación si falta algo), prompt `write.v2`,
    sección «Lo que nos habéis pedido» en el Word y cobertura en el fixture (16 de 16 en la demo).
  - Falta: que la web lo pinte (D, forma del JSON en `docs/estado/D.md`). `posicionamiento_deseado`
    y `atributos_deseados` existen, pero `intake.v1` aún no los extrae ni son puntos de cobertura.

## Exactitud de marca (`feature/A-exactitud-marca`, ADR 0011)

- `domain/accuracy.py` (puro):
  - `extraer_afirmaciones(runs, brand, brief, *, marcas, ciudades)`
  - `verificar(afirmaciones, brief, brand, *, marcas, ciudades)`
  - `hallazgo_exactitud(study_id, brand_id, afirmaciones, verificaciones)`
  - `acciones_mitigacion(afirmaciones, verificaciones, brand, *, fuentes)`
  - Todo junto: `evaluar_exactitud(study_id, brand, brief, runs, *, marcas, ciudades,
    afirmaciones_llm) -> (HallazgoExactitud, list[AccionMitigacion])`.
  - Recuentos: `recuento(hallazgo)` y `expresiones_a_revisar(hallazgo)`.
  - Listas documentadas: `EXPRESIONES_RIESGO`, `SERVICIOS_CONOCIDOS` y `CIUDADES_CONOCIDAS`.
- Capa LLM opcional: `application/accuracy.extraer_afirmaciones_llm(llm, runs, brand, *, study_id,
  marcas) -> (afirmaciones, trazas)` con `prompts/claims.v1.md`. En fixture es determinista.
- **Kit de Alborada (reglas, datos reales):**
  - 276 afirmaciones en 193 evaluaciones.
  - **0 inexactitudes**: no se fabrican.
  - Por estado: 62 correctas, 193 no verificables y **21 «a revisar por la clínica»** (todas por
    «la opción más recomendada / recomendable»).
  - Por tipo: servicio 195 (62 correctas, 131 no verificables, 2 a revisar), profesional 62 (no
    verificables), otro 19 (a revisar). Sede, precio y resultado clínico: 0.
- Falta:
  - Conectarlo al grafo y a la API (C). Mostrarlo en la web (D) y en el Word (E).
  - Muchas «no verificables» lo son porque el `BriefSummary` no tiene diferenciales, sedes ni
    equipo médico. Ampliarlo es un `contract-change` que no se ha hecho.
- Escenarios del plan (`feature/A-escenarios`, ADR 0009): `scenarios.build_scenario`,
  `build_preset`/`build_presets` y `minimal_cover` (en los preajustes la medición no cubre hallazgos).
  Alborada: mínimo viable 5 puntos → 27,67; equilibrado 7 puntos → 28,20; completo 16 puntos →
  30,77. `intervalo` en None hasta el IC del score (`feature/A-rigor-estadistico`). Falta que C
  rellene `escenarios` (`EscenarioGuardado`, #24) con `build_presets`, más un endpoint para el
  escenario personalizado, y que D lo pinte.
- Competidores declarados frente a los que pone la IA (`feature/A-competidores-declarados`,
  ADR 0012): `competitor_gap.brecha_competidores(brief, market, metrics)` → `BrechaCompetidores`
  (en `competitor_gap_schemas.py`), con los hallazgos `F-competidor-no-declarado` (ventaja ≥ 5
  puntos; L ≥ 10) y `F-declarado-poco-visible` (tasa espontánea < max(10 %, 50 % de la foco)).
  Con el kit:
  - **Declarados por Alborada:** Valdecruz (1.º, 66,5), Tramuntana (2.º, 47,2) y Láser Nítida
    (4.º, 37,0). Ninguno queda «poco visible».
  - **No declarados por delante:** Oftalmos Centro (3.º, +13,1 → hallazgo L), Cervantes (+1,7),
    Santa Eulalia (+1,2) y Vistalia (+0,4). Alborada es 8.ª de 10.
  - **Contrato que haría falta (no se ha tocado):** `Finding.brand_ids: list[str] = []`, para
    enlazar el hallazgo con las marcas que nombra sin parsear el texto.
  - Sin conectar al grafo: nota para C en `docs/estado/C.md`.
- **Posible fallo de nombres en `market` (zona C/E, no arreglado):** `prompts/market.v1.md` dice
  que el estado trae `brief_summary` y `marcas_candidatas`, pero `application/nodes/market.py`
  envía `{"brief": ..., "candidatos": ...}`. `OpenAICompatLLM` manda el `state` tal cual como
  JSON en el mensaje de usuario, así que el LLM sí recibe los candidatos, aunque con otra clave.
  El riesgo es que el prompt busque `marcas_candidatas`, no la encuentre y aplique la regla 6
  («si está vacía, construye el mercado solo con el brief»). Entonces las marcas de contexto
  del kit (Oftalmos Centro, Cervantes…) no entran en el mercado y no se miden, porque
  `reconcile` solo mapea las marcas que el LLM propone. Esto afectaría también a este hallazgo.
  En fixture no se nota, porque el `FixtureLLM` ignora el estado y devuelve
  `kit.brands_in_runs()`. Arreglo propuesto: renombrar las claves en `market.py` a
  `brief_summary`/`marcas_candidatas` (C), o cambiar el prompt y el README de prompts (E).

## Falta
- Que la web (D) y el Word (E) muestren la simulación. La calidad del plan solo existe con claves de juez.

## Ensayo de la demo (2026-10-21, `develop` en `59745d5`; repetido sobre `e0fa86a`)

En `feature/A-ensayo-web`: la web contra la API en fixture, con Playwright headless y el brief de
Alborada en modo kit. Guion y tiempos en [`docs/demo/guion.md`](../demo/guion.md). Las 5 pantallas
funcionan de punta a punta en **15–18 s de máquina** y el Word se descarga (45 KB). En pantalla,
con la #16: **25,93**, 8.ª de 10, a 40,53 del líder (Valdecruz, 66,46), y un plan de 22.000 € en 4
fases. La API proyecta 25,93 → 30,77 (27,77–33,95), que es 25,9 → 30,8 como en la deck. La
re-medición (#14) todavía no aparece en la web: no hay botón y `metrics_delta` no se muestra.

Fallos y rarezas por zona:

- **D (web):**
  - **No pinta `simulacion`**, aunque la API la devuelve: 25,93 → 30,77 (27,77–33,95). Tampoco pinta
    `calidad_plan`. Ni el plan ni la propuesta muestran la proyección.
  - KPI «Visibilidad espontánea en Barcelona» se muestra como «0,0 → 0,2»: redondea a un decimal una
    fracción (0,04). Debería salir «4 % → 20 %».
  - «Descargar PDF» está siempre visible: sin LibreOffice la API da 503 y sale un error.
  - El botón «Subir .md o .txt» está anidado dentro de su `<label>` (un botón dentro de otro control
    interactivo). Clicar el `<button>` lo intercepta el label; con ratón funciona.
  - Una vez, con `playwright-cli`, «Leyendo el brief» y «Midiendo» se quedaron sin avanzar hasta
    recargar. En 4 pasadas con Playwright programático no se reprodujo; si pasa en la demo, F5.
  - No hay acceso a la re-medición (`POST /studies/{id}/remeasure`, #14) ni a `metrics_delta`.
- **C (API/grafo):**
  - `calidad_plan` vale `null` en fixture (sin claves de juez; es lo diseñado). No hay alternativa
    determinista que se vea en la demo.
  - Los estudios del ensayo se quedan en `posiq.db` y salen en «Mediciones de esta marca». Hay que
    borrar `posiq.db` antes de la demo.
- **B (LLM fixture):** el resumen ejecutivo empieza con «DEMO SIN IA: textos y plan de ejemplo».
  Las trazas marcan 0 tokens y 0 ms.
- **E (export):** el Word no incluye la simulación ni la proyección. Mezcla 25,9 (diagnóstico) con
  25,93 (tabla de objetivos) y escribe el KPI de Barcelona como fracción (0,04 → 0,20).
- **A (dominio, propio):** los textos de `findings.py` usan formato inglés: `:.1f`/`:.2f` dan
  «25.9 frente a 66.5» y «1.00», y la fase sale como «decision», sin tilde.

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
