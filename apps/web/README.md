# apps/web — interfaz de posiq.

Interfaz React de la zona D. Recorre un estudio completo en cinco pantallas: brief, revisión de
competidores, diagnóstico, revisión del plan y propuesta.

Stack: Vite + React 18 + TypeScript + TanStack Query + React Router + Tailwind. Sin estado global:
el estado del estudio vive en la caché de TanStack Query y se sondea cada 3 s mientras está en curso.

## Arrancar

Requiere Node 20 o posterior.

```sh
cd apps/web
npm install
cp .env.example .env.local   # y ajusta las variables
npm run dev                  # http://localhost:5173
```

### Con mocks (sin backend)

```sh
# .env.local
VITE_API_URL=
VITE_USE_MOCKS=true
```

MSW intercepta las llamadas en el navegador (`public/mockServiceWorker.js`) y simula el grafo: cada
tramo tarda unos 4,5 s, así que se ve el sondeo y los estados «en curso». Los estudios del mock se
guardan en `sessionStorage` y sobreviven a recargar la página.

El mock devuelve siempre el caso **Clínica Alborada Visión** del kit, sea cual sea el brief. Sus
cifras no están escritas a mano: `src/mocks/fixtures/` sale de ejecutar `posiq.domain` sobre el kit
(score 25,93, 8.ª de 10, líder Valdecruz 66,46). El plan, la propuesta y las trazas son de ejemplo,
pero leen sus valores actuales de esas métricas. La descarga Word del mock es un `.txt`; la de PDF
es un PDF mínimo válido.

### Contra la API

```sh
# .env.local
VITE_API_URL=http://localhost:8000
VITE_USE_MOCKS=false
```

y en la raíz del repo: `uv run uvicorn posiq.interfaces.api.main:app --reload`. La API debe permitir
CORS desde el origen de Vite.

## Scripts

| Comando | Qué hace |
|---|---|
| `npm run dev` | Servidor de desarrollo |
| `npm run build` | Comprueba tipos y genera `dist/` |
| `npm run lint` | ESLint sin avisos permitidos |
| `npm test` | Vitest + Testing Library, con MSW en Node |

Desde la raíz del repo, con el entorno de Python:

| Comando | Qué hace |
|---|---|
| `uv run python apps/web/scripts/check_types.py` | Comprueba que `src/types/schemas.ts` replica campo a campo `domain/schemas.py` |
| `uv run python apps/web/scripts/gen_mock_fixtures.py` | Regenera los fixtures del mock con el dominio |

## Estructura

```
src/
  api/        cliente HTTP, hooks de TanStack Query (sondeo de 3 s) y QueryClient
  components/ bloques de pantalla: score, ranking, visibilidad, fuentes, hallazgos, evidencias,
              editores de marcas y acciones, trazas
  pages/      cuentas (login, registro, verificación), las cinco pantallas del estudio, su layout
              y el seguimiento por marca
  mocks/      handlers de MSW, estudios en memoria y fixtures del kit
  types/      espejo de schemas.py (schemas.ts) y contrato HTTP (api.ts)
  lib/        formato es-ES y utilidades sin React
```

## Contrato con la API (zona C)

Contrato base:

| Método | Ruta | Cuerpo | Respuesta |
|---|---|---|---|
| POST | `/studies` | `{brief_texto, modo: "kit" \| "real"}` | `{study_id}` |
| GET | `/studies/{id}` | — | `{study, estado, revision_pendiente, coste_acumulado_eur, errores, brief?, market?, metrics?, findings?, plan?, proposal?}` |
| POST | `/studies/{id}/resume` | `{revision: "competidores", payload: Market}` o `{revision: "plan", payload: Plan}` | 202 |
| GET | `/studies/{id}/export?formato=docx\|pdf` | — | fichero, con `Content-Disposition` |
| GET | `/studies?brand_id=` | — | `Study[]` |

Endpoints que la web **asume además** y que la zona C debe confirmar. Si no existen, la web degrada:

| Método | Ruta | Respuesta | Si falta |
|---|---|---|---|
| GET | `/studies/{id}/evaluations?ids=a,b` | `[{evaluation, motor, prompt, texto_respuesta, fuentes}]` | El panel de evidencias muestra solo los ids |
| GET | `/studies/{id}/traces` | `Trace[]` | El panel de trazas dice que no hay datos |
| GET | `/estimate?modo=kit\|real` | `{llamadas, coste_estimado_eur, presupuesto_max_eur, …}` | Sin estimación en la pantalla 1; en real hay que confirmar para lanzar |

### Cuentas y seguimiento (contrato acordado con C; mientras no esté en la API, lo simula MSW)

Todo endpoint salvo `/health` y `/auth/register|verify|verify/reenviar|login` exige
`Authorization: Bearer <token>`; sin él o caducado, 401 y la web vuelve a `/login?next=<ruta>`. Un
estudio ajeno responde 404.

| Método | Ruta | Cuerpo | Respuesta |
|---|---|---|---|
| POST | `/auth/register` | `{email, password, nombre?}` | 201 `{user, verificacion: {enviado, codigo_dev?}}`; 409 si existe; 422 si la contraseña tiene menos de 8 caracteres |
| POST | `/auth/verify` | `{email, codigo}` | 200 `{user}`; 429 tras 5 intentos |
| POST | `/auth/verify/reenviar` | `{email}` | 202 |
| POST | `/auth/login` | `{email, password}` | 200 `{token, expira_en, user}`; 401; 403 `correo_no_verificado` |
| POST | `/auth/logout` | — | 204 |
| GET | `/auth/me` | — | `{user}` |
| GET | `/brands` | — | `[{brand_id, nombre, n_mediciones, ultima_medicion}]` |
| GET | `/brands/{id}/serie` | — | `SerieMarca` (`src/types/tracking.ts`) |
| GET | `/studies/{id}/remeasure/estimate` | — | `CostEstimate` |
| POST | `/studies/{id}/remeasure` | `{confirmado: true, coste_estimado_eur}` | 201 `{study_id, remedicion_de}`; 400; 409 (coste cambiado o re-medición en curso) |
| GET | `/estimate?modo=kit\|real` | — | `CostEstimate` (también en kit: el juez puede costar) |

Con los mocks, la cuenta de demostración es `demo@posiq.app` / `demo1234`; trae dos mediciones de
ejemplo anteriores para que el seguimiento muestre un cambio de método y un cambio significativo.
Cualquier otra cuenta se registra en la propia web (el código aparece en pantalla: modo demo).

Supuestos de comportamiento:

- Los errores llegan como `{"detail": "..."}` (formato de FastAPI) y se muestran tal cual.
- `errores` trae, durante la revisión del plan, las violaciones de `validate_plan_against_brief`.
- Tras el `resume`, `GET /studies/{id}` devuelve `estado: "en_curso"` hasta la siguiente revisión.
- Cuando existe `plan`, la respuesta puede incluir `simulacion` (rangos por fase) y `calidad_plan`
  (calidad por acción); ambos se muestran como ayudas orientativas y no sustituyen una re-medición.
- Una re-medición devuelve un nuevo `study_id`; si existe `metrics_delta`, el diagnóstico muestra
  el score anterior, actual y su diferencia.
