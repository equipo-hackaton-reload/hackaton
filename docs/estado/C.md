# Zona C · orquestación y API (`application/`, `interfaces/api/`)

## En develop
- Grafo LangGraph (intake, market, prompts, run, judge, analyze, plan, write) con revisiones por
  `interrupt()` y checkpointer SQLite; `SqlStudyRepo`.
- API: `POST /studies`, `GET /studies`, `GET /studies/{id}`, `POST /studies/{id}/resume` (409 fuera de
  turno), `GET /studies/{id}/evaluations?ids=`, `GET /studies/{id}/traces`, `GET /estimate?modo=`,
  `GET /studies/{id}/export?formato=docx|pdf`, `/health`. CORS para `localhost:5173`.
- `revision_pendiente` es `null` cuando no hay revisión pendiente.
- Simulación y calidad del plan: el nodo `plan` añade `simulacion` (`simulate_plan`) y
  `calidad_plan` (PlanGuard). Sin claves de juez, `calidad_plan` es `null` y no bloquea. Si la
  persona edita el plan, ambas se recalculan. Las dos salen en `GET /studies/{id}`.
- Re-medición: `POST /studies/{id}/remeasure` (201; 409 si el estudio no está completado) crea un
  estudio nuevo con el brief y el mercado confirmado del original. Empieza en `prompts`, sin repetir
  intake ni la revisión de competidores; el plan nuevo sí pasa por revisión. `GET /studies/{id}`
  devuelve `metrics_delta` (null en la primera medición). En modo kit el delta es 0: mide
  repetibilidad, no una mejora.
- `JUDGE_PROVIDER=reglas` (por defecto `auto`): el juez de menciones y PlanGuard no llaman a ningún
  LLM aunque haya claves; DeepSeek solo hace intake, plan y redacción (< 0,10 €, minutos). Si el
  nodo `judge` evaluó por reglas (por elección o sin clave), la propuesta lo declara en sus
  limitaciones; la demo en fixture explica en sus supuestos que usa etiquetas del kit y reglas.
  PlanGuard ya no bloquea el plan si su API falla.
- Demo sin claves: `LLM_PROVIDER=fixture` + `scripts/demo_kit.py`.
- El nodo `intake` usa `intake.v2` (zona E): `brief.posicionamiento_deseado` y
  `brief.atributos_deseados` llegan rellenos en `GET /studies/{id}` si el brief los trae.
- README de arranque reproducible: requisitos, demo sin claves (API + web o `demo_kit.py`), claves,
  API, desarrollo y limitaciones. Comprobado desde cero en un worktree el 2026-10-21.
- Trazabilidad brief → propuesta (zona A, ADR 0013): el nodo `write` usa `write.v2`, manda
  `puntos_brief` al redactor y rellena `proposal.encargo` con `domain.brief_coverage`. Si falta un
  punto enlazable (no restricciones ni presupuesto), reintenta una vez con `carencias_cobertura` y
  `borrador_anterior`; lo que siga pendiente va a `contexto.limitaciones` («Puntos del brief sin
  tratar…»). Forma del JSON en `docs/estado/D.md`.

- Cuentas (ADR 0015, `feature/C-cuentas`): `/auth/register|verify|verify/reenviar|login|logout|me`
  en `interfaces/api/auth.py`; reglas en `application/accounts.py` (`AccountService`, puerto
  `AccountRepo`) y `application/security.py` (scrypt, tokens, códigos); tablas `user`, `session`,
  `verification` y `study_owner` en `adapters/repo/accounts.py` sobre el motor de `SqlStudyRepo`.
  Dependencia `current_user` (`CurrentUser`) en todas las rutas salvo `/health` y el alta; estudios
  ajenos → 404 en lectura, resume, remeasure, evaluations, traces y export; la re-medición hereda
  el propietario. Estudios sin propietario: ocultos, o del correo `AUTH_DEMO_USER`. 415 sin JSON
  en `/auth/*` y `resume`, 413 por encima de `BRIEF_MAX_BYTES`, rate limit en memoria. Los tests de
  API se autentican con `tests/auth_helpers.py`; `demo_kit.py` entra como `demo@posiq.local`.
  **La web necesita login (zona D)**: sin él, contra la API real todo da 401.
- Coste (ADR 0018): el modo kit es siempre gratis aunque haya claves (`FixtureLLM`,
  `FixtureJudge` con las etiquetas del kit, sin PlanGuard); `KIT_IA_REAL=true` es el opt-in para
  usar el LLM y el juez de pago sobre el kit. Lo ya pagado en un nodo que falla (intentos de
  `LLMOutputError`, reintentos de plan/redacción, PlanGuard, juez y su fallback) viaja en la
  excepción y `StudyRunner` lo suma al checkpoint y al repo: sale en `/traces` y en
  `coste_acumulado_eur` también con estado `error`. `GET /estimate` cuenta LLM de los nodos
  (`LLM_TOKENS`), juez con fallback (25 %) y PlanGuard; `estimate_study(..., remedicion=True)`
  quita intake y market (para `GET /studies/{id}/remeasure/estimate`).

## Diferencial v0.4.0 (en curso)
- Base común: el checkpointer admite `stats_schemas`, `scenario_schemas`, `source_map_schemas`,
  `accuracy_schemas` y `application/diferencial.py`. `GET /studies/{id}` ya trae los bloques
  `rigor`, `escenarios`, `oportunidades_fuente`, `exactitud` y `mitigaciones`, en `null` hasta que
  llegue el dominio de cada uno (`feature/A-rigor-estadistico`, `A-escenarios`, `A-mapa-fuentes`,
  `A-exactitud-marca`).
- Forma del JSON para la web y el Word:
  - `rigor`: `{score_global: Intervalo|null, score_por_motor: {Motor: Intervalo},
    aparicion_por_motor: {Motor: Intervalo}, hallazgos: {finding_id: Significancia},
    deltas: {"score_global" | "tipo:dimension:valor": Significancia}}`.
  - `escenarios`: `[{id, elegido, escenario: EscenarioPlan}]`; solo uno elegido.
  - `oportunidades_fuente`: `[OportunidadFuente]`; `exactitud`: `[HallazgoExactitud]` (uno por
    marca); `mitigaciones`: `[AccionMitigacion]`.
- Pendiente, una PR por punto: (1) rigor y `JUDGE_VOTES`, (2) escenarios, (3) mapa de fuentes,
  (4) exactitud.
- **Nota de A (competidores declarados, ADR 0012), por enganchar en `application/diferencial.py`:**
  `posiq.domain.competitor_gap.brecha_competidores(brief, market, metrics) -> BrechaCompetidores`
  (`domain/competitor_gap_schemas.py`). Es puro y se llama tras `compute_metrics`. Forma:
  `{study_id, marca_foco_id, puesto_foco, score_foco, tasa_foco, n_marcas,
  declarados: [CompetidorMedido], no_resueltos: [str],
  no_declarados_por_delante: [CompetidorMedido], sorpresas: [brand_id],
  declarados_poco_mencionados: [brand_id], umbral_ventaja_puntos, umbral_tasa,
  hallazgos: [Finding]}`, con
  `CompetidorMedido = {brand_id, nombre, declarado, nombre_declarado, puesto, score,
  ventaja_puntos, tasa_espontanea, n_espontaneo}`. Propuesta: un bloque `competidores` en
  `GET /studies/{id}`. Los `hallazgos` (`F-competidor-no-declarado`, `F-declarado-poco-visible`)
  pueden sumarse a los de `detect_findings` antes del plan, respetando el máximo de 7 de la
  propuesta. Hay que añadir el modelo al checkpointer.
- **Aviso de A sobre `nodes/market.py`:** envía `{"brief", "candidatos"}`, pero
  `prompts/market.v1.md` espera `brief_summary` y `marcas_candidatas`. Con DeepSeek, el LLM puede
  tratar los candidatos como ausentes y dejar fuera del mercado las marcas de contexto. Detalle en
  `docs/estado/A.md`.

## Falta
- Estudio de Alborada con DeepSeek real → `docs/ejemplos/` (bloqueado: falta `DEEPSEEK_API_KEY`).
  Dos formas: completo (juez DeepSeek, ≈1–2,5 € y 20–30 min) o rápido con `JUDGE_PROVIDER=reglas`.
- `StudyRunner.fallos` vive en memoria y se pierde al reiniciar.
- Con los precios de `settings`, un estudio real completo (624 llamadas, 4 motores) cuesta unos
  10,56 € y `BUDGET_EUR_MAX` es 5 €: hay que subir el tope o reducir el estudio.

## Siguiente tarea
- Endpoints de seguimiento sobre las cuentas: `GET /brands`, `GET /brands/{id}/serie`,
  `GET /studies/{id}/remeasure/estimate` y `remeasure` con confirmación de coste.
- Ajustar `LLM_TOKENS` de `estimate.py` con las `Trace` del primer estudio real.
- Estudio de Alborada con DeepSeek en cuanto haya `DEEPSEEK_API_KEY`.
- Persistir `StudyRunner.fallos` para que el estado `error` sobreviva a un reinicio.

## No tocar
- Cifras: se calculan en `domain/`, nunca en nodos ni en la API.
