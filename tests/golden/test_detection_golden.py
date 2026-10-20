"""Detección por reglas frente a las etiquetas humanas de `muestra_evaluada.csv` (133 filas)."""

from posiq.domain.detection import detect_in_run
from tests.golden.conftest import Kit

MIN_ACUERDO_APARECE = 0.9


def _agreement(kit: Kit) -> tuple[float, float]:
    runs = {r.id: r for r in kit.runs}
    aparece = posicion = 0
    for label in kit.sample:
        detection = detect_in_run(runs[label.run_id], kit.brands).get(label.brand_id)
        aparece += (detection is not None) == label.aparece
        posicion += (detection.posicion if detection else None) == label.posicion
    return aparece / len(kit.sample), posicion / len(kit.sample)


def test_muestra_completa(kit: Kit) -> None:
    assert len(kit.sample) == 133
    assert len({e.run_id for e in kit.sample}) == 15


def test_acuerdo_en_aparicion(kit: Kit) -> None:
    acuerdo, _ = _agreement(kit)
    print(f"acuerdo aparece = {acuerdo:.3f}")
    assert acuerdo >= MIN_ACUERDO_APARECE


def test_acuerdo_en_posicion(kit: Kit) -> None:
    _, acuerdo = _agreement(kit)
    print(f"acuerdo posicion = {acuerdo:.3f}")
    assert acuerdo >= MIN_ACUERDO_APARECE
