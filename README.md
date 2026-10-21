# posiq.

Posicionamiento + IQ: sistema agéntico que mide la visibilidad de una marca en asistentes de IA
(ChatGPT, Gemini, Perplexity, Claude), la compara con competidores y genera una propuesta con plan
de acción. Convenciones y reglas en [CLAUDE.md](CLAUDE.md) y [CONTRIBUTING.md](CONTRIBUTING.md).

Un estudio recorre `brief → mercado → [revisión humana] → preguntas → motores → juez → métricas →
plan → [revisión humana] → propuesta`. Las cifras las calcula el código (`src/posiq/domain/`); el
LLM solo interpreta y redacta sobre ellas. Arquitectura y decisiones en [`docs/adr/`](docs/adr/).

## Requisitos

| Herramienta | Versión | Para qué |
|---|---|---|
| Python | 3.12 o superior | API y grafo |
| [uv](https://docs.astral.sh/uv/) | reciente | Entorno y dependencias de Python |
| Node.js | 22 (la del CI) | Interfaz web |
| LibreOffice | opcional | Exportar a PDF (sin él, solo Word) |

Instalar uv en Windows (mejor que `pip install uv`, que no siempre lo deja en el PATH):

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Arranque rápido: demo sin claves

El modo kit no llama a ninguna API ni gasta nada, haya o no claves en el entorno o en `.env`
(ADR 0018): usa las 624 respuestas sintéticas del kit, las etiquetas del kit como juez y textos de
ejemplo para el caso **Clínica Alborada Visión**. Con `LLM_PROVIDER=fixture` tampoco el modo real
llama al LLM.

```sh
git clone https://github.com/equipo-hackaton-reload/hackaton.git
cd hackaton
uv sync
cp .env.example .env              # y pon LLM_PROVIDER=fixture
```

**Terminal 1 · API** (http://localhost:8000):

```powershell
# PowerShell
$env:LLM_PROVIDER = "fixture"; uv run uvicorn posiq.interfaces.api.main:app --port 8000
```

```sh
# bash
LLM_PROVIDER=fixture uv run uvicorn posiq.interfaces.api.main:app --port 8000
```

**Terminal 2 · web** (http://localhost:5173):

```sh
cd apps/web
cp .env.example .env.local        # y pon VITE_USE_MOCKS=false para usar la API real
npm ci
npm run dev
```

Con `VITE_USE_MOCKS=true` la web funciona sola, sin backend, con datos simulados (MSW).

**Sin web**, el flujo completo por la API (crea el estudio, aprueba las dos revisiones y descarga el
Word en `data/demo/`):

```sh
uv run python scripts/demo_kit.py --base-url http://localhost:8000
```

El modo fixture es una demostración: solo interpreta el brief de Alborada y no mide la calidad de
un LLM real. Guion clic a clic de la demo en [`docs/demo/guion.md`](docs/demo/guion.md); si algo
falla, [`docs/plan-b.md`](docs/plan-b.md).

## Con claves: estudio real

Las claves van en `.env` (está en `.gitignore`; nunca se suben). Las variables están en
[`.env.example`](.env.example):

| Variable | Para qué |
|---|---|
| `DEEPSEEK_API_KEY` | LLM de los nodos (brief, mercado, plan, redacción) y juez de respaldo |
| `TYPESAFE_API_KEY` | Juez Jev |
| `OPENAI_API_KEY`, `GEMINI_API_KEY`, `PERPLEXITY_API_KEY`, `ANTHROPIC_API_KEY` | Motores reales (`modo=real`) |
| `JUDGE_PROVIDER` | `auto` (por defecto) o `reglas`: juez solo por reglas, sin llamadas al LLM |
| `BUDGET_EUR_MAX` | Tope de gasto por estudio (5 € por defecto); el estudio se para al superarlo |

Antes de lanzar un estudio, mira cuánto costará:

```sh
curl "http://localhost:8000/estimate?modo=real"
```

- **Modo kit:** 0 €, siempre. Para ensayar el LLM y el juez de pago sobre las respuestas del kit
  hay que pedirlo con `KIT_IA_REAL=true`. Entonces, con `JUDGE_PROVIDER=reglas` cuesta céntimos y
  tarda minutos; con el juez LLM son unas 2.928 evaluaciones (≈ 20–30 min).
- **Qué cuenta la estimación:** motores, LLM de intake, market, prompts, plan y redacción (tokens
  típicos, con el reintento de plan y redacción), juez con su fallback y PlanGuard. Los intentos
  fallidos también quedan en `/traces` y cuentan en `BUDGET_EUR_MAX`.
- **Modo real:** consulta los motores con búsqueda web. Con los precios provisionales de
  `settings.py`, un estudio del tamaño del kit (52 preguntas × 4 motores × 3 repeticiones = 624
  llamadas) supera el tope de 5 €: sube `BUDGET_EUR_MAX` o reduce el estudio. Los precios están sin
  contrastar con las tarifas oficiales.

## API

Todo salvo `/health` y el alta de cuentas exige `Authorization: Bearer <token>`; cada usuario solo
ve sus estudios (los ajenos dan 404). No hay correo real: el código de verificación sale en el log de
la API y, con `LLM_PROVIDER=fixture`, también en la respuesta (`codigo_dev`). Detalle en
[ADR 0015](docs/adr/0015-cuentas-y-propiedad.md).

| Método | Ruta | Qué hace |
|---|---|---|
| `POST` | `/auth/register` | Alta `{email, password, nombre?}`; envía el código de verificación |
| `POST` | `/auth/verify` | `{email, codigo}` verifica el correo (`/auth/verify/reenviar` pide otro) |
| `POST` | `/auth/login` | `{email, password}` → `{token, expira_en, user}` |
| `POST` | `/auth/logout` · `GET` `/auth/me` | Cierra la sesión · usuario de la sesión |
| `POST` | `/studies` | Crea y lanza un estudio: JSON `{brief_texto, modo}`, Markdown, texto o Word |
| `GET` | `/studies` | Lista de estudios (`?brand_id=` para una marca) |
| `GET` | `/studies/{id}` | Estado, revisión pendiente, métricas, hallazgos, plan, simulación, delta y propuesta |
| `POST` | `/studies/{id}/resume` | Aprueba o edita una revisión: `{"revision": "competidores" \| "plan", "payload": …}` |
| `POST` | `/studies/{id}/remeasure` | Re-mide un estudio completado con el mismo brief y mercado |
| `GET` | `/studies/{id}/evaluations?ids=` | Evidencias: evaluación, motor, prompt y respuesta |
| `GET` | `/studies/{id}/traces` | Llamadas externas del estudio: modelo, tokens y coste |
| `GET` | `/studies/{id}/export?formato=docx\|pdf` | Propuesta en Word o PDF |
| `GET` | `/estimate?modo=` | Coste estimado antes de ejecutar |
| `GET` | `/health` | Estado del servicio |

Documentación interactiva en http://localhost:8000/docs con la API arrancada.

## Desarrollo

```sh
uv run pre-commit install         # una vez por worktree: ruff, formato y mypy en cada commit
uv run pytest                     # tests de Python (lo mismo que el CI)
cd apps/web && npm test && npm run lint && npm run build
```

Se trabaja por zonas, en ramas `feature/<ZONA>-<tarea>` y con PR a `develop`. Cada PR actualiza el
CHANGELOG y `docs/estado/<ZONA>.md`. Detalle en [CONTRIBUTING.md](CONTRIBUTING.md).

## Limitaciones

- Los datos del kit son sintéticos: no representan el comportamiento real de ningún motor.
- Los modelos no son deterministas: una medición es una foto en una fecha. Por eso existe la
  re-medición; en modo kit su delta es 0, porque mide repetibilidad y no una mejora.
- SQLite con un solo proceso: la API no está preparada para varios workers. El límite de intentos
  de login y verificación vive en memoria del proceso.
- Sin proveedor de correo ni recuperación de contraseña: el código de verificación se lee del log.
- La calibración del juez con claves reales y la prueba real de los motores están pendientes
  ([`docs/calibracion/`](docs/calibracion/)).
