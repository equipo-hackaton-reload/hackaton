"""Comprueba que `src/types/schemas.ts` replica campo a campo los modelos de `domain/schemas.py`.

Uso (desde la raíz del repo): `uv run python apps/web/scripts/check_types.py`
"""

import re
import sys
from pathlib import Path

from pydantic import BaseModel

from posiq.domain import schemas

TS = Path(__file__).resolve().parents[1] / "src" / "types" / "schemas.ts"
INTERFACE = re.compile(r"export interface (\w+) \{(.*?)\n\}", re.S)
FIELD = re.compile(r"^\s*(?:readonly\s+)?(\w+)\??:", re.M)


def main() -> int:
    ts = {name: set(FIELD.findall(body)) for name, body in INTERFACE.findall(TS.read_text("utf-8"))}
    modelos = {
        name: obj
        for name, obj in vars(schemas).items()
        if isinstance(obj, type)
        and issubclass(obj, BaseModel)
        and obj.__module__ == schemas.__name__
        and not name.startswith("_")
    }
    errores = []
    for name, model in sorted(modelos.items()):
        py = set(model.model_fields) | set(model.model_computed_fields)
        if name not in ts:
            errores.append(f"{name}: falta la interfaz en schemas.ts")
        elif py != ts[name]:
            solo_py, solo_ts = sorted(py - ts[name]), sorted(ts[name] - py)
            errores.append(f"{name}: solo en Python {solo_py}, solo en TS {solo_ts}")
    for e in errores:
        print(e)
    print("OK: tipos alineados" if not errores else f"{len(errores)} modelos divergen")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
