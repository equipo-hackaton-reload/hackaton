"""Mapa de fuentes del sector y oportunidades de fuente por marca (ADR 0010). Puro y determinista.

Todo sale de `Run.fuentes` cruzado con el catálogo, nunca de `Evaluation.tipo_fuente` (en el kit
está vacío en la mayoría de evaluaciones). Definiciones:

- **Cita:** un dominio en `Run.fuentes` de una ejecución. Un dominio repetido en la misma ejecución
  cuenta una vez.
- **Marcas de una respuesta:** las marcas con una evaluación `aparece` en esa ejecución, y que
  además estén en `Run.marcas_a_evaluar` (la misma regla de elegibilidad que `metrics`).
- **Web propia:** dominio del catálogo de tipo «Web propia», o dominio (o subdominio) del
  `Brand.dominio` de alguna marca de los mercados. Es `propio`; el resto es `ganado`.
- **Segmentos:** los del resto del dominio. Tipo de visibilidad (`tipo:espontaneo`,
  `tipo:asistido`, como en `metrics`), fase del embudo (`fase:<fase>`) y ciudad del prompt
  (`ciudad:<Ciudad>`). Los prompts sin ciudad no entran en ningún segmento de ciudad.

Anonimización del mapa:

1. Una fuente solo entra si la citan respuestas sobre al menos `MIN_MARCAS_SECTOR` marcas
   distintas (la unión de las marcas de las respuestas que la citan).
2. Las webs propias identifican a una marca. Se agregan en una sola entrada, `WEBS_PROPIAS`, y
   ningún dominio de marca sale en el mapa. A esa entrada también se le aplica la regla 1.
3. El mapa solo lleva recuentos y cuotas; ningún campo dice qué marca acompaña a qué fuente.

Las cuotas son la fracción de TODAS las citas (del sector, del motor o del segmento), también de
las fuentes que no entran en el mapa. Por eso las cuotas del mapa pueden sumar menos de 1.
"""

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

from posiq.domain.findings import confidence_for
from posiq.domain.schemas import (
    Brand,
    BriefSummary,
    Evaluation,
    Finding,
    Market,
    Motor,
    PromptInstance,
    Run,
    Source,
    Talla,
    TipoFuenteCatalogo,
)
from posiq.domain.source_map_schemas import (
    MIN_MARCAS_SECTOR,
    FuenteSector,
    MapaFuentes,
    OportunidadFuente,
    Propiedad,
    Puntuacion,
)

WEBS_PROPIAS: Final = "(webs propias)"
"""Dominio centinela de la entrada que agrega todas las webs propias del sector."""

WEB_PROPIA: Final[TipoFuenteCatalogo] = "Web propia"

UMBRAL_ALTA: Final = 0.005
"""`valor` ≥ 0,005 → Alta: p. ej. una fuente con el 5 % de las citas y 10 pp de brecha."""
UMBRAL_MEDIA: Final = 0.002
"""`valor` ≥ 0,002 → Media (5 % de cuota y 4 pp); por debajo, Baja. Distribución en el ADR 0010."""

MIN_APARICIONES_COMPETIDOR: Final = 5
"""Un competidor entra en la presencia media si aparece en ≥ 5 respuestas espontáneas."""

DECIMALES: Final = 4

Nivel = Literal["dominio", "tipo"]


@dataclass(frozen=True)
class DatosEstudio:
    """Un estudio ya cargado: su mercado, sus prompts, sus ejecuciones y sus evaluaciones."""

    market: Market
    prompts: Sequence[PromptInstance]
    runs: Sequence[Run]
    evaluations: Sequence[Evaluation]

    @property
    def study_id(self) -> str:
        ids = {r.study_id for r in self.runs} | {e.study_id for e in self.evaluations}
        if len(ids) != 1:
            raise ValueError(f"un DatosEstudio necesita exactamente un study_id; hay {sorted(ids)}")
        return ids.pop()


# --- Utilidades -----------------------------------------------------------------------------------


def _norm(dominio: str) -> str:
    d = dominio.strip().lower().rstrip(".")
    return d[4:] if d.startswith("www.") else d


def _parents(dominio: str) -> list[str]:
    """`a.b.c` → [`a.b.c`, `b.c`]: el dominio y sus padres con al menos dos etiquetas."""
    partes = _norm(dominio).split(".")
    return [".".join(partes[i:]) for i in range(max(len(partes) - 1, 1))]


class _Resolver:
    """Tipo de cada dominio (catálogo, también por dominio padre; si no, el de la ejecución)."""

    def __init__(self, catalogo: Iterable[Source], marcas: Iterable[Brand]) -> None:
        self.catalogo = {_norm(s.dominio): s.tipo for s in catalogo}
        self.propios = {_norm(b.dominio) for b in marcas if b.dominio}

    def tipo(self, fuente: Source) -> TipoFuenteCatalogo | None:
        if self.es_propia(fuente):
            return WEB_PROPIA
        for d in _parents(fuente.dominio):
            if self.catalogo.get(d) is not None:
                return self.catalogo[d]
        return fuente.tipo

    def es_propia(self, fuente: Source) -> bool:
        if fuente.tipo == WEB_PROPIA:
            return True
        return any(
            d in self.propios or self.catalogo.get(d) == WEB_PROPIA
            for d in _parents(fuente.dominio)
        )

    def clave(self, fuente: Source) -> str:
        """Dominio con el que la fuente entra en el mapa (las webs propias, agregadas)."""
        return WEBS_PROPIAS if self.es_propia(fuente) else _norm(fuente.dominio)


def _es_de_marca(dominio: str, marca: Brand) -> bool:
    return bool(marca.dominio) and _norm(marca.dominio or "") in _parents(dominio)


def _marcas_por_run(estudio: DatosEstudio) -> dict[str, set[str]]:
    """Marcas que aparecen en cada ejecución (solo marcas elegibles de la ejecución)."""
    elegibles = {r.id: set(r.marcas_a_evaluar) for r in estudio.runs}
    out: dict[str, set[str]] = defaultdict(set)
    for e in estudio.evaluations:
        if e.aparece and e.brand_id in elegibles.get(e.run_id, set()):
            out[e.run_id].add(e.brand_id)
    return out


def _dominios(run: Run) -> list[Source]:
    """Fuentes únicas de la ejecución (un dominio repetido cuenta una vez)."""
    vistos: dict[str, Source] = {}
    for s in run.fuentes:
        vistos.setdefault(_norm(s.dominio), s)
    return [vistos[d] for d in sorted(vistos)]


def _segmentos(prompt: PromptInstance | None) -> list[str]:
    if prompt is None:
        return []
    out = [f"tipo:{prompt.tipo}", f"fase:{prompt.fase_embudo}"]
    if prompt.ciudad:
        out.append(f"ciudad:{prompt.ciudad}")
    return out


def _r(x: float) -> float:
    return round(x, DECIMALES)


def _estudios_unicos(estudios: Sequence[DatosEstudio]) -> None:
    ids = [e.study_id for e in estudios]
    repetidos = sorted({i for i in ids if ids.count(i) > 1})
    if repetidos:
        raise ValueError(f"estudios repetidos: {repetidos}")


# --- 1-2. Mapa de fuentes del sector --------------------------------------------------------------


def mapa_fuentes(
    sector: str,
    estudios: Sequence[DatosEstudio],
    catalogo: Iterable[Source] = (),
    min_marcas: int = MIN_MARCAS_SECTOR,
) -> MapaFuentes:
    """Mapa agregado y anonimizado de las fuentes que citan los motores en `sector`.

    `estudios`: uno o varios estudios del mismo sector, ya cargados (p. ej. todos los de un sector
    en el repositorio). `catalogo`: el catálogo de fuentes (tipo por dominio).
    """
    if not estudios:
        raise ValueError("el mapa de fuentes necesita al menos un estudio")
    if min_marcas < MIN_MARCAS_SECTOR:
        raise ValueError(f"min_marcas no puede bajar de {MIN_MARCAS_SECTOR} (anonimización)")
    _estudios_unicos(estudios)
    resolver = _Resolver(catalogo, [b for e in estudios for b in e.market.marcas])

    total = 0
    total_motor: Counter[Motor] = Counter()
    total_seg: Counter[str] = Counter()
    citas: Counter[str] = Counter()
    por_motor: dict[str, Counter[Motor]] = defaultdict(Counter)
    por_seg: dict[str, Counter[str]] = defaultdict(Counter)
    marcas: dict[str, set[str]] = defaultdict(set)
    estudios_de: dict[str, set[str]] = defaultdict(set)
    tipos: dict[str, set[TipoFuenteCatalogo | None]] = defaultdict(set)
    todas_marcas: set[str] = set()

    for estudio in estudios:
        sid = estudio.study_id
        prompts = {p.id: p for p in estudio.prompts}
        marcas_run = _marcas_por_run(estudio)
        for run in sorted(estudio.runs, key=lambda r: r.id):
            segs = _segmentos(prompts.get(run.prompt_id))
            en_run = marcas_run.get(run.id, set())
            todas_marcas |= en_run
            for fuente in _dominios(run):
                clave = resolver.clave(fuente)
                total += 1
                total_motor[run.motor] += 1
                citas[clave] += 1
                por_motor[clave][run.motor] += 1
                for s in segs:
                    total_seg[s] += 1
                    por_seg[clave][s] += 1
                marcas[clave] |= en_run
                estudios_de[clave].add(sid)
                tipos[clave].add(resolver.tipo(fuente))

    fuentes: list[FuenteSector] = []
    for clave in sorted(citas, key=lambda c: (-citas[c], c)):
        if len(marcas[clave]) < min_marcas:
            continue
        tipo = WEB_PROPIA if clave == WEBS_PROPIAS else _tipo_unico(tipos[clave])
        fuentes.append(
            FuenteSector(
                dominio=clave,
                tipo=tipo,
                propiedad="propio" if tipo == WEB_PROPIA else "ganado",
                citas=citas[clave],
                cuota_citas=_r(citas[clave] / total),
                por_motor={m: _r(n / total_motor[m]) for m, n in sorted(por_motor[clave].items())},
                por_segmento={s: _r(n / total_seg[s]) for s, n in sorted(por_seg[clave].items())},
                n_estudios=len(estudios_de[clave]),
                n_marcas=len(marcas[clave]),
            )
        )
    return MapaFuentes(
        sector=sector,
        fuentes=fuentes,
        n_estudios=len(estudios),
        n_marcas=len(todas_marcas),
        n_citas=total,
        min_marcas=min_marcas,
    )


def _tipo_unico(tipos: set[TipoFuenteCatalogo | None]) -> TipoFuenteCatalogo | None:
    """El tipo del catálogo si es único; None si falta o hay contradicción entre estudios."""
    conocidos = {t for t in tipos if t is not None}
    return conocidos.pop() if len(conocidos) == 1 else None


def cuota_por_tipo(mapa: MapaFuentes) -> dict[TipoFuenteCatalogo, float]:
    """Cuota de citas del sector por tipo de fuente (solo fuentes que entran en el mapa)."""
    out: dict[TipoFuenteCatalogo, float] = defaultdict(float)
    for f in mapa.fuentes:
        if f.tipo is not None:
            out[f.tipo] += f.cuota_citas
    return {t: _r(c) for t, c in sorted(out.items(), key=lambda kv: (-kv[1], kv[0]))}


# --- 3. Oportunidades por marca -------------------------------------------------------------------


def puntuacion(valor: float) -> Puntuacion:
    """Alta ≥ `UMBRAL_ALTA` · Media ≥ `UMBRAL_MEDIA` · Baja (umbrales fijos, ADR 0010)."""
    if valor >= UMBRAL_ALTA:
        return "Alta"
    return "Media" if valor >= UMBRAL_MEDIA else "Baja"


@dataclass(frozen=True)
class _Objetivo:
    """Una fuente o tipo del mapa y cómo saber si una ejecución lo cita para una marca dada."""

    dominio: str | None
    tipo: TipoFuenteCatalogo | None
    cuota_sector: float
    propio: bool
    claves: frozenset[str]  # dominios (normalizados) que cuentan; vacío si es web propia


def _objetivos(
    mapa: MapaFuentes, nivel: Nivel, resolver: _Resolver, marca: Brand
) -> list[_Objetivo]:
    ganadas = [f for f in mapa.fuentes if f.propiedad == "ganado"]
    propia = next((f for f in mapa.fuentes if f.propiedad == "propio"), None)
    out: list[_Objetivo] = []
    if nivel == "dominio":
        out += [
            _Objetivo(f.dominio, f.tipo, f.cuota_citas, False, frozenset({f.dominio}))
            for f in ganadas
        ]
    else:
        por_tipo: dict[TipoFuenteCatalogo, list[FuenteSector]] = defaultdict(list)
        for f in ganadas:
            if f.tipo is not None:
                por_tipo[f.tipo].append(f)
        out += [
            _Objetivo(
                None,
                tipo,
                _r(sum(f.cuota_citas for f in fs)),
                False,
                frozenset(f.dominio for f in fs),
            )
            for tipo, fs in sorted(por_tipo.items())
        ]
    if propia is not None and marca.dominio:
        out.append(
            _Objetivo(
                _norm(marca.dominio) if nivel == "dominio" else None,
                WEB_PROPIA,
                propia.cuota_citas,
                True,
                frozenset(),
            )
        )
    return out


def _cita(run: Run, objetivo: _Objetivo, marca: Brand, resolver: _Resolver) -> bool:
    """¿La ejecución cita el objetivo? Para la web propia: la web propia DE ESA marca."""
    if objetivo.propio:
        return any(_es_de_marca(s.dominio, marca) for s in run.fuentes)
    return any(resolver.clave(s) in objetivo.claves for s in run.fuentes)


def oportunidades_fuente(
    mapa: MapaFuentes,
    estudio: DatosEstudio,
    brand_id: str,
    catalogo: Iterable[Source] = (),
    nivel: Nivel = "dominio",
) -> list[OportunidadFuente]:
    """Fuentes (o tipos) del mapa donde la marca está menos presente que sus competidores.

    Se miran las respuestas ESPONTÁNEAS del estudio, como `metrics._source_gap`: cuando el usuario
    no nombra a nadie, ¿qué fuentes acompañan a los competidores y no a la marca?

    - `presencia_marca`: fracción de las respuestas espontáneas donde aparece la marca que citan la
      fuente (0 si la marca no aparece en ninguna).
    - `presencia_competidores`: media simple de esa fracción en las demás marcas del mercado con al
      menos `MIN_APARICIONES_COMPETIDOR` apariciones espontáneas.
    - Para la web propia, «citar la fuente» es citar la web propia de cada marca.
    - `gap` = competidores − marca; `valor` = cuota_sector × gap. Solo se devuelven gaps > 0,
      ordenadas por valor (y por dominio o tipo a igualdad).
    - `evaluation_ids`: apariciones de competidores en respuestas espontáneas que citan la fuente
      y en las que la marca no aparece, más la evaluación de ausencia de la marca en ellas.
    """
    marcas = {b.id: b for b in estudio.market.marcas}
    if brand_id not in marcas:
        raise ValueError(f"la marca {brand_id} no está en el mercado del estudio")
    marca = marcas[brand_id]
    resolver = _Resolver(catalogo, estudio.market.marcas)
    prompts = {p.id: p for p in estudio.prompts}
    espontaneas = sorted(
        (r for r in estudio.runs if (p := prompts.get(r.prompt_id)) and p.tipo == "espontaneo"),
        key=lambda r: r.id,
    )
    marcas_run = _marcas_por_run(estudio)
    runs_de: dict[str, list[Run]] = defaultdict(list)
    for run in espontaneas:
        for b in sorted(marcas_run.get(run.id, set())):
            runs_de[b].append(run)
    competidores = [
        marcas[b]
        for b in sorted(runs_de)
        if b != brand_id and b in marcas and len(runs_de[b]) >= MIN_APARICIONES_COMPETIDOR
    ]
    if not competidores:
        return []
    evals_de_run: dict[str, list[Evaluation]] = defaultdict(list)
    for e in estudio.evaluations:
        evals_de_run[e.run_id].append(e)

    out: list[OportunidadFuente] = []
    for obj in _objetivos(mapa, nivel, resolver, marca):
        propias = runs_de.get(brand_id, [])
        p_marca = _presencia(propias, obj, marca, resolver)
        p_comp = sum(_presencia(runs_de[c.id], obj, c, resolver) for c in competidores) / len(
            competidores
        )
        gap = p_comp - p_marca
        if gap <= 0:
            continue
        ids = _evidencias(espontaneas, obj, brand_id, competidores, evals_de_run, resolver)
        if not ids:
            continue
        valor = obj.cuota_sector * gap
        out.append(
            OportunidadFuente(
                brand_id=brand_id,
                dominio=obj.dominio,
                tipo=obj.tipo,
                cuota_sector=obj.cuota_sector,
                presencia_marca=_r(p_marca),
                presencia_competidores=_r(p_comp),
                gap=_r(gap),
                valor=_r(valor),
                puntuacion=puntuacion(_r(valor)),
                evaluation_ids=ids,
            )
        )
    return sorted(out, key=lambda o: (-o.valor, o.dominio or "", o.tipo or ""))


def _presencia(runs: Sequence[Run], obj: _Objetivo, marca: Brand, resolver: _Resolver) -> float:
    if not runs:
        return 0.0
    return sum(_cita(r, obj, marca, resolver) for r in runs) / len(runs)


def _evidencias(
    espontaneas: Sequence[Run],
    obj: _Objetivo,
    brand_id: str,
    competidores: Sequence[Brand],
    evals_de_run: Mapping[str, Sequence[Evaluation]],
    resolver: _Resolver,
) -> list[str]:
    comp = {c.id: c for c in competidores}
    ids: set[str] = set()
    for run in espontaneas:
        evals = evals_de_run.get(run.id, [])
        if any(e.brand_id == brand_id and e.aparece for e in evals):
            continue
        apoyo = [
            e.id
            for e in evals
            if e.aparece
            and e.brand_id in comp
            and e.brand_id in run.marcas_a_evaluar
            and _cita(run, obj, comp[e.brand_id], resolver)
        ]
        if apoyo:
            ids.update(apoyo)
            ids.update(e.id for e in evals if e.brand_id == brand_id and not e.aparece)
    return sorted(ids)


# --- 4. Hallazgo: cuota de citas de la web propia -------------------------------------------------


def _cuota_propia(runs: Sequence[Run], marca: Brand) -> tuple[int, int]:
    """(citas de la web de la marca, citas totales) en esas ejecuciones."""
    total = propias = 0
    for run in runs:
        for s in _dominios(run):
            total += 1
            propias += _es_de_marca(s.dominio, marca)
    return propias, total


def _pct(x: float) -> str:
    return f"{x * 100:.1f}".replace(".", ",") + " %"


def hallazgo_web_propia(
    estudio: DatosEstudio, brand_id: str, catalogo: Iterable[Source] = ()
) -> Finding | None:
    """% de las citas que van a la web propia de la marca en las respuestas donde aparece.

    Cuenta todas las respuestas (espontáneas y asistidas) en las que la marca aparece. Se compara
    con la media de esa misma cuota en los competidores (cada uno con su web) y con la cuota de
    todas las webs propias en esas respuestas. Impacto: L si la cuota es menos de la mitad de la
    media de los competidores · M si es menor que la media · S si no. None si la marca no tiene
    dominio propio o sus respuestas no citan fuentes. No entra en `detect_findings`.
    """
    marcas = {b.id: b for b in estudio.market.marcas}
    marca = marcas.get(brand_id)
    if marca is None or not marca.dominio:
        return None
    resolver = _Resolver(catalogo, estudio.market.marcas)
    runs = {r.id: r for r in estudio.runs}
    marcas_run = _marcas_por_run(estudio)
    de_marca: dict[str, list[Run]] = defaultdict(list)
    for run_id in sorted(marcas_run):
        for b in marcas_run[run_id]:
            if run_id in runs:
                de_marca[b].append(runs[run_id])
    propias, total = _cuota_propia(de_marca.get(brand_id, []), marca)
    if total == 0:
        return None
    cuota = propias / total
    webs = sum(resolver.es_propia(s) for r in de_marca.get(brand_id, []) for s in _dominios(r))
    cuotas_comp = [
        p / t
        for c in sorted(marcas)
        if c != brand_id and marcas[c].dominio
        for p, t in [_cuota_propia(de_marca.get(c, []), marcas[c])]
        if t > 0
    ]
    media = sum(cuotas_comp) / len(cuotas_comp) if cuotas_comp else None
    impacto: Talla = "S"
    if media is not None and cuota < media / 2:
        impacto = "L"
    elif media is not None and cuota < media:
        impacto = "M"
    comparacion = (
        f" La media de sus competidores es del {_pct(media)} de las citas de sus respuestas."
        if media is not None
        else ""
    )
    titulo = (
        "Su web propia se cita menos que la de sus competidores"
        if media is not None and cuota < media
        else "Su web propia se cita más que la de sus competidores"
        if media is not None
        else "Peso de la web propia en las citas"
    )
    ids = sorted(
        e.id
        for e in estudio.evaluations
        if e.brand_id == brand_id and e.aparece and brand_id in marcas_run.get(e.run_id, set())
    )
    n = len(de_marca[brand_id])
    return Finding(
        id="F-web-propia",
        study_id=estudio.study_id,
        titulo=titulo,
        descripcion=(
            f"{marca.dominio} recibe {propias} de las {total} citas ({_pct(cuota)}) de las "
            f"{n} respuestas en las que aparece la marca; las webs propias en conjunto, el "
            f"{_pct(webs / total)}.{comparacion}"
        ),
        impacto=impacto,
        confianza=confidence_for(n),
        cifra=_r(cuota),
        unidad="fraccion",
        origen_cifra=f"citas a {marca.dominio} / citas en respuestas donde aparece la marca",
        evaluation_ids=ids,
    )


# --- 5. Punto de partida para un cliente nuevo ----------------------------------------------------


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FuentePrioritaria(_Model):
    """Fuente ganada del sector recomendada como punto de partida.

    `relevancia`: la cuota con la que se ordena (de las ciudades del brief, del motor o del sector).
    `base`: de dónde sale esa cuota (`sector`, `ciudad:Madrid+Barcelona`, `motor:Gemini`).
    """

    dominio: str
    tipo: TipoFuenteCatalogo | None
    propiedad: Propiedad
    relevancia: float
    cuota_sector: float
    base: str


class PuntoDePartida(_Model):
    """Fuentes prioritarias del sector para un cliente sin datos propios."""

    sector: str
    prioritarias: list[FuentePrioritaria]
    por_tipo: dict[TipoFuenteCatalogo, list[FuentePrioritaria]]
    por_motor: dict[Motor, list[FuentePrioritaria]]
    cuota_webs_propias: float | None
    avisos: list[str] = []


def _prioritaria(f: FuenteSector, relevancia: float, base: str) -> FuentePrioritaria:
    return FuentePrioritaria(
        dominio=f.dominio,
        tipo=f.tipo,
        propiedad=f.propiedad,
        relevancia=_r(relevancia),
        cuota_sector=f.cuota_citas,
        base=base,
    )


def _ordenar(items: list[FuentePrioritaria], top_n: int) -> list[FuentePrioritaria]:
    return sorted(items, key=lambda p: (-p.relevancia, -p.cuota_sector, p.dominio))[:top_n]


def punto_de_partida(
    mapa: MapaFuentes,
    brief: BriefSummary | None = None,
    motores: Sequence[Motor] | None = None,
    top_n: int = 5,
) -> PuntoDePartida:
    """Fuentes prioritarias del sector para un cliente nuevo: global, por tipo y por motor.

    Solo fuentes ganadas (las webs propias de otras marcas no sirven a un cliente nuevo; su peso
    agregado sale en `cuota_webs_propias`). Con `brief`, si el mapa tiene datos de sus ciudades,
    la relevancia es la cuota media en esas ciudades y se quitan las fuentes que no se citan en
    ninguna. El mapa no segmenta por servicio: los servicios del brief no filtran (sale un aviso).
    """
    ganadas = [f for f in mapa.fuentes if f.propiedad == "ganado"]
    propia = next((f for f in mapa.fuentes if f.propiedad == "propio"), None)
    avisos: list[str] = []

    base = "sector"
    relevancia = {f.dominio: f.cuota_citas for f in ganadas}
    if brief is not None:
        ciudades = [
            c for c in brief.ciudades if any(f"ciudad:{c}" in f.por_segmento for f in ganadas)
        ]
        sin_datos = [c for c in brief.ciudades if c not in ciudades]
        if sin_datos:
            avisos.append(f"el mapa no tiene datos de {', '.join(sin_datos)}: se usa el sector")
        if ciudades:
            base = "ciudad:" + "+".join(ciudades)
            relevancia = {
                f.dominio: sum(f.por_segmento.get(f"ciudad:{c}", 0.0) for c in ciudades)
                / len(ciudades)
                for f in ganadas
            }
        if brief.servicios_prioritarios:
            avisos.append("el mapa no segmenta por servicio: los servicios del brief no filtran")

    candidatas = [_prioritaria(f, relevancia[f.dominio], base) for f in ganadas]
    candidatas = [p for p in candidatas if p.relevancia > 0]
    por_tipo: dict[TipoFuenteCatalogo, list[FuentePrioritaria]] = defaultdict(list)
    for p in candidatas:
        if p.tipo is not None:
            por_tipo[p.tipo].append(p)
    lista_motores = sorted(motores or {m for f in ganadas for m in f.por_motor})
    por_motor = {
        m: _ordenar(
            [_prioritaria(f, f.por_motor[m], f"motor:{m}") for f in ganadas if f.por_motor.get(m)],
            top_n,
        )
        for m in lista_motores
    }
    return PuntoDePartida(
        sector=mapa.sector,
        prioritarias=_ordenar(candidatas, top_n),
        por_tipo={t: _ordenar(ps, top_n) for t, ps in sorted(por_tipo.items())},
        por_motor=por_motor,
        cuota_webs_propias=propia.cuota_citas if propia else None,
        avisos=avisos,
    )
