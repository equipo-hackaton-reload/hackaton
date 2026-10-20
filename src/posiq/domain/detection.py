"""Detección de marcas por reglas en el texto de una respuesta.

Reglas (metodología §6 y doc 07 N1.3):
- Se compara sin acentos ni mayúsculas, con el nombre completo y todos los alias.
- Una coincidencia exige límite de palabra: no puede ir pegada a una letra o dígito.
- Los alias de menos de 4 caracteres exigen límite estricto: tampoco pueden ir pegados a
  `-`, `.`, `_`, `/`, `@` ni apóstrofo (evita casar siglas dentro de dominios o códigos).
- Las coincidencias solapadas cuentan una sola vez: gana la que empieza antes y, a igualdad, la
  más larga («Clínica Alborada Visión» absorbe a «Alborada Visión» y a «Alborada»).
- `posicion` es el orden de primera aparición entre las marcas detectadas (1 = la primera).
"""

import re
from dataclasses import dataclass

from posiq.domain.schemas import Brand, Detection, Evaluation, Run
from posiq.domain.text import fold, fold_with_map

STRICT_MIN_LEN = 4
_WORD = r"\w"
_STRICT = r"[\w\-._/@'’]"


@dataclass(frozen=True)
class _Match:
    start: int
    end: int
    brand_id: str


def _pattern(name: str) -> re.Pattern[str]:
    folded = re.escape(fold(name.strip()))
    edge = _STRICT if len(name.strip()) < STRICT_MIN_LEN else _WORD
    return re.compile(f"(?<!{edge}){folded}(?!{edge})")


def _matches(folded: str, brands: list[Brand]) -> list[_Match]:
    found: list[_Match] = []
    for brand in brands:
        for name in {brand.nombre, *brand.aliases}:
            if name.strip():
                found.extend(
                    _Match(m.start(), m.end(), brand.id) for m in _pattern(name).finditer(folded)
                )
    found.sort(key=lambda m: (m.start, -(m.end - m.start)))
    kept: list[_Match] = []
    for match in found:
        if not kept or match.start >= kept[-1].end:
            kept.append(match)
    return kept


def detect_brands(text: str, brands: list[Brand]) -> list[Detection]:
    """Marcas presentes en `text`, ordenadas por posición. Las ausentes no aparecen en la lista."""
    folded, index = fold_with_map(text)
    first: dict[str, _Match] = {}
    counts: dict[str, int] = {}
    for match in _matches(folded, brands):
        first.setdefault(match.brand_id, match)
        counts[match.brand_id] = counts.get(match.brand_id, 0) + 1
    ordered = sorted(first.values(), key=lambda m: m.start)
    return [
        Detection(
            brand_id=m.brand_id,
            posicion=pos,
            span=(index[m.start], index[m.end - 1] + 1),
            menciones=counts[m.brand_id],
        )
        for pos, m in enumerate(ordered, start=1)
    ]


def detect_in_run(run: Run, brands: list[Brand]) -> dict[str, Detection]:
    """Detección sobre una ejecución, solo entre sus marcas a evaluar. Clave: brand_id."""
    eligibles = [b for b in brands if b.id in run.marcas_a_evaluar]
    return {d.brand_id: d for d in detect_brands(run.texto_respuesta, eligibles)}


def evaluation_from_detection(
    run: Run, brand: Brand, detection: Detection | None, confianza: float = 0.3
) -> Evaluation:
    """Evaluación mínima solo con reglas (sin juez): aparición y posición.

    Si aparece, fuerza 1 (mención neutra) y tipo de mención, sentimiento y tipo de fuente sin
    resolver. Sirve de suelo cuando no hay juez; `origen` = `fallback`.
    """
    return Evaluation(
        id=f"{run.id}:{brand.id}",
        study_id=run.study_id,
        run_id=run.id,
        brand_id=brand.id,
        aparece=detection is not None,
        posicion=detection.posicion if detection else None,
        fuerza=1 if detection else 0,
        tipo_fuente=None if detection and run.fuentes else ("Sin fuente" if detection else None),
        confianza=confianza,
        origen="fallback",
    )
