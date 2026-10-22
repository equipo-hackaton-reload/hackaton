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
- Revisión de cuentas (`feature/C-cuentas-coste-fixes`): intentos de verificación atómicos
  (`AccountRepo.count_attempt`, `UPDATE … RETURNING`, contado antes de comparar); 3 reenvíos por
  correo, cliente y hora y 10 por correo; límite por IP y ruta, por IP y correo y por correo con
  umbral 5 veces mayor, con cortocircuito (verificar y reenviar comparten clave; el bloqueo de
  cuentas ajenas queda como riesgo residual, ADR 0015 punto 10); `RateLimiter` purga claves
  caducadas; tiempo igual
  exista o no el correo en alta y reenvío; el 409 del alta se mantiene (riesgo aceptado, ADR 0015
  punto 11); brief leído en streaming con tope (413 sin `Content-Length`); cuenta de demo y
  `AUTH_DEMO_USER` solo en modo demo (`demo_activo`, si no 403 `cuenta_demo_desactivada`). El
  nodo `run` adjunta las trazas ya pagadas a su excepción y el runner las guarda con `db`.
  `POST /studies` devuelve `aviso` en modo kit (`AVISO_KIT` en `interfaces/api/schemas.py`).
- Coste (ADR 0018): el modo kit es siempre gratis aunque haya claves (`FixtureLLM`,
  `FixtureJudge` con las etiquetas del kit, sin PlanGuard); `KIT_IA_REAL=true` es el opt-in para
  usar el LLM y el juez de pago sobre el kit. Lo ya pagado en un nodo que falla (intentos de
  `LLMOutputError`, reintentos de plan/redacción, PlanGuard, juez y su fallback) viaja en la
  excepción y `StudyRunner` lo suma al checkpoint y al repo: sale en `/traces` y en
  `coste_acumulado_eur` también con estado `error`. `GET /estimate` cuenta LLM de los nodos
  (`LLM_TOKENS`), juez con fallback (25 %) y PlanGuard; `estimate_study(..., remedicion=True)`
  quita intake y market (para `GET /studies/{id}/remeasure/estimate`).

## Elegir escenario (`feature/C-elegir-escenario`)
- `GET /studies/{id}/scenarios` (los tres preajustes del nodo `plan`, `completo` elegido);
  `POST /studies/{id}/scenarios` con una `EntradaEscenario` → 201 `{id: "P1", …}` (422 si nombra
  acciones que no están en el plan, 409 sin plan o con el grafo en marcha);
  `POST /studies/{id}/scenarios/{eid}/elegir` (404 si no existe, 409 con la propuesta redactada).
  Los escenarios se escriben en el checkpoint sin cambiar el siguiente nodo: el plan se aprueba
  después con normalidad.
- `write` (`con_escenario`): con un escenario elegido distinto de `completo`, la propuesta y el
  redactor ven solo sus acciones y la primera limitación lo declara («Propuesta con el escenario…»).
  El plan aprobado del estudio no cambia y el presupuesto sigue siendo el del plan completo (el
  coste declarado se cita aparte). Con `completo` la propuesta es la de siempre (golden intactos).
- Editar el plan en la revisión recalcula los preajustes y descarta los personalizados.

## Seguimiento (A2, `feature/C-seguimiento-api`)
- `GET /brands` → `[{brand_id, nombre, n_mediciones, ultima_medicion}]`: marcas de los estudios
  visibles del usuario (ADR 0015). `n_mediciones` cuenta solo los completados; una marca con un
  estudio en curso aparece con 0 y `ultima_medicion` null. Orden: la medición más reciente primero.
- `GET /brands/{id}/serie` → `SerieMarca` de `domain.tracking.construir_serie` (ADR 0016) con los
  estudios completados del usuario de esa marca: muestra, mercado, exactitud y trazas salen del
  checkpoint de cada estudio; catálogo del kit. Bootstrap fuera del bucle de eventos. 404 sin
  mediciones completadas (o si la marca es de otro usuario).
- `GET /studies/{id}/remeasure/estimate` → `CostEstimate` con `remedicion=True` y el número de
  prompts del original (la re-medición reutiliza su banco).
- `POST /studies/{id}/remeasure` acepta `{confirmado: true, coste_estimado_eur}`. Si la estimación es
  mayor que 0, el cuerpo es obligatorio (409 sin él) y la estimación actual no puede superar la
  confirmada (409 «ha subido»; margen de 0,005 €). En modo kit cuesta 0 y sigue sin cuerpo.

## Diferencial v0.4.0 (conectado, `feature/C-diferencial-grafo`)
- Nodo `diferencial` entre `analyze` y `plan` (`application/nodes/diferencial.py`), sin LLM ni
  coste. Todo sale de `domain/`:
  - `rigor`: `informe_rigor` + `intervalos_score_por_motor` + `aparicion_por_motor`; en una
    re-medición, `significancia_remedicion(...).por_clave()` en `deltas`.
  - `competidores`: `brecha_competidores(brief, market, metrics)`. Sus hallazgos NO se suman a
    `findings` (los 7 hallazgos del golden de Alborada no cambian).
  - `oportunidades_fuente`: `mapa_fuentes(brief.sector, [este estudio], catálogo)` +
    `oportunidades_fuente` de la marca foco.
  - `exactitud` y `mitigaciones`: `evaluar_exactitud` solo para la marca del brief, solo reglas
    (la capa LLM `claims.v1` no se usa en el grafo).
  - Cada bloque se calcula por separado: si uno lanza `ValueError`/`KeyError`, queda en null con el
    motivo en `errores` («diferencial: … sin calcular: …») y el estudio sigue.
    Dentro de `rigor`, los deltas de la re-medición van aparte: si el contraste con la medición
    anterior falla, `rigor.deltas` queda vacío con «diferencial: rigor.deltas sin calcular: …» en
    `errores` y se conservan los IC y significancias de la medición actual.
- Coste en tiempo: con Alborada, ≈2,7 s en esta máquina (1,4 s el informe con 2000 réplicas,
  0,5 s los cuatro motores, 0,8 s la exactitud; el ADR 0008 habla de ≈4 s en otra). Corre en
  `asyncio.to_thread`: no bloquea el bucle de la API (test con latidos del bucle). Una re-medición
  añade otro bootstrap (≈1 s).
- `escenarios`: `build_presets` en `plan` (dentro de `plan_checks`) y, si la persona edita el plan,
  en `review_plan`. Tres `EscenarioGuardado` (`minimo_viable`, `equilibrado`, `completo`) con el
  completo `elegido`. `EscenarioPlan.intervalo` sigue en null (no hay IC del score proyectado en
  el dominio).
- Forma del JSON para la web y el Word (`GET /studies/{id}`):
  - `rigor`: `{score_global: Intervalo|null, score_por_motor: {Motor: Intervalo},
    aparicion_por_motor: {Motor: Intervalo}, hallazgos: {finding_id: SignificanciaHallazgo},
    deltas: {"score_global" | "tipo:dimension:valor": Significancia}, replicas_bootstrap,
    semilla_bootstrap}`. **Cambio:** `hallazgos` es ahora `SignificanciaHallazgo`
    (`{finding_id, contraste, significancia: Significancia|null, sin_contraste: str|null}`): un
    hallazgo sin contraste (`F-fuente-lider`) lo dice, no se lee como «no significativo».
  - `competidores` (nuevo, aditivo): `BrechaCompetidores` (forma en `domain/competitor_gap_schemas.py`).
  - `escenarios`: `[{id, elegido, escenario: EscenarioPlan}]`; `oportunidades_fuente`:
    `[OportunidadFuente]`; `exactitud`: `[HallazgoExactitud]` (uno, la marca del brief);
    `mitigaciones`: `[AccionMitigacion]`.
  - Alborada en fixture (`tests/e2e/test_diferencial_api.py`): score 25,93 [21,6–30,15], Oftalmos
    Centro como sorpresa, top de oportunidades wikipedia.org (Media), 0 incorrectas, 3 escenarios.
- Re-medición comparable: `prepare_remeasure` siembra también los `prompts` del original (el nodo
  `prompts` los reutiliza si ya están en el estado, en cualquier modo) y `medicion_anterior`
  (`TypedDict` con métricas, prompts, ejecuciones y evaluaciones del original; un modelo con
  modelos anidados no sobrevive al checkpointer). La huella del banco coincide.
- Claves de los prompts: `market` manda `brief_summary` y `marcas_candidatas` (antes `brief` y
  `candidatos`, que el prompt no declaraba); `prompts` (modo real) manda `brief_summary`, `market` y
  `banco_plantillas` (antes faltaba el banco: el LLM no tenía plantillas); `plan` usa `plan.v2.md`,
  cuya cabecera declara lo que el nodo ya mandaba. `tests/application/test_prompt_state.py` graba
  todas las llamadas y lo comprueba para todos los prompts.

## Auditoría técnica web (ADR 0019, `feature/C-web-audit-nodo`)
- Nodo `web_audit` (`application/nodes/web_audit.py`) entre `judge` y `analyze`, `external=True`
  (reintentos del grafo; el fetcher no lanza). Con `Deps.web_fetcher=None` o marca sin
  `dominio`: `auditoria_web=None`, sin descargas ni trazas.
- Descargas: los 12 `RECURSOS` en paralelo (un hilo cada una), después las `Sitemap:` de
  robots.txt que cumplen `url_permitida` (sin repetir el `/sitemap.xml` fijo) y hasta 3 páginas
  (`paginas_sitemap`). `analizar_web` + `hallazgos_web` + `vincular_hallazgos` (todo `domain/`).
- Trazas: una por descarga, `nodo="web_audit"`, `modelo="http:<fetcher.name>"`,
  `prompt_version="web_audit.v1"`, 0 tokens, coste 0, `duracion_ms` de la respuesta.
- `origen`: `fixture` con `FixtureWebFetcher` y SIEMPRE en modo kit (regla de oro), `real` solo en
  modo real con el fetcher httpx. `analyze` suma `hallazgos_web` a `findings` solo si es `real`
  (el plan puede usar la palanca `tecnico`); en fixture quedan aparte y los 7 hallazgos / 9
  acciones de Alborada no cambian (`tests/e2e/test_web_audit_api.py`).
- Configuración: `WEB_AUDIT=off|fixture|real` (`off` por defecto; en kit `real` → fixture, vía
  `adapters.web.crear_web_fetcher`) y `WEB_AUDIT_TIMEOUT_S` (tope por recurso del fetcher real,
  recortado a 10 s). El encargo hablaba de `web_audit_enabled`; se sigue el ADR 0019 (`Literal`).
- Checkpointer: admite los modelos de `web_audit_schemas` (ida y vuelta probada).
- `GET /estimate` no cambia (coste 0).

### Cambios de contrato para la Mitad B
- `GET /studies/{id}` añade (aditivo, null si la auditoría está apagada o no hay dominio):
  - `auditoria_web: AuditoriaWeb | null` (forma en `domain/web_audit_schemas.py`: `dominio`,
    `origen` `real|fixture`, `fetcher`, `puntuacion`, `bloques[{bloque, puntuacion, ...}]`,
    `comprobaciones[{id, bloque, estado, detalle, evidencia, recurso, motores_afectados}]`,
    `accesos_bots[{bot, motor, permitido, regla}]`, `recursos`, `finding_ids`...). Con
    `origen="fixture"`, rótulo «Ejemplo (caso sintético)».
  - `hallazgos_web: Finding[] | null`: los hallazgos técnicos (`F-web-*`). Con `origen="real"`
    están también en `findings`; con `fixture`, solo aquí.
- `GET /studies/{id}/traces` incluye las trazas `web_audit` (coste 0).

## Falta
- Estudio de Alborada con DeepSeek real → `docs/ejemplos/` (bloqueado: falta `DEEPSEEK_API_KEY`).
  Dos formas: completo (juez DeepSeek, ≈1–2,5 € y 20–30 min) o rápido con `JUDGE_PROVIDER=reglas`.
- `StudyRunner.fallos` vive en memoria y se pierde al reiniciar.
- Con los precios de `settings`, un estudio real completo (624 llamadas, 4 motores) cuesta unos
  10,56 € y `BUDGET_EUR_MAX` es 5 €: hay que subir el tope o reducir el estudio.

## Siguiente tarea
- Web (zona D): pintar `rigor`, `competidores`, `oportunidades_fuente`, `exactitud` y `escenarios`.
- Ajustar `LLM_TOKENS` de `estimate.py` con las `Trace` del primer estudio real.
- Estudio de Alborada con DeepSeek en cuanto haya `DEEPSEEK_API_KEY`.
- Persistir `StudyRunner.fallos` para que el estado `error` sobreviva a un reinicio.

## No tocar
- Cifras: se calculan en `domain/`, nunca en nodos ni en la API.
