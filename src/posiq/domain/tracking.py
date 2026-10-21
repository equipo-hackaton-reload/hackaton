"""Seguimiento con método: serie temporal de las mediciones de una marca (ADR 0016). Puro.

posiq. no vende un score suelto: mide una línea base y la vuelve a medir con el mismo banco de
prompts y la misma versión de la metodología. Este módulo convierte varias mediciones (estudios)
de una marca en una `SerieMarca` y solo informa de los cambios que salen del margen de error.

- **Comparabilidad** (`comparabilidad`): dos mediciones consecutivas se comparan si coinciden la
  versión de la metodología, la del score, el juez (`juez_medicion`), el banco de prompts
  (`huella_banco`) y el conjunto de motores. Si cambia el modelo de un motor (`Run.modelo`), siguen
  siendo comparables, con un aviso. Si no lo son, se dicen los motivos y no se calcula ningún
  cambio entre ellas. Si cambia el conjunto de marcas del mercado (o su versión), el score y la
  aparición siguen siendo comparables, pero el puesto y la diferencia frente a los competidores no
  se calculan como cambio.
- **Núcleo común del banco:** si el banco crece o se recorta pero quedan preguntas comunes
  (`clave_pregunta`), el par se compara solo sobre ellas: se recalculan las métricas de cada
  medición con esas preguntas y los cambios llevan `sobre_nucleo_comun=True`. El score del banco
  completo se informa aparte (`PuntoSerie.score`) y no se compara.
- **Configuración versionada:** `version_perfil` y `version_mercado` de cada medición; la serie
  marca dónde cambian (`SerieMarca.cambios_configuracion`). La exactitud se verifica contra el
  perfil vigente en la fecha de la medición (`exactitud_con_perfil`, `vigente_en`).
- **Cambios** entre puntos consecutivos comparables:
  - Score de la marca: bootstrap independiente de cada estudio (`stats.significancia_remedicion`).
  - Aparición espontánea global y por motor: Newcombe (`stats.significancia_remedicion`).
  - Puesto en el ranking y diferencia frente a la media de los competidores: bootstrap
    independiente entre estudios y emparejado dentro de cada uno (las marcas de un estudio se
    evalúan en las mismas respuestas). Cada réplica recalcula el score de TODAS las marcas con la
    fórmula de `scoring` (`score_from_profile`) y de ahí el puesto y la diferencia.
  Un cambio es significativo si y solo si su IC al 95 % excluye 0, como en `stats`.
- **Indicadores adelantados** (se mueven antes que el score): % de citas a la web propia
  (`source_map.hallazgo_web_propia`), presencia en las 5 fuentes ganadas más citadas del mercado
  del estudio, inexactitudes y afirmaciones «a revisar por la clínica» (`accuracy`). None si la
  medición no trae los datos: nunca se inventa un valor.
- **Textos:** plantillas en español con coma decimal; ningún LLM interviene.
"""

import hashlib
import json
import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from statistics import fmean
from typing import Final, NamedTuple

from posiq.domain.accuracy import evaluar_exactitud
from posiq.domain.accuracy_schemas import AccionMitigacion, Afirmacion, HallazgoExactitud
from posiq.domain.metrics import compute_metrics
from posiq.domain.schemas import (
    Brand,
    Dimension,
    Market,
    Metrics,
    Motor,
    PromptInstance,
    Run,
    Source,
    Study,
    Trace,
)
from posiq.domain.scoring import (
    AppearanceProfile,
    appearance_quality,
    score_from_profile,
    spontaneous_population,
)
from posiq.domain.source_map import (
    WEBS_PROPIAS,
    DatosEstudio,
    _dominios,
    _marcas_por_run,
    _Resolver,
    hallazgo_web_propia,
    mapa_fuentes,
)
from posiq.domain.stats import (
    NIVEL,
    REPLICAS_BOOTSTRAP,
    SEMILLA_BOOTSTRAP,
    Muestra,
    _es,
    _limites_percentil,
    intervalo_score,
    significancia_remedicion,
)
from posiq.domain.stats_schemas import Intervalo, Significancia
from posiq.domain.tracking_schemas import (
    CambioConfiguracion,
    CambioSerie,
    IndicadorAdelantado,
    NucleoComun,
    PuntoSerie,
    QueCambia,
    SerieMarca,
    ValorIndicador,
    VersionMercado,
    VersionPerfil,
)

SIN_CAMBIOS: Final = "Sin cambios fuera del margen de error"
SIN_CAMBIOS_COMPARABLES: Final = f"{SIN_CAMBIOS} en lo que sí es comparable."
MOTIVO_LINEA_BASE: Final = "Línea base: es la primera medición de la serie."
RESUMEN_LINEA_BASE: Final = "Línea base: aún no hay con qué comparar."
RESUMEN_SIN_MEDICIONES: Final = "Sin mediciones: aún no hay con qué comparar."
NO_COMPARABLE: Final = "No comparable con la medición anterior"
SIN_DATOS_CAMBIOS: Final = "No hay datos para calcular cambios con la medición anterior."
MOTIVO_COMPETIDORES: Final = "Cambian los competidores del mercado"
MOTIVO_JUEZ: Final = "Cambia el juez"
MOTIVO_BANCO: Final = "Cambia el banco de prompts"
PREFIJO_JUEZ_TRAZA: Final = "judge:"
"""Las trazas del juez se llaman `judge:<proveedor>` (`adapters/judge/base.py`)."""
TOP_FUENTES_MERCADO: Final = 5
"""Fuentes ganadas más citadas del mercado del estudio para el indicador de presencia."""

METRICA_SCORE: Final = "score"
METRICA_POSICION: Final = "posicion"
METRICA_DIFERENCIA: Final = "diferencia_vs_competidores"
PREFIJO_APARICION: Final = "aparicion_espontanea:"


@dataclass(frozen=True)
class MedicionSerie:
    """Una medición de la marca: su estudio, sus métricas y la muestra con la que se calcularon.

    `market` y `catalogo` (opcionales) permiten los indicadores de fuentes; `exactitud` (opcional,
    de `accuracy.evaluar_exactitud` o `exactitud_con_perfil`), los de exactitud. Sin ellos, esos
    indicadores valen None.

    `juez` (opcional, «proveedor/modelo») declara quién evaluó; si falta, se deduce de `trazas` y
    de `Evaluation.origen` (`juez_medicion`). `version_perfil`/`version_mercado` (opcionales): la
    configuración de la marca vigente en la fecha de la medición.
    """

    study: Study
    metrics: Metrics
    muestra: Muestra
    market: Market | None = None
    catalogo: Sequence[Source] = field(default_factory=tuple)
    exactitud: HallazgoExactitud | None = None
    juez: str | None = None
    trazas: Sequence[Trace] = field(default_factory=tuple)
    version_perfil: str | None = None
    version_mercado: str | None = None


class Comparabilidad(NamedTuple):
    """`comparable`: el score y la aparición se comparan. `motivos_competidores` no vacío: cambió
    el mercado y el puesto y la diferencia frente a los competidores NO se comparan (solo se
    rellena si el par es comparable; si no, ya lo explican `motivos`). `avisos_banco` no vacío: el
    banco cambió y el par se compara sobre el núcleo común (`nucleo_comun`)."""

    comparable: bool
    motivos: list[str]
    avisos: list[str]
    motivos_competidores: list[str]
    avisos_banco: list[str] = []

    @property
    def nucleo_comun(self) -> bool:
        return self.comparable and bool(self.avisos_banco)

    @property
    def competidores_comparables(self) -> bool:
        return self.comparable and not self.motivos_competidores


# --- Formato --------------------------------------------------------------------------------------


def _num(x: float, decimales: int = 1) -> str:
    return _es(x, decimales)


def _signo(x: float, decimales: int = 1) -> str:
    """«+5,3», «−5,3» o «0,0» (coma decimal y menos tipográfico)."""
    texto = _es(x, decimales)
    return texto if texto.startswith("−") or not texto.strip("0,") else f"+{texto}"


def _pct(x: float) -> str:
    return f"{_num(x * 100)} %"


def _fecha(d: datetime) -> str:
    return d.strftime("%d/%m/%Y")


def _ic(s: Significancia, k: float = 1, decimales: int = 1, unidad: str = "") -> str:
    inf, sup = s.intervalo.inf * k, s.intervalo.sup * k
    return f"IC 95 % del cambio: [{_signo(inf, decimales)}; {_signo(sup, decimales)}]{unidad}"


def _conclusion(s: Significancia | None) -> str:
    if s is None:
        return "Sin contraste estadístico: no se puede decir si sale del margen de error."
    if s.significativa:
        return "Sale del margen de error."
    return "Está dentro del margen de error."


# --- Huella y comparabilidad ----------------------------------------------------------------------


def clave_pregunta(p: PromptInstance) -> str:
    """Clave estable de una pregunta entre mediciones: todo lo que se pregunta, sin el id.

    Plantilla, familia, fase, instanciación, perfil, ciudad, texto, marcas nombradas y prioridad,
    como JSON. Dos prompts de bancos distintos son «la misma pregunta» si y solo si coinciden en
    todo esto (el id de instancia cambia entre mediciones y no cuenta). Es la fila de
    `huella_banco` y la clave del núcleo común.
    """
    return json.dumps(
        [
            p.template_id,
            p.familia,
            p.fase_embudo,
            p.instanciacion,
            p.perfil,
            p.ciudad,
            p.texto,
            p.marca_nombrada,
            p.marca_nombrada_b,
            p.prioridad,
        ],
        ensure_ascii=False,
    )


def huella_banco(prompts: Iterable[PromptInstance]) -> str:
    """Huella determinista del banco de prompts (no depende del orden ni de los ids de instancia).

    Entra todo lo que cambia lo que se pregunta (`clave_pregunta`). `sha256:` + los 16 primeros
    hex.
    """
    filas = sorted(clave_pregunta(p) for p in prompts)
    digest = hashlib.sha256("\n".join(filas).encode("utf-8")).hexdigest()
    return f"sha256:{digest[:16]}"


def juez_medicion(med: MedicionSerie) -> str | None:
    """Quién evaluó las respuestas de la medición, para la comparabilidad.

    1. `med.juez` si se declara (p. ej. la API con el proveedor y modelo de `Settings`).
    2. Si no, las trazas del juez del estudio (`nodo` = `judge:<proveedor>`): «proveedor/modelo»,
       varios unidos con « + » (p. ej. un juez de consenso).
    3. Si no hay trazas, el origen de las evaluaciones: `jev` si alguna es de Jev; si no, `humano`
       (etiquetas del kit o revisión humana); si todas son `fallback`, `reglas`. Que una persona
       revise algunas evaluaciones del juez no cambia el juez de la medición.

    None si no hay evaluaciones ni nada declarado.
    """
    if med.juez:
        return med.juez
    de_trazas = sorted(
        {
            f"{t.nodo.removeprefix(PREFIJO_JUEZ_TRAZA)}/{t.modelo}"
            for t in med.trazas
            if t.nodo.startswith(PREFIJO_JUEZ_TRAZA) and t.study_id == med.study.id
        }
    )
    if de_trazas:
        return " + ".join(de_trazas)
    origenes = {e.origen for e in med.muestra.evaluations}
    if not origenes:
        return None
    if "jev" in origenes:
        return "jev"
    return "humano" if "humano" in origenes else "reglas"


def comparabilidad(
    anterior: PuntoSerie, actual: PuntoSerie, *, n_comunes: int = 0
) -> Comparabilidad:
    """Si `actual` se puede comparar con `anterior`, por qué no, y avisos que no lo impiden.

    `n_comunes`: preguntas comunes a los dos bancos (`clave_pregunta`). Si el banco cambia y hay
    alguna, el par se compara sobre ese núcleo común (aviso en `avisos_banco`) en vez de dejar de
    ser comparable.
    """
    motivos: list[str] = []
    if actual.version_metodologia != anterior.version_metodologia:
        motivos.append(
            f"Cambia la versión de la metodología ({anterior.version_metodologia} → "
            f"{actual.version_metodologia})."
        )
    if actual.score_version != anterior.score_version:
        motivos.append(
            f"Cambia la versión del score ({anterior.score_version} → {actual.score_version})."
        )
    if actual.juez and anterior.juez and actual.juez != anterior.juez:
        motivos.append(f"{MOTIVO_JUEZ} ({anterior.juez} → {actual.juez}).")
    avisos_banco: list[str] = []
    if actual.banco_prompts != anterior.banco_prompts:
        cambio = f"{MOTIVO_BANCO} ({anterior.banco_prompts} → {actual.banco_prompts})"
        if n_comunes > 0:
            preguntas = "pregunta común" if n_comunes == 1 else "preguntas comunes"
            avisos_banco.append(
                f"{cambio}. El score, la aparición y la posición se comparan sobre las "
                f"{n_comunes} {preguntas} a las dos mediciones (núcleo común); el banco completo "
                "se informa aparte, sin comparar."
            )
        else:
            motivos.append(f"{cambio}.")
    if set(actual.motores) != set(anterior.motores):
        motivos.append(
            f"Cambian los motores ({', '.join(anterior.motores) or 'ninguno'} → "
            f"{', '.join(actual.motores) or 'ninguno'})."
        )
    avisos: list[str] = []
    if bool(actual.juez) != bool(anterior.juez):
        avisos.append(
            "No consta el juez en una de las dos mediciones: no se puede comprobar si ha cambiado."
        )
    for motor in sorted(set(actual.motores) & set(anterior.motores)):
        antes, ahora = anterior.modelos_motor.get(motor), actual.modelos_motor.get(motor)
        if antes and ahora and antes != ahora:
            avisos.append(
                f"El modelo de {motor} cambia ({antes} → {ahora}): la serie sigue siendo "
                "comparable, pero parte del cambio puede deberse al modelo."
            )
        elif bool(antes) != bool(ahora):
            avisos.append(
                f"No consta el modelo de {motor} en una de las dos mediciones: no se puede "
                "comprobar si ha cambiado."
            )
    # Si el par no es comparable, nada se compara: el motivo de competidores (que dice que el score
    # y la aparición sí) sobraría y contradiría `comparable=False`.
    competidores = [] if motivos else _motivos_competidores(anterior, actual)
    return Comparabilidad(
        not motivos, motivos, avisos, competidores, [] if motivos else avisos_banco
    )


def _motivos_competidores(anterior: PuntoSerie, actual: PuntoSerie) -> list[str]:
    """Motivo si cambia el conjunto de marcas del mercado (vacío en un punto = no consta) o, con
    las mismas marcas, la versión del mercado (pueden cambiar alias o dominios de los rivales)."""
    antes, ahora = set(anterior.marcas_mercado), set(actual.marcas_mercado)
    va, vb = anterior.version_mercado, actual.version_mercado
    if antes and ahora and antes == ahora and va and vb and va != vb:
        return [
            f"{MOTIVO_COMPETIDORES}: cambia la versión del mercado ({va} → {vb}). El score y la "
            "aparición se comparan; el puesto y la diferencia frente a los competidores, no."
        ]
    if not antes or not ahora or antes == ahora:
        return []
    partes = []
    if entran := sorted(ahora - antes):
        partes.append(f"entran {', '.join(entran)}")
    if salen := sorted(antes - ahora):
        partes.append(f"salen {', '.join(salen)}")
    return [
        f"{MOTIVO_COMPETIDORES}: {'; '.join(partes)} ({len(antes)} → {len(ahora)} marcas). "
        "El score y la aparición se comparan; el puesto y la diferencia frente a los "
        "competidores, no."
    ]


# --- Mercado: scores de todas las marcas por ejecución --------------------------------------------

_Contribucion = tuple[bool, int, int, float]
"""(aparece, peso de posición, fuerza, calidad de la fuente) de una marca en una ejecución."""


@dataclass(frozen=True)
class _Mercado:
    foco: str
    brand_ids: tuple[str, ...]
    run_ids: tuple[str, ...]
    contrib: dict[str, dict[str, _Contribucion]]

    def scores(self, run_ids: Sequence[str]) -> dict[str, float | None]:
        out: dict[str, float | None] = {}
        for b in self.brand_ids:
            propias = self.contrib[b]
            elegidas = [propias[r] for r in run_ids if r in propias]
            if not elegidas:
                out[b] = None
                continue
            ap = [c for c in elegidas if c[0]]
            perfil = AppearanceProfile(
                tasa=len(ap) / len(elegidas),
                peso_medio=fmean(c[1] for c in ap) if ap else 0.0,
                fuerza_media=fmean(c[2] for c in ap) if ap else 0.0,
                calidad_media=fmean(c[3] for c in ap) if ap else 0.0,
            )
            out[b] = score_from_profile(b, len(elegidas), perfil).score
        return out

    def posicion_y_diferencia(self, run_ids: Sequence[str]) -> tuple[int | None, float | None]:
        return _posicion_y_diferencia(self.scores(run_ids), self.foco)


def _posicion_y_diferencia(
    scores: dict[str, float | None], foco: str
) -> tuple[int | None, float | None]:
    """Puesto de `foco` (mismo orden que `metrics._ranking`) y score − media de los demás."""
    propio = scores.get(foco)
    if propio is None:
        return None, None
    con = {b: s for b, s in scores.items() if s is not None}
    orden = sorted(con, key=lambda b: (-con[b], b))
    otros = [s for b, s in con.items() if b != foco]
    return orden.index(foco) + 1, (propio - fmean(otros) if otros else None)


def _mercado(medicion: MedicionSerie) -> _Mercado:
    m, muestra = medicion.metrics, medicion.muestra
    contrib: dict[str, dict[str, _Contribucion]] = {}
    runs: set[str] = set()
    for b in m.ranking:
        propias: dict[str, _Contribucion] = {}
        for e, r in spontaneous_population(muestra.evaluations, muestra.runs, muestra.prompts, b):
            if r.id in propias:
                raise ValueError(f"más de una evaluación de {b} en la ejecución {r.id}")
            propias[r.id] = (e.aparece, e.peso_posicion, e.fuerza, appearance_quality(e, r))
        contrib[b] = propias
        runs |= propias.keys()
    return _Mercado(m.marca_foco_id, tuple(m.ranking), tuple(sorted(runs)), contrib)


def _significancia_bootstrap(
    delta: float, valores: list[float], n: int, nivel: float, digits: int
) -> Significancia | None:
    if not valores:
        return None
    inf, sup = _limites_percentil(sorted(valores), nivel)
    inf, sup = min(round(inf, digits), delta), max(round(sup, digits), delta)
    intervalo = Intervalo(valor=delta, inf=inf, sup=sup, n=n, nivel=nivel, metodo="bootstrap")
    return Significancia(delta=delta, intervalo=intervalo, significativa=not inf <= 0 <= sup)


def _bootstrap_mercado(
    antes: _Mercado, ahora: _Mercado, replicas: int, semilla: int
) -> tuple[list[float], list[float]]:
    """Réplicas de (Δ puesto, Δ diferencia frente a competidores), estudios independientes."""
    rng = random.Random(semilla)
    d_pos: list[float] = []
    d_dif: list[float] = []
    for _ in range(replicas):
        ids_a = rng.choices(antes.run_ids, k=len(antes.run_ids)) if antes.run_ids else []
        ids_b = rng.choices(ahora.run_ids, k=len(ahora.run_ids)) if ahora.run_ids else []
        pa, da = antes.posicion_y_diferencia(ids_a)
        pb, db = ahora.posicion_y_diferencia(ids_b)
        if pa is not None and pb is not None:
            d_pos.append(pb - pa)
        if da is not None and db is not None:
            d_dif.append(db - da)
    return d_pos, d_dif


# --- Puntos ---------------------------------------------------------------------------------------


def _validar(brand_id: str, med: MedicionSerie) -> None:
    s, m, mu = med.study, med.metrics, med.muestra
    if s.brand_id != brand_id:
        raise ValueError(f"el estudio {s.id} es de la marca {s.brand_id}, no de {brand_id}")
    if m.study_id != s.id:
        raise ValueError(f"las métricas son del estudio {m.study_id}, no de {s.id}")
    ajenos = sorted(({r.study_id for r in mu.runs} | {e.study_id for e in mu.evaluations}) - {s.id})
    if ajenos:
        raise ValueError(f"la muestra del estudio {s.id} trae datos de otros estudios: {ajenos}")
    if med.exactitud is not None and med.exactitud.study_id != s.id:
        raise ValueError(f"la exactitud es del estudio {med.exactitud.study_id}, no de {s.id}")


def _modelos(med: MedicionSerie) -> tuple[dict[Motor, str], list[str]]:
    por_motor: dict[Motor, set[str]] = {}
    for r in med.muestra.runs:
        if r.modelo:
            por_motor.setdefault(r.motor, set()).add(r.modelo)
    avisos = [
        f"{motor} responde con varios modelos en esta medición ({', '.join(sorted(ms))})."
        for motor, ms in sorted(por_motor.items())
        if len(ms) > 1
    ]
    return {motor: " + ".join(sorted(ms)) for motor, ms in sorted(por_motor.items())}, avisos


def _punto(
    med: MedicionSerie, mercado: _Mercado, replicas: int, semilla: int, nivel: float
) -> PuntoSerie:
    m = med.metrics
    foco = m.marca_foco_id
    score = m.score_global.score
    scores = {s.brand_id: s.score for s in m.scores}
    posicion, _ = _posicion_y_diferencia(scores, foco)
    otros = [s for b, s in scores.items() if b != foco and s is not None]
    media = round(fmean(otros), 2) if otros else None
    diferencia = round(score - fmean(otros), 2) if score is not None and otros else None
    recalculado = mercado.scores(mercado.run_ids).get(foco)
    if (recalculado is None) != (score is None) or (
        recalculado is not None and score is not None and abs(recalculado - score) > 0.01
    ):
        raise ValueError(
            f"la muestra del estudio {m.study_id} da score {recalculado}, pero las métricas "
            f"dicen {score}"
        )
    modelos, avisos = _modelos(med)
    if med.study.score_version != m.score_version:
        avisos.append(
            f"El estudio declara la versión del score {med.study.score_version}, pero las "
            f"métricas se calcularon con la {m.score_version}."
        )
    return PuntoSerie(
        study_id=med.study.id,
        fecha=med.study.creado_en,
        score=score,
        intervalo=intervalo_score(
            med.muestra, foco, replicas=replicas, semilla=semilla, nivel=nivel
        )
        if score is not None
        else None,
        posicion=posicion,
        n_marcas=len(m.ranking),
        score_medio_competidores=media,
        diferencia_vs_competidores=diferencia,
        version_metodologia=med.study.version_metodologia,
        score_version=m.score_version,
        banco_prompts=huella_banco(med.muestra.prompts),
        motores=sorted({r.motor for r in med.muestra.runs}),
        modelos_motor=modelos,
        comparable_con_anterior=False,
        motivos_no_comparable=[MOTIVO_LINEA_BASE],
        avisos=avisos,
        marcas_mercado=sorted(m.ranking),
        juez=juez_medicion(med),
        version_perfil=med.version_perfil,
        version_mercado=med.version_mercado,
    )


# --- Cambios --------------------------------------------------------------------------------------


def _periodo(a: PuntoSerie, b: PuntoSerie) -> str:
    return f"Del {_fecha(a.fecha)} al {_fecha(b.fecha)}"


def _verbo(delta: float, decimales: int = 1) -> str:
    if round(delta, decimales) > 0:
        return "sube"
    return "baja" if round(delta, decimales) < 0 else "se mantiene"


def _cambio_score(
    periodo: str, a: PuntoSerie, b: PuntoSerie, s: Significancia | None
) -> CambioSerie | None:
    if s is None or a.score is None or b.score is None:
        return None
    verbo = _verbo(s.delta, 1)
    tramo = (
        f"se mantiene en {_num(b.score)}"
        if verbo == "se mantiene"
        else f"{verbo} de {_num(a.score)} a {_num(b.score)}"
    )
    texto = (
        f"{periodo}: el Score de Citación {tramo} ({_signo(s.delta)} puntos; {_ic(s)}). "
        f"{_conclusion(s)}"
    )
    return CambioSerie(
        desde_study_id=a.study_id,
        hasta_study_id=b.study_id,
        metrica=METRICA_SCORE,
        delta=s.delta,
        significancia=s,
        significativo=s.significativa,
        texto=texto,
    )


def _cambios_aparicion(
    periodo: str,
    a: PuntoSerie,
    b: PuntoSerie,
    anterior: Metrics,
    actual: Metrics,
    tasas: dict[str, Significancia],
) -> list[CambioSerie]:
    foco = actual.marca_foco_id
    out: list[CambioSerie] = []
    valores = ["global", *b.motores]
    for valor in valores:
        dimension: Dimension = "global" if valor == "global" else "motor"
        s = tasas.get(f"espontaneo:{dimension}:{valor}")
        ca = anterior.cell(foco, "espontaneo", dimension, valor)
        cb = actual.cell(foco, "espontaneo", dimension, valor)
        if s is None or ca is None or cb is None or ca.tasa is None or cb.tasa is None:
            continue
        donde = "" if valor == "global" else f" en {valor}"
        verbo = _verbo(s.delta * 100, 1)
        tramo = (
            f"se mantiene en el {_pct(cb.tasa)}"
            if verbo == "se mantiene"
            else f"{verbo} del {_pct(ca.tasa)} al {_pct(cb.tasa)}"
        )
        texto = (
            f"{periodo}: la aparición espontánea{donde} {tramo} ({_signo(s.delta * 100)} pp; "
            f"{_ic(s, k=100, unidad=' pp')}). {_conclusion(s)}"
        )
        out.append(
            CambioSerie(
                desde_study_id=a.study_id,
                hasta_study_id=b.study_id,
                metrica=f"{PREFIJO_APARICION}{valor}",
                delta=s.delta,
                significancia=s,
                significativo=s.significativa,
                texto=texto,
            )
        )
    return out


def _cambio_posicion(
    periodo: str, a: PuntoSerie, b: PuntoSerie, s: Significancia | None
) -> CambioSerie | None:
    if a.posicion is None or b.posicion is None:
        return None
    delta = float(b.posicion - a.posicion)
    if delta == 0:
        movimiento = "mantiene el puesto"
    else:
        k = abs(int(delta))
        sentido = "gana" if delta < 0 else "pierde"
        movimiento = f"{sentido} {k} {'puesto' if k == 1 else 'puestos'}"
    detalle = f"; {_ic(s, decimales=0)}" if s is not None else ""
    tramo = (
        f"se mantiene en el {b.posicion}.º puesto de {b.n_marcas}"
        if delta == 0
        else f"pasa del {a.posicion}.º al {b.posicion}.º puesto de {b.n_marcas}"
    )
    texto = f"{periodo}: la marca {tramo} ({movimiento}{detalle}). {_conclusion(s)}"
    return CambioSerie(
        desde_study_id=a.study_id,
        hasta_study_id=b.study_id,
        metrica=METRICA_POSICION,
        delta=s.delta if s is not None else delta,
        significancia=s,
        significativo=s.significativa if s is not None else False,
        relativo_a_competidores=True,
        texto=texto,
    )


def _cambio_diferencia(
    periodo: str, a: PuntoSerie, b: PuntoSerie, s: Significancia | None
) -> CambioSerie | None:
    if a.diferencia_vs_competidores is None or b.diferencia_vs_competidores is None:
        return None
    delta = round(b.diferencia_vs_competidores - a.diferencia_vs_competidores, 2)
    detalle = f"; {_ic(s)}" if s is not None else ""
    tramo = (
        f"se mantiene en {_signo(b.diferencia_vs_competidores)} puntos"
        if round(delta, 1) == 0
        else f"pasa de {_signo(a.diferencia_vs_competidores)} a "
        f"{_signo(b.diferencia_vs_competidores)} puntos"
    )
    texto = (
        f"{periodo}: frente a la media de sus competidores, la marca {tramo} "
        f"({_signo(delta)} puntos{detalle}). {_conclusion(s)}"
    )
    return CambioSerie(
        desde_study_id=a.study_id,
        hasta_study_id=b.study_id,
        metrica=METRICA_DIFERENCIA,
        delta=s.delta if s is not None else delta,
        significancia=s,
        significativo=s.significativa if s is not None else False,
        relativo_a_competidores=True,
        texto=texto,
    )


def _cambios(
    a: PuntoSerie,
    b: PuntoSerie,
    med_a: MedicionSerie,
    med_b: MedicionSerie,
    merc_a: _Mercado,
    merc_b: _Mercado,
    replicas: int,
    semilla: int,
    nivel: float,
    *,
    competidores: bool = True,
    etiqueta: str = "",
) -> list[CambioSerie]:
    """Cambios entre dos puntos comparables. Sin `competidores` (cambió el mercado), no se
    calculan el puesto ni la diferencia frente a los competidores. `etiqueta` se añade al periodo
    del texto (p. ej. « (núcleo común de 12 preguntas)»)."""
    periodo = f"{_periodo(a, b)}{etiqueta}"
    rem = significancia_remedicion(
        med_b.metrics,
        med_a.metrics,
        med_b.muestra,
        med_a.muestra,
        replicas=replicas,
        semilla=semilla,
        nivel=nivel,
    )
    tasas = rem.por_clave()
    propios = [
        _cambio_score(periodo, a, b, rem.score),
        *_cambios_aparicion(periodo, a, b, med_a.metrics, med_b.metrics, tasas),
    ]
    if not competidores:
        return [c for c in propios if c is not None]
    d_pos, d_dif = _bootstrap_mercado(merc_a, merc_b, replicas, semilla)
    n = len(merc_a.run_ids) + len(merc_b.run_ids)
    s_pos = (
        _significancia_bootstrap(float(b.posicion - a.posicion), d_pos, n, nivel, 2)
        if a.posicion is not None and b.posicion is not None
        else None
    )
    s_dif = (
        _significancia_bootstrap(
            round(b.diferencia_vs_competidores - a.diferencia_vs_competidores, 2),
            d_dif,
            n,
            nivel,
            2,
        )
        if a.diferencia_vs_competidores is not None and b.diferencia_vs_competidores is not None
        else None
    )
    candidatos = [
        *propios,
        _cambio_posicion(periodo, a, b, s_pos),
        _cambio_diferencia(periodo, a, b, s_dif),
    ]
    return [c for c in candidatos if c is not None]


# --- Indicadores adelantados ----------------------------------------------------------------------


def _datos_estudio(med: MedicionSerie) -> DatosEstudio | None:
    if med.market is None:
        return None
    mu = med.muestra
    return DatosEstudio(med.market, mu.prompts, mu.runs, mu.evaluations)


def cuota_web_propia(med: MedicionSerie) -> float | None:
    """Fracción de las citas que van a la web propia de la marca (`hallazgo_web_propia`)."""
    estudio = _datos_estudio(med)
    if estudio is None or not med.muestra.runs:
        return None
    hallazgo = hallazgo_web_propia(estudio, med.metrics.marca_foco_id, med.catalogo)
    return hallazgo.cifra if hallazgo is not None else None


def presencia_top_fuentes(med: MedicionSerie, top: int = TOP_FUENTES_MERCADO) -> float | None:
    """Fracción de las respuestas en las que aparece la marca que citan al menos una de las `top`
    fuentes ganadas más citadas del mercado del estudio (sin la entrada agregada de webs propias).

    None si no hay mercado, si el mapa no tiene fuentes ganadas o si la marca no aparece.
    """
    estudio = _datos_estudio(med)
    if estudio is None or not med.muestra.runs:
        return None
    mapa = mapa_fuentes(med.study.brief.sector, [estudio], med.catalogo)
    objetivo = {
        f.dominio for f in mapa.fuentes if f.dominio != WEBS_PROPIAS and f.propiedad == "ganado"
    }
    principales = [f.dominio for f in mapa.fuentes if f.dominio in objetivo][:top]
    if not principales:
        return None
    resolver = _Resolver(med.catalogo, estudio.market.marcas)
    foco = med.metrics.marca_foco_id
    marcas_run = _marcas_por_run(estudio)
    runs = [r for r in estudio.runs if foco in marcas_run.get(r.id, set())]
    if not runs:
        return None
    con = sum(any(resolver.clave(s) in principales for s in _dominios(r)) for r in runs)
    return round(con / len(runs), 4)


def _indicadores(puntos: list[PuntoSerie], meds: list[MedicionSerie]) -> list[IndicadorAdelantado]:
    def serie(valores: list[float | None]) -> list[ValorIndicador]:
        return [
            ValorIndicador(study_id=p.study_id, valor=v)
            for p, v in zip(puntos, valores, strict=True)
        ]

    return [
        IndicadorAdelantado(
            clave="cuota_web_propia",
            nombre="Citas a la web propia",
            unidad="fraccion",
            valores=serie([cuota_web_propia(m) for m in meds]),
        ),
        IndicadorAdelantado(
            clave="presencia_top_fuentes",
            nombre=f"Presencia en las {TOP_FUENTES_MERCADO} fuentes más citadas del mercado",
            unidad="fraccion",
            valores=serie([presencia_top_fuentes(m) for m in meds]),
        ),
        IndicadorAdelantado(
            clave="inexactitudes",
            nombre="Inexactitudes sobre la marca",
            unidad="recuento",
            valores=serie(
                [float(m.exactitud.n_incorrectas) if m.exactitud else None for m in meds]
            ),
        ),
        IndicadorAdelantado(
            clave="a_revisar",
            nombre="Afirmaciones a revisar por la clínica",
            unidad="recuento",
            valores=serie(
                [float(m.exactitud.n_riesgo_regulatorio) if m.exactitud else None for m in meds]
            ),
        ),
    ]


# --- Núcleo común del banco -----------------------------------------------------------------------


def _claves_comunes(anterior: MedicionSerie, actual: MedicionSerie) -> set[str]:
    """Claves de las preguntas que están en los dos bancos (`clave_pregunta`)."""
    antes = {clave_pregunta(p) for p in anterior.muestra.prompts}
    return antes & {clave_pregunta(p) for p in actual.muestra.prompts}


def _etiqueta_nucleo(n: int) -> str:
    return f" (núcleo común de {n} {'pregunta' if n == 1 else 'preguntas'})"


def _mercado_metricas(med: MedicionSerie) -> Market:
    """Mercado con el que recalcular las métricas: el de la medición si cuadra con su ranking; si
    no, uno mínimo con los brand_ids del ranking (la foco con el nombre del brief)."""
    m = med.metrics
    if med.market is not None and {b.id for b in med.market.marcas} == set(m.ranking):
        return med.market
    return Market(
        marcas=[
            Brand(
                id=b,
                nombre=med.study.brief.marca if b == m.marca_foco_id else b,
                rol="foco" if b == m.marca_foco_id else "lider" if b == m.lider_id else "contexto",
            )
            for b in m.ranking
        ]
    )


def restringir_a_preguntas(med: MedicionSerie, claves: set[str]) -> MedicionSerie:
    """La medición con solo las preguntas de `claves` y sus métricas recalculadas (`metrics`)."""
    prompts = [p for p in med.muestra.prompts if clave_pregunta(p) in claves]
    ids = {p.id for p in prompts}
    runs = [r for r in med.muestra.runs if r.prompt_id in ids]
    run_ids = {r.id for r in runs}
    evals = [e for e in med.muestra.evaluations if e.run_id in run_ids]
    metrics = compute_metrics(
        med.study.brief,
        _mercado_metricas(med),
        prompts,
        runs,
        evals,
        list(med.catalogo),
        study_id=med.study.id,
    )
    return replace(med, metrics=metrics, muestra=Muestra(evals, runs, prompts))


@dataclass(frozen=True)
class _ParNucleo:
    med_anterior: MedicionSerie
    med_actual: MedicionSerie
    anterior: PuntoSerie
    actual: PuntoSerie
    nucleo: NucleoComun


def _par_nucleo(
    med_a: MedicionSerie,
    med_b: MedicionSerie,
    comunes: set[str],
    replicas: int,
    semilla: int,
    nivel: float,
) -> _ParNucleo:
    ca, cb = restringir_a_preguntas(med_a, comunes), restringir_a_preguntas(med_b, comunes)
    pa = _punto(ca, _mercado(ca), replicas, semilla, nivel)
    pb = _punto(cb, _mercado(cb), replicas, semilla, nivel)
    nucleo = NucleoComun(
        huella=huella_banco(cb.muestra.prompts),
        n_prompts_comunes=len(comunes),
        n_prompts_anterior=len({clave_pregunta(p) for p in med_a.muestra.prompts}),
        n_prompts_actual=len({clave_pregunta(p) for p in med_b.muestra.prompts}),
        score_anterior=pa.score,
        score_actual=pb.score,
    )
    return _ParNucleo(ca, cb, pa, pb, nucleo)


# --- Configuración versionada ---------------------------------------------------------------------


def _cambio_configuracion(anterior: PuntoSerie, actual: PuntoSerie) -> CambioConfiguracion | None:
    """Marca del gráfico si cambia la versión del perfil o del mercado (ambas deben constar)."""
    que: list[QueCambia] = []
    partes: list[str] = []
    if anterior.version_perfil and actual.version_perfil:
        if anterior.version_perfil != actual.version_perfil:
            que.append("perfil")
            partes.append(
                f"el perfil de la marca ({anterior.version_perfil} → {actual.version_perfil}; "
                "no afecta al score)"
            )
    if anterior.version_mercado and actual.version_mercado:
        if anterior.version_mercado != actual.version_mercado:
            que.append("mercado")
            partes.append(
                f"el mercado ({anterior.version_mercado} → {actual.version_mercado}; el puesto y "
                "la diferencia frente a los competidores no se comparan)"
            )
    if not que:
        return None
    texto = f"Desde el {_fecha(actual.fecha)} cambia {' y '.join(partes)}."
    return CambioConfiguracion(study_id=actual.study_id, que_cambia=que, texto=texto)


def vigente_en[V: (VersionPerfil, VersionMercado)](
    versiones: Sequence[V], fecha: datetime
) -> V | None:
    """La versión vigente en `fecha`: la de `vigente_desde` más reciente que no sea posterior.

    None si ninguna estaba vigente. Lanza `ValueError` si dos versiones empiezan a la vez.
    """
    inicios = [v.vigente_desde for v in versiones]
    if len(inicios) != len(set(inicios)):
        raise ValueError("dos versiones de la configuración empiezan en la misma fecha")
    candidatas = [v for v in versiones if v.vigente_desde <= fecha]
    return max(candidatas, key=lambda v: v.vigente_desde) if candidatas else None


def exactitud_con_perfil(
    study: Study,
    brand: Brand,
    version: VersionPerfil,
    runs: Sequence[Run],
    *,
    marcas: Iterable[Brand] = (),
    ciudades: Iterable[str] = (),
    afirmaciones_llm: Sequence[Afirmacion] = (),
) -> tuple[HallazgoExactitud, list[AccionMitigacion]]:
    """Exactitud de la medición `study` verificada contra el perfil `version`, que debe ser el
    vigente en la fecha de la medición (no el actual): una afirmación correcta en marzo no pasa a
    ser inexacta porque el perfil cambie en junio. Lanza `ValueError` si la versión es posterior
    a la medición."""
    if version.vigente_desde > study.creado_en:
        raise ValueError(
            f"el perfil {version.version} es posterior a la medición {study.id} "
            f"({_fecha(version.vigente_desde)} > {_fecha(study.creado_en)})"
        )
    return evaluar_exactitud(
        study.id,
        brand,
        version.perfil,
        runs,
        marcas=marcas,
        ciudades=ciudades,
        afirmaciones_llm=afirmaciones_llm,
    )


def exactitud_en_fecha(
    study: Study,
    brand: Brand,
    versiones: Sequence[VersionPerfil],
    runs: Sequence[Run],
    *,
    marcas: Iterable[Brand] = (),
    ciudades: Iterable[str] = (),
    afirmaciones_llm: Sequence[Afirmacion] = (),
) -> tuple[HallazgoExactitud, list[AccionMitigacion]]:
    """`exactitud_con_perfil` con la versión del perfil vigente en `study.creado_en`."""
    version = vigente_en(versiones, study.creado_en)
    if version is None:
        raise ValueError(f"no hay perfil vigente en la fecha de la medición {study.id}")
    return exactitud_con_perfil(
        study,
        brand,
        version,
        runs,
        marcas=marcas,
        ciudades=ciudades,
        afirmaciones_llm=afirmaciones_llm,
    )


# --- Serie ----------------------------------------------------------------------------------------


def construir_serie(
    brand_id: str,
    nombre: str,
    mediciones: Sequence[MedicionSerie],
    *,
    replicas: int = REPLICAS_BOOTSTRAP,
    semilla: int = SEMILLA_BOOTSTRAP,
    nivel: float = NIVEL,
) -> SerieMarca:
    """Serie temporal de `brand_id` a partir de sus mediciones (en cualquier orden).

    Ordena por fecha (y `study_id` en empates), calcula cada punto, decide la comparabilidad con el
    anterior, los cambios entre consecutivos comparables y los indicadores adelantados. Lanza
    `ValueError` si una medición es de otra marca, mezcla estudios o se repite.
    """
    ids = [m.study.id for m in mediciones]
    repetidos = sorted({i for i in ids if ids.count(i) > 1})
    if repetidos:
        raise ValueError(f"estudios repetidos en la serie: {repetidos}")
    for med in mediciones:
        _validar(brand_id, med)
    meds = sorted(mediciones, key=lambda m: (m.study.creado_en, m.study.id))
    mercados = [_mercado(m) for m in meds]
    puntos: list[PuntoSerie] = []
    cambios: list[CambioSerie] = []
    configuracion: list[CambioConfiguracion] = []
    lineas: list[str] = []
    for i, (med, mercado) in enumerate(zip(meds, mercados, strict=True)):
        punto = _punto(med, mercado, replicas, semilla, nivel)
        if puntos:
            anterior = puntos[-1]
            comunes = _claves_comunes(meds[i - 1], med)
            comp = comparabilidad(anterior, punto, n_comunes=len(comunes))
            par = (
                _par_nucleo(meds[i - 1], med, comunes, replicas, semilla, nivel)
                if comp.nucleo_comun
                else None
            )
            punto = punto.model_copy(
                update={
                    "comparable_con_anterior": comp.comparable,
                    "motivos_no_comparable": comp.motivos,
                    "avisos": [
                        *punto.avisos,
                        *comp.avisos,
                        *comp.avisos_banco,
                        *comp.motivos_competidores,
                    ],
                    "competidores_comparables": comp.competidores_comparables,
                    "nucleo_comun": par.nucleo if par is not None else None,
                }
            )
            if cambio_config := _cambio_configuracion(anterior, punto):
                configuracion.append(cambio_config)
            periodo = _periodo(anterior, punto)
            if not comp.comparable:
                lineas.append(f"{periodo}: {NO_COMPARABLE.lower()}: {' '.join(comp.motivos)}")
            else:
                lineas += [f"{periodo}: {m}" for m in comp.avisos_banco]
                lineas += [f"{periodo}: {m}" for m in comp.motivos_competidores]
                if par is not None:
                    del_par = [
                        c.model_copy(update={"sobre_nucleo_comun": True})
                        for c in _cambios(
                            par.anterior,
                            par.actual,
                            par.med_anterior,
                            par.med_actual,
                            _mercado(par.med_anterior),
                            _mercado(par.med_actual),
                            replicas,
                            semilla,
                            nivel,
                            competidores=comp.competidores_comparables,
                            etiqueta=_etiqueta_nucleo(len(comunes)),
                        )
                    ]
                else:
                    del_par = _cambios(
                        anterior,
                        punto,
                        meds[i - 1],
                        med,
                        mercados[i - 1],
                        mercado,
                        replicas,
                        semilla,
                        nivel,
                        competidores=comp.competidores_comparables,
                    )
                if not del_par:
                    lineas.append(f"{periodo}: {SIN_DATOS_CAMBIOS}")
                lineas += [c.texto for c in del_par if c.significativo]
                cambios += del_par
        puntos.append(punto)
    significativos = [c for c in cambios if c.significativo]
    return SerieMarca(
        brand_id=brand_id,
        nombre=nombre,
        puntos=puntos,
        cambios=cambios,
        cambios_significativos=significativos,
        indicadores=_indicadores(puntos, meds),
        resumen=_resumen(puntos, cambios, lineas),
        cambios_configuracion=configuracion,
    )


def _resumen(puntos: list[PuntoSerie], cambios: list[CambioSerie], lineas: list[str]) -> list[str]:
    """Distingue la línea base, lo no comparable y «sin cambios» (solo si se calculó alguno)."""
    if not puntos:
        return [RESUMEN_SIN_MEDICIONES]
    if len(puntos) == 1:
        return [RESUMEN_LINEA_BASE]
    if not cambios or any(c.significativo for c in cambios):
        return lineas
    return [*lineas, SIN_CAMBIOS_COMPARABLES] if lineas else [SIN_CAMBIOS]
