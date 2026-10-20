"""Demo HTTP de Alborada. Servidor: LLM_PROVIDER=fixture uv run uvicorn ...

Ejecutar: uv run python scripts/demo_kit.py --base-url http://127.0.0.1:8000
"""

import argparse
import time
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import httpx

ROOT = Path(__file__).resolve().parents[1]
BRIEF = ROOT / "data/kit/01_Briefings/Brief_de_ejemplo_Clinica_Alborada.md"


def wait_for(client: httpx.Client, study_id: str, estado: str, timeout: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/studies/{study_id}")
        response.raise_for_status()
        view = response.json()
        if view["estado"] == "error":
            raise RuntimeError(view["errores"])
        if view["estado"] == estado:
            print(f"Estado: {estado}", flush=True)
            return view
        time.sleep(0.2)
    raise TimeoutError(f"El estudio no llegó a {estado} en {timeout} segundos")


def demo(client: httpx.Client, output: Path, timeout: float = 120) -> Path:
    client.get("/health").raise_for_status()
    response = client.post(
        "/studies", json={"brief_texto": BRIEF.read_text(encoding="utf-8"), "modo": "kit"}
    )
    response.raise_for_status()
    sid = response.json()["study_id"]
    print(f"Estudio creado: {sid} (kit sintético)", flush=True)
    wait_for(client, sid, "esperando_revision_competidores", timeout)
    response = client.post(
        f"/studies/{sid}/resume", json={"revision": "competidores", "payload": {"aprobado": True}}
    )
    response.raise_for_status()
    print("Competidores confirmados", flush=True)
    wait_for(client, sid, "esperando_revision_plan", timeout)
    response = client.post(
        f"/studies/{sid}/resume", json={"revision": "plan", "payload": {"aprobado": True}}
    )
    response.raise_for_status()
    print("Plan aprobado", flush=True)
    view = wait_for(client, sid, "completado", timeout)
    print(f"Coste: {view['coste_acumulado_eur']} EUR", flush=True)
    response = client.get(f"/studies/{sid}/export", params={"formato": "docx"})
    response.raise_for_status()
    output.mkdir(parents=True, exist_ok=True)
    path = output / f"alborada-{sid}.docx"
    path.write_bytes(response.content)
    with ZipFile(path) as doc:
        assert "word/document.xml" in doc.namelist(), "La respuesta no es un Word válido"
    print(f"Word descargado: {path} ({len(response.content)} bytes)", flush=True)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--output", type=Path, default=ROOT / "data/demo")
    args = parser.parse_args()
    with httpx.Client(base_url=args.base_url, timeout=args.timeout) as client:
        demo(client, args.output, args.timeout)


if __name__ == "__main__":
    main()
