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

## Protección de ramas (configurar en GitHub)

Requiere permisos de **admin** en el repo, que tiene su propietario. Se configura después de hacer
push de `develop` y de que el CI haya corrido al menos una vez, para que aparezca el check `check`.

1. GitHub → repo → **Settings** → **Branches** (o **Rules → Rulesets**) → **Add branch protection rule**.
2. *Branch name pattern*: `main`.
3. Marca **Require a pull request before merging**, con *Required approvals* = **1**.
4. Marca **Require status checks to pass before merging** → *Require branches to be up to date* →
   busca y añade el check **`check`** (job del workflow CI).
5. Marca **Do not allow bypassing the above settings**.
6. Deja desmarcados *Allow force pushes* y *Allow deletions*. Guarda.
7. Repite los pasos 2–6 con `develop`.
8. Opcional, en **Settings → General → Pull Requests**: deja solo **Allow squash merging**.

Equivalente con `gh`, ejecutado por un admin:

```sh
for b in main develop; do
  gh api -X PUT repos/walterandres-dybek-sanchez/hackaton/branches/$b/protection --input - <<'JSON'
{"required_status_checks":{"strict":true,"contexts":["check"]},
 "enforce_admins":true,
 "required_pull_request_reviews":{"required_approving_review_count":1},
 "restrictions":null}
JSON
done
```
