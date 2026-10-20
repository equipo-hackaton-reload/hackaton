# posiq/application

Orquestación del estudio con LangGraph (ADR 0005).

- `state.py`: `StudyState` e `initial_state`.
- `deps.py`: `Deps` (LLM, motores, fábrica del juez, repositorio, presupuesto, settings) y utilidades.
- `nodes/`: un fichero por nodo, `async def nodo(state, deps) -> dict`; `review.py` son las revisiones
  humanas con `interrupt()`.
- `graph.py`: `build_graph(deps, checkpointer)` y el checkpointer SQLite.
- `runner.py`: `StudyRunner`, que la API usa para crear, lanzar, reanudar y consultar estudios.
- `kit.py`: datos del kit para el modo `kit`.
