"""Motor simulado sobre `ejecuciones.csv` del kit: responde con la ejecución ya grabada.

Hay un `KitEngine` por motor del kit (ChatGPT, Gemini, Perplexity, Claude), para que la
orquestación trate los cuatro como `Engine` distintos. Los CSV se leen una sola vez por carpeta y
los comparten todas las instancias.
"""

from functools import lru_cache
from pathlib import Path

from posiq.domain import kit_loader as kl
from posiq.domain.schemas import Motor, PromptInstance, Run
from posiq.settings import Settings

KIT_MOTORES: tuple[Motor, ...] = ("ChatGPT", "Gemini", "Perplexity", "Claude")
_LOAD_STUDY = "kit"


class KitMissError(LookupError):
    """El kit no tiene ejecución para ese prompt, motor y repetición."""

    def __init__(self, prompt_id: str, motor: Motor, repeticion: int) -> None:
        super().__init__(
            f"el kit no tiene ejecución para prompt_id={prompt_id}, motor={motor}, "
            f"repetición={repeticion}"
        )
        self.prompt_id = prompt_id


@lru_cache(maxsize=4)
def _load_runs(kit_dir: str) -> dict[tuple[str, Motor, int], Run]:
    path = Path(kit_dir)
    brands = kl.load_brands(path / "marcas.csv")
    sources = kl.load_sources(path / "fuentes_catalogo.csv")
    runs = kl.load_runs(path / "ejecuciones.csv", brands, sources, _LOAD_STUDY)
    return {(r.prompt_id, r.motor, r.repeticion): r for r in runs}


class KitEngine:
    """`ports.Engine` que devuelve la `Run` del kit con el `study_id` del estudio en curso."""

    def __init__(self, kit_dir: str | Path, motor: Motor, *, name: str | None = None) -> None:
        self.kit_dir = str(Path(kit_dir).resolve())
        self.motor: Motor = motor
        self.name = name or f"kit:{motor}"

    @classmethod
    def all_motors(cls, kit_dir: str | Path) -> list["KitEngine"]:
        """Un motor del kit por cada motor grabado (ChatGPT, Gemini, Perplexity, Claude)."""
        return [cls(kit_dir, motor) for motor in KIT_MOTORES]

    @classmethod
    def from_settings(cls, settings: Settings) -> list["KitEngine"]:
        return cls.all_motors(settings.kit_dir)

    def ask(self, prompt: PromptInstance, *, repeticion: int, study_id: str) -> Run:
        run = _load_runs(self.kit_dir).get((prompt.id, self.motor, repeticion))
        if run is None:
            raise KitMissError(prompt.id, self.motor, repeticion)
        return run.model_copy(update={"study_id": study_id, "origen": "kit"})
