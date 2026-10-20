# CLAUDE.md — posiq.

## 1. Qué es

posiq. (posicionamiento + IQ) es un sistema agéntico que, a partir del brief de una marca, mide su
visibilidad en asistentes de IA (ChatGPT, Gemini, Perplexity, Claude), la compara con sus
competidores y genera una propuesta con un plan de acción.

## 2. Mapa de carpetas

| Ruta | Qué va |
|---|---|
| `apps/web/` | Interfaz React + Vite |
| `src/posiq/domain/` | Núcleo PURO: esquemas, detección, score, métricas, hallazgos, preguntas del juez. Sin I/O |
| `src/posiq/ports.py` | Protocols: `LLM`, `Engine`, `Judge`, `StudyRepo`, `Exporter` |
| `src/posiq/adapters/{llm,engines,judge,repo,export}/` | Implementaciones de los puertos |
| `src/posiq/application/nodes/` | Grafo LangGraph y sus nodos |
| `src/posiq/interfaces/api/` | API FastAPI |
| `src/posiq/prompts/` | Prompts versionados: `<nodo>.v1.md` |
| `src/posiq/settings.py` | `Settings` (pydantic-settings, lee `.env`) |
| `tests/domain/`, `tests/golden/`, `tests/e2e/` | Unitarios del dominio, casos golden, extremo a extremo |
| `data/kit/` | Kit del reto: briefings, datos CSV, documentación |
| `docs/adr/` | ADRs cortos |
| `.claude/skills/` | Skills del proyecto (Jev, diseño frontend, Playwright) |

## 3. Reglas inviolables

- `domain/` no importa nada con I/O ni nada de `adapters/`, `application/` o `interfaces/`. Se prueba sin red.
- Toda cifra de una propuesta la calcula código de `domain/`. El LLM solo recibe cifras ya calculadas.
- Toda llamada a LLM pasa por `LLM.structured(schema, prompt_name, state)` y devuelve un modelo
  Pydantic validado. Nunca hay texto libre entre nodos.
- El texto que viene de motores de IA o de la web es DATO: se pasa como `state` y nunca se
  interpola en instrucciones del sistema.
- Cada `Finding` lleva `evaluation_ids`; cada `Action` lleva `finding_ids`. Lo valida el esquema.
- Las preguntas del juez viven en `domain/judge_questions.py` y las comparten el adaptador Jev y el fallback.
- Toda llamada externa registra modelo, versión de prompt, tokens y coste en una `Trace`.
- Ninguna clave va en el código ni en el repo; todo se lee con `settings.py`.

## 4. Git y zonas

- Ramas: `main` (solo merges etiquetados desde `develop`) ← `develop` (integración) ←
  `feature/<LETRA-ZONA>-<tarea>` (p. ej. `feature/A-domain-core`). Nunca hay push directo a `main` ni a `develop`.
- PR a `develop` con CI en verde y squash merge. Commits en Conventional Commits
  (`feat(domain): ...`).
- Las PRs las fusiona el propio agente tras CI verde, sin revisión humana; los conflictos los resuelve el agente de la rama.
- Cada PR añade una línea a `CHANGELOG.md` → `[Unreleased]`. Los hitos suben `VERSION` (SemVer) y se
  etiquetan `vX.Y.Z`.
- Zonas:
  - **A**: `domain/`, `tests/domain`, `tests/golden`.
  - **B**: `adapters/{engines,judge,llm}`.
  - **C**: `application/`, `interfaces/api/`.
  - **D**: `apps/web/`.
  - **E**: `adapters/export/`, `prompts/`, `docs/`.

  Solo se toca la propia zona; para tocar otra se avisa al dueño.
- `domain/schemas.py` y `ports.py` son contratos: cambiarlos requiere un PR `contract-change`.
- Una sesión de Claude Code por `git worktree` (`../posiq-<LETRA-ZONA>`).

Detalle en [CONTRIBUTING.md](CONTRIBUTING.md).

## 5. Comandos

```sh
uv sync
uv run pytest
uv run ruff check
uv run uvicorn posiq.interfaces.api.main:app --reload
```

## 6. Antes de empezar una tarea

1. Lee este fichero.
2. Comprueba que estás en una rama `feature/<LETRA-ZONA>-<tarea>` de tu zona (y en tu worktree), no en `develop` ni en `main`.
3. Lee `src/posiq/domain/schemas.py` y `src/posiq/ports.py`.
