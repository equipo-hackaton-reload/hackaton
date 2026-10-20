# posiq/interfaces

Interfaces de entrada; `api/` es la app FastAPI (`uvicorn posiq.interfaces.api.main:app`).

- `api/main.py`: endpoints y `create_app(runner=None, settings=None)`.
- `api/schemas.py`: cuerpos y respuestas (contrato con la web, Zona D).
- `api/wiring.py`: construye `Deps` y `StudyRunner` desde `Settings`.
