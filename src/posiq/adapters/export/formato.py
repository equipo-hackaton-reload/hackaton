"""Formato de cifras para el Word: solo presentación (redondeo, separadores, porcentaje, unidad).

No deriva cifras nuevas: cada número que se formatea aquí ya lo calculó `domain/`.
"""

from collections.abc import Callable

from posiq.domain.schemas import UnidadCifra

Formato = Callable[[float | None], str]

SIN_DATOS = "s. d."


# --- Formato (sin aritmética de negocio) ----------------------------------------------------------


def fmt_num(x: float | None, decimales: int = 1) -> str:
    """Número en formato español: `1.234,5`. None → «s. d.» (sin datos, nunca 0)."""
    if x is None:
        return SIN_DATOS
    texto = f"{x:,.{decimales}f}"
    return texto.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def fmt_pct(x: float | None) -> str:
    """Proporción 0-1 como porcentaje: `0.342` → `34,2 %`."""
    return SIN_DATOS if x is None else f"{fmt_num(x * 100, 1)} %"


def fmt_eur(x: float | None) -> str:
    return SIN_DATOS if x is None else f"{fmt_num(x, 0)} €"


def _sin_ceros(x: float, decimales: int) -> str:
    return fmt_num(x, decimales).rstrip("0").rstrip(",")


def fmt_cifra(x: float, unidad: UnidadCifra = "fraccion") -> str:
    """Cifra de un hallazgo según su `unidad`: `0.15` → `15,0 %`, `40.53` → `40,53 puntos`."""
    if unidad == "fraccion":
        return fmt_pct(x)
    if unidad == "eur":
        return fmt_eur(x)
    if unidad == "recuento":
        return fmt_num(x, 0)
    texto = _sin_ceros(x, 2)
    return f"{texto} punto" if texto == "1" else f"{texto} puntos"


def fmt_score(x: float | None) -> str:
    return fmt_num(x, 1)


def parrafos(texto: str) -> list[str]:
    return [p.strip() for p in texto.split("\n") if p.strip()]


def lista(items: list[str], sep: str = ", ") -> str:
    return sep.join(items) if items else "—"


def semanas(n: int) -> str:
    return f"{n} semana" if n == 1 else f"{n} semanas"


def fmt_pp(x: float | None) -> str:
    """Diferencia entre dos proporciones 0-1 en puntos porcentuales: `0.054` → `5,4 p. p.`."""
    return SIN_DATOS if x is None else f"{fmt_num(x * 100, 1)} p. p."


def fmt_rango(inf: float | None, sup: float | None, fmt: "Formato") -> str:
    """Rango ya calculado `[inf–sup]` con el formato de su valor."""
    if inf is None or sup is None:
        return SIN_DATOS
    return f"[{fmt(inf)}–{fmt(sup)}]"


def ordinal(n: int | None) -> str:
    """Puesto en un ranking: `8` → `8.ª` (la posición)."""
    return SIN_DATOS if n is None else f"{n}.ª"


def si_no(x: bool | None) -> str:
    return SIN_DATOS if x is None else ("Sí" if x else "No")
