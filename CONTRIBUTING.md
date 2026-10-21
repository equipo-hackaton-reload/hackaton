# Contribuir a posiq.

## Ramas (git flow simplificado)

- `main`: solo recibe merges desde `develop`, cada uno etiquetado `vX.Y.Z`.
- `develop`: rama de integración.
- Cada tarea en `feature/<LETRA-ZONA>-<tarea>` creada desde `develop`
  (p. ej. `feature/A-domain-core`, `feature/B-jev`).
- **Nunca** se hace push directo a `develop` ni a `main`.

## Pull requests

- **Revisión y CI:** PR obligatorio a `develop` con CI en verde. No hace falta aprobación humana.
- **Fusión:** quien abre la PR la fusiona con squash (`gh pr merge <n> --squash --delete-branch`)
  en cuanto CI pase.
- **Conflictos con `develop`:** los resuelve el agente de esa rama:
  1. `git fetch origin && git rebase origin/develop`.
  2. Resuelve conservando ambos lados; si el conflicto es en `uv.lock`, ejecuta `uv lock`.
  3. Pasa ruff, mypy y pytest.
  4. `push --force-with-lease` y fusiona.
- **Después del squash:** la rama se borra y la siguiente tarea empieza en una rama nueva desde
  `develop`. Nadie rebasa una rama sobre su propio squash.

- **CHANGELOG por PR:** cada PR añade al menos una línea en `CHANGELOG.md` → `[Unreleased]`
  (sección `Added`, `Changed` o `Fixed`), indicando la zona. Una PR sin línea en el CHANGELOG no se fusiona.
- **Estado por zona:** cada PR actualiza `docs/estado/<LETRA>.md` de su zona (qué hay, qué falta,
  siguiente tarea).

## Pre-commit

Obligatorio en cada worktree antes del primer commit:

```sh
uv run pre-commit install
```

Los hooks (`.pre-commit-config.yaml`) ejecutan `ruff --fix`, `ruff format` y `mypy src`. No se
salta ningún hook (`--no-verify` prohibido); si un hook falla, se corrige y se vuelve a hacer commit.
Antes de abrir la PR, además: `uv run pytest` en verde (es lo mismo que comprueba el CI).

## Commits

[Conventional Commits](https://www.conventionalcommits.org/es/): `feat(domain): ...`, `fix(api): ...`,
`chore: ...`, `docs: ...`, `test: ...`. El scope es la zona o la carpeta tocada.

## Versionado

- `VERSION` sigue SemVer: **MINOR** por cada nivel del reto completado, **PATCH** por correcciones.
- Al cerrar un hito: subir `VERSION`, mover `[Unreleased]` a `[X.Y.Z] - AAAA-MM-DD` en el CHANGELOG,
  abrir el PR `develop → main` y, tras el merge, etiquetar en `main`:

  ```sh
  git checkout main && git pull
  git tag vX.Y.Z && git push origin vX.Y.Z
  ```

## Reparto por zonas

Cada persona es dueña de una zona y solo abre PRs que toquen su zona. Para tocar otra zona hay que
avisar antes a su dueño. Los dueños están en `.github/CODEOWNERS`.

| Zona | Carpetas | Contenido |
|---|---|---|
| A | `src/posiq/domain/`, `tests/domain/`, `tests/golden/` | esquemas, detección, score, métricas, hallazgos, preguntas del juez |
| B | `adapters/engines/`, `adapters/judge/`, `adapters/llm/` | kit, APIs reales, Jev y fallback, cliente DeepSeek |
| C | `application/`, `interfaces/api/` | grafo LangGraph, nodos, interrupts, API, jobs |
| D | `apps/web/` | interfaz React |
| E | `adapters/export/`, `prompts/`, `docs/`, presentación | plantillas Word/PDF, prompts versionados, documento de arquitectura |

## Contratos compartidos

`src/posiq/domain/schemas.py` y `src/posiq/ports.py` se cierran **el primer día**. Para cambiarlos
después hace falta:

1. Un PR con la etiqueta `contract-change`.
2. Aviso en el canal del equipo.
3. Actualizar en ese mismo PR, o coordinado con sus dueños, todo el código que dependa del contrato.

## Sesiones paralelas de Claude Code

Cada persona trabaja en su propio `git worktree` sobre su rama feature, para que dos agentes nunca
escriban en el mismo directorio de trabajo:

```sh
git fetch origin
git worktree add -b feature/<LETRA-ZONA>-<tarea> ../posiq-<LETRA-ZONA> origin/develop
cd ../posiq-<LETRA-ZONA> && uv sync
```

Al terminar: `git worktree remove ../posiq-<LETRA-ZONA>`.

## Protección de ramas

El repo `equipo-hackaton-reload/hackaton` es **privado y está en plan gratuito**: GitHub no aplica
reglas de protección de ramas ni *rulesets* a repos privados en ese plan. La protección es por
convención y la hacen cumplir los propios agentes:

- **Sin push directo** a `main` ni a `develop`: todo entra por PR. `.claude/settings.json` deniega
  `git push origin main|develop` y los `push --force` sin `--force-with-lease`.
- **CI en verde** (`check` y `web`) antes de fusionar: `gh pr checks <n>` y luego
  `gh pr merge <n> --squash --delete-branch`.
- **Solo squash** a nivel de repo y borrado automático de la rama tras fusionar (lo configura un admin):

  ```sh
  gh api -X PATCH repos/equipo-hackaton-reload/hackaton     -f allow_merge_commit=false -f allow_rebase_merge=false -F delete_branch_on_merge=true
  ```

- `main` solo recibe la PR `develop → main` de cada hito, abierta por la zona A.

Si el repo pasa a público o a un plan de pago, se activan reglas reales para `main` y `develop`
(PR obligatoria, check `check` requerido, sin force push ni borrado).
