"""Exactitud de marca: qué afirman los motores sobre la marca y si cuadra con el brief. Sin I/O.

Decisiones en `docs/adr/0011-exactitud-de-marca.md`. En resumen:

1. **Extracción por reglas.** Se toman las oraciones de cada respuesta que nombran la marca (con la
   misma detección que el score) y, en cada una, los términos de un vocabulario: servicios
   (`SERVICIOS_CONOCIDOS` + servicios del brief), sedes (`CIUDADES_CONOCIDAS` + ciudades del
   brief), profesionales, precios y resultados clínicos. Una afirmación es un par (oración, tipo):
   su `texto` es el fragmento literal de la respuesta, acotado a `MAX_FRAGMENTO` caracteres
   alrededor de la marca. Un término solo cuenta si la marca más cercana que lo precede (o, si no
   hay, la siguiente) es la del estudio: así no se atribuye a la marca lo que la oración dice de
   un competidor.
2. **Verificación conservadora contra el `BriefSummary`.** `incorrecta` solo cuando el brief tiene
   el dato y la afirmación lo contradice: niega un servicio o una ciudad del brief, o sitúa una sede
   («centro en», «sede en»…) en una ciudad que el brief no recoge. Si no hay dato con qué comparar,
   `no_verificable`, nunca `incorrecta`.
3. **Riesgo regulatorio.** `EXPRESIONES_RIESGO` es una lista explícita de expresiones que la clínica
   debe revisar (`ETIQUETA_RIESGO`): garantías, ausencia de riesgo, absolutos, superlativos y
   comparaciones. No es un juicio de legalidad.
4. **Mitigación.** Para cada afirmación incorrecta, la fuente que citó el motor (la del marcador
   `[n]` del fragmento o, si no lo hay, las de la respuesta) y una acción enlazada a una `Palanca`.

La capa opcional con LLM (`AfirmacionesLLM`) solo propone fragmentos: se descartan los que no son
literales de la respuesta y la verificación la hace siempre este módulo.
"""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from posiq.domain.accuracy_schemas import (
    ETIQUETA_RIESGO,
    AccionMitigacion,
    Afirmacion,
    EstadoVerificacion,
    HallazgoExactitud,
    TipoAfirmacion,
    Verificacion,
)
from posiq.domain.detection import brand_mentions
from posiq.domain.schemas import Brand, BriefSummary, Palanca, Run, Source
from posiq.domain.text import fold, slugify

MAX_FRAGMENTO = 300
TIPOS: tuple[TipoAfirmacion, ...] = (
    "servicio",
    "sede",
    "profesional",
    "precio",
    "resultado_clinico",
    "otro",
)
ESTADOS: tuple[EstadoVerificacion, ...] = (
    "correcta",
    "incorrecta",
    "no_verificable",
    "riesgo_regulatorio",
)

# --- Vocabulario ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class ServicioConocido:
    """Servicio del sector. `patrones` son regex sobre texto plegado (sin acentos, minúsculas).

    `equivale_a`: términos plegados que, si aparecen en el brief, lo confirman (LASIK es cirugía
    refractiva).
    """

    nombre: str
    patrones: tuple[str, ...]
    equivale_a: tuple[str, ...] = ()


SERVICIOS_CONOCIDOS: tuple[ServicioConocido, ...] = (
    ServicioConocido("cirugía refractiva", (r"cirugias? refractivas?",)),
    ServicioConocido(
        "cirugía láser",
        (r"cirugias? (con )?laser", r"laser excimer"),
        ("cirugia refractiva",),
    ),
    ServicioConocido("LASIK", (r"lasik",), ("cirugia refractiva",)),
    ServicioConocido("PRK", (r"prk",), ("cirugia refractiva",)),
    ServicioConocido("SMILE", (r"smile",), ("cirugia refractiva",)),
    ServicioConocido("lentes fáquicas", (r"lentes? faquicas?",), ("cirugia refractiva",)),
    ServicioConocido("cataratas", (r"cataratas?",)),
    ServicioConocido(
        "lentes intraoculares",
        (r"lentes? intraoculares?", r"lentes? premium", r"lentes? multifocales?"),
        ("cataratas", "cirugia refractiva"),
    ),
    ServicioConocido("presbicia", (r"presbicia", r"vista cansada")),
    ServicioConocido(
        "control de miopía infantil",
        (
            r"control de (la )?miopia( infantil)?",
            r"miopia (infantil|progresiva)",
            r"ortoqueratologia",
        ),
        ("miopia infantil", "control de miopia"),
    ),
    ServicioConocido("retina", (r"retina",)),
    ServicioConocido("glaucoma", (r"glaucoma",)),
    ServicioConocido("queratocono", (r"queratocono",)),
    ServicioConocido("ojo seco", (r"ojo seco",)),
    ServicioConocido("estrabismo", (r"estrabismo",)),
    ServicioConocido("oftalmología pediátrica", (r"oftalmologia (pediatrica|infantil)",)),
    ServicioConocido(
        "revisiones oftalmológicas",
        (r"revision(es)? oftalmologicas?", r"revisiones de (la )?vista"),
    ),
    ServicioConocido(
        "valoración preoperatoria",
        (r"valoracion(es)? preoperatorias?", r"estudios? preoperatorios?"),
    ),
    ServicioConocido(
        "seguimiento postoperatorio",
        (r"seguimiento (postoperatorio|personalizado)", r"revisiones postoperatorias"),
    ),
    ServicioConocido("optometría", (r"optometria",)),
)

# Capitales de provincia y grandes ciudades: para detectar sedes que el brief NO recoge. El kit solo
# trae Madrid y Barcelona; las ciudades del brief se añaden siempre.
CIUDADES_CONOCIDAS: tuple[str, ...] = (
    "Madrid", "Barcelona", "Valencia", "Sevilla", "Zaragoza", "Málaga", "Murcia", "Palma",
    "Las Palmas", "Bilbao", "Alicante", "Córdoba", "Valladolid", "Vigo", "Gijón", "A Coruña",
    "Granada", "Vitoria", "Elche", "Oviedo", "Pamplona", "San Sebastián", "Santander", "Logroño",
    "Badajoz", "Cáceres", "Salamanca", "Burgos", "Albacete", "Castellón", "Tarragona", "Lleida",
    "Girona", "Huesca", "Teruel", "Almería", "Jaén", "Cádiz", "Huelva", "Ourense", "Pontevedra",
    "Lugo", "Segovia", "Ávila", "Soria", "Zamora", "Palencia", "Toledo", "Cuenca",
    "Ciudad Real", "Guadalajara", "Santa Cruz de Tenerife", "Santiago de Compostela",
    "Cartagena", "Jerez", "Marbella",
)  # fmt: skip

# Palabras que convierten «en <ciudad>» en una afirmación de sede.
_SEDE = re.compile(
    r"\b(sedes?|centros?|clinicas?|consultas?|instalaciones|delegacion(es)?|ubicad[oa]s?|"
    r"situad[oa]s?|abri[oa]|abiertos?|inaugur\w*|presencia)\b"
)
_NEGACION = re.compile(r"\b(no|nunca|tampoco)\b(?!\s+solo\b)")
_LIMITE_CLAUSULA = re.compile(r"[,;:()–—]|\s(?:pero|aunque|mientras|sino)\s")

_PROFESIONAL_NOMBRE = re.compile(
    r"\b(?:Dr|Dra|Doctor|Doctora)\.?\s+[A-ZÁÉÍÓÚÑ][\wáéíóúñü]+(?:\s+[A-ZÁÉÍÓÚÑ][\wáéíóúñü]+){0,2}"
)
_PROFESIONAL = (
    r"equipo (medico|de oftalmologos|de cirujanos|de especialistas)",
    r"\d+ (oftalmologos|cirujanos|especialistas|medicos|optometristas)",
)
_PRECIO = (
    r"\d[\d.,]*\s?(€|euros?\b|eur\b)",
    r"\b(gratis|gratuit[oa]s?|sin coste)\b",
    r"\b(precios?|tarifas?)\s+(\w+\s+)?(ajustad|competitiv|cerrad|economic|baj|asequibl|reducid)\w*",
    r"\bfinanciacion\b",
    r"\blow cost\b",
)
_RESULTADO = (
    r"\b(tasa|indice|porcentaje) de (exito|acierto|curacion)",
    r"\d[\d.,]*\s?% de (exito|pacientes|casos|curacion)",
    r"\bvision perfecta\b",
    r"\bgafas para siempre\b",
    r"\bresultados? (garantizad|asegurad|definitiv|permanent)\w*",
    r"\bgarantiz\w* (los |unos )?resultados?\b",
    r"\bsin (efectos secundarios|complicaciones)\b",
)

# --- Lista de expresiones a revisar por la clínica ------------------------------------------------

CategoriaRiesgo = Literal[
    "garantia_resultado", "ausencia_riesgo", "absoluto", "superlativo", "comparacion"
]


@dataclass(frozen=True)
class ExpresionRiesgo:
    """Expresión de la lista de revisión. `patron` es una regex sobre texto plegado."""

    id: str
    categoria: CategoriaRiesgo
    expresion: str
    patron: str


EXPRESIONES_RIESGO: tuple[ExpresionRiesgo, ...] = (
    ExpresionRiesgo(
        "garantiza",
        "garantia_resultado",
        "garantiza / garantizado",
        r"\bgarantiz(a|an|amos|ad[oa]s?)\b",
    ),
    ExpresionRiesgo(
        "garantia-resultado",
        "garantia_resultado",
        "garantía de resultado / éxito",
        r"\bgarantia (de|del) (exito|resultado)",
    ),
    ExpresionRiesgo(
        "asegurado",
        "garantia_resultado",
        "resultado / éxito asegurado",
        r"\b(resultados?|exito) asegurad[oa]s?\b",
    ),
    ExpresionRiesgo(
        "sin-riesgo",
        "ausencia_riesgo",
        "sin riesgo / riesgo cero",
        r"\bsin (ningun )?riesgos?\b|\briesgo cero\b|\blibre de riesgos?\b",
    ),
    ExpresionRiesgo(
        "totalmente-seguro",
        "ausencia_riesgo",
        "totalmente seguro",
        r"\b(totalmente|completamente|100 ?%) segur[oa]s?\b",
    ),
    ExpresionRiesgo(
        "sin-efectos",
        "ausencia_riesgo",
        "sin efectos secundarios / sin complicaciones",
        r"\bsin (efectos secundarios|complicaciones)\b",
    ),
    ExpresionRiesgo("100", "absoluto", "100 % / cien por cien", r"\b100 ?%|\bcien por cien\b"),
    ExpresionRiesgo("para-siempre", "absoluto", "para siempre", r"\bpara siempre\b"),
    ExpresionRiesgo("vision-perfecta", "absoluto", "visión perfecta", r"\bvision perfecta\b"),
    ExpresionRiesgo(
        "el-mejor", "superlativo", "el mejor / la mejor", r"\b(el|la|los|las) mejor(es)?\b"
    ),
    ExpresionRiesgo(
        "numero-uno", "superlativo", "número uno / n.º 1", r"\bnumero uno\b|\bn\.? ?[ºo°] ?1\b"
    ),
    ExpresionRiesgo(
        "mas-recomendada",
        "superlativo",
        "la opción más recomendada / recomendable",
        r"\bmas recomendad[oa]s?\b|\bmas recomendables?\b",
    ),
    ExpresionRiesgo(
        "lider", "superlativo", "líder indiscutible", r"\blider (indiscutible|absolut)"
    ),
    ExpresionRiesgo("mejor-que", "comparacion", "mejor que (otro centro)", r"\bmejor(es)? que\b"),
    ExpresionRiesgo(
        "mas-que",
        "comparacion",
        "más barato / seguro / eficaz que",
        r"\bmas (barat|economic|segur|eficaz|rapid)\w* que\b",
    ),
    ExpresionRiesgo(
        "superior-a",
        "comparacion",
        "superior a otros centros",
        r"\bsuperior(es)? a (otr|la competencia|cualquier)",
    ),
)

_NEGACION_PREVIA = re.compile(r"\b(no|nunca|ningun[oa]?)\b(\s+\w+){0,2}\s*$")


# --- Texto ----------------------------------------------------------------------------------------


def _plegar(texto: str) -> str:
    """`fold` carácter a carácter con la misma longitud: los índices valen para el original."""
    return "".join((fold(c) or c)[0] for c in texto)


_ABREVIATURAS = frozenset(
    {"dr", "dra", "dres", "sr", "sra", "srta", "etc", "aprox", "ej", "n", "p"}
)


def _oraciones(texto: str) -> list[tuple[int, int]]:
    """Spans de las oraciones (por línea y por `.`, `!`, `?` seguidos de espacio)."""
    spans: list[tuple[int, int]] = []
    for linea in re.finditer(r"[^\n]+", texto):
        inicio = linea.start()
        for fin_m in re.finditer(r"[.!?]+(?=\s)", linea.group()):
            corte = linea.start() + fin_m.end()
            previa = texto[inicio : linea.start() + fin_m.start()].strip()
            palabra = re.split(r"\s+", previa)[-1].lower() if previa else ""
            if palabra in _ABREVIATURAS or re.fullmatch(r"\d+", previa):
                continue
            spans.append((inicio, corte))
            inicio = corte
        spans.append((inicio, linea.end()))
    out: list[tuple[int, int]] = []
    for a, b in spans:
        tramo = texto[a:b]
        a += len(tramo) - len(tramo.lstrip())
        b -= len(tramo) - len(tramo.rstrip())
        lista = re.match(r"(?:[*\-•]|\d+\.)\s+", texto[a:b])
        if lista:
            a += lista.end()
        if a < b:
            out.append((a, b))
    return out


def _acotar(texto: str, a: int, b: int, foco: int) -> tuple[int, int]:
    """Ventana de `MAX_FRAGMENTO` caracteres dentro de [a, b) alrededor de `foco`, sin cortar
    palabras."""
    if b - a <= MAX_FRAGMENTO:
        return a, b
    ini = max(a, foco - MAX_FRAGMENTO // 3)
    fin = min(b, ini + MAX_FRAGMENTO)
    while ini > a and not texto[ini - 1].isspace() and ini < fin:
        ini += 1
    while fin < b and not texto[fin].isspace() and fin > ini:
        fin -= 1
    return ini, fin


# --- Análisis de un fragmento ---------------------------------------------------------------------


@dataclass(frozen=True)
class _Vocabulario:
    servicios: tuple[ServicioConocido, ...]
    ciudades: tuple[str, ...]


def _vocabulario(brief: BriefSummary | None, ciudades: Iterable[str] = ()) -> _Vocabulario:
    del_brief = tuple(
        ServicioConocido(s, (re.escape(fold(s)),))
        for s in (brief.servicios_prioritarios if brief else [])
    )
    nombres = [*(brief.ciudades if brief else []), *ciudades, *CIUDADES_CONOCIDAS]
    vistas: dict[str, str] = {}
    for c in nombres:
        vistas.setdefault(fold(c.strip()), c.strip())
    return _Vocabulario(del_brief + SERVICIOS_CONOCIDOS, tuple(v for v in vistas.values() if v))


@dataclass(frozen=True)
class _Termino:
    tipo: TipoAfirmacion
    clave: str
    inicio: int
    fin: int
    negado: bool = False
    sede_explicita: bool = False


@dataclass(frozen=True)
class _Analisis:
    terminos: tuple[_Termino, ...]
    riesgos: tuple[str, ...]  # ids de EXPRESIONES_RIESGO

    def de_tipo(self, tipo: TipoAfirmacion) -> list[_Termino]:
        return [t for t in self.terminos if t.tipo == tipo]


def _inicio_clausula(plegado: str, pos: int) -> int:
    inicio = 0
    for m in _LIMITE_CLAUSULA.finditer(plegado, 0, pos):
        if m.end() <= pos:
            inicio = m.end()
    return inicio


def _sin_solapes(encontrados: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    encontrados.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    kept: list[tuple[int, int, str]] = []
    for e in encontrados:
        if not kept or e[0] >= kept[-1][1]:
            kept.append(e)
    return kept


def _buscar(patrones: Iterable[tuple[str, str]], texto: str) -> list[tuple[int, int, str]]:
    """Coincidencias `(inicio, fin, clave)` de pares (clave, regex) con límite de palabra."""
    out: list[tuple[int, int, str]] = []
    for clave, patron in patrones:
        for m in re.finditer(rf"(?<!\w)(?:{patron})(?!\w)", texto):
            out.append((m.start(), m.end(), clave))
    return _sin_solapes(out)


def _duenyo(pos: int, menciones: list[tuple[int, int, str]], foco: str) -> str:
    """La marca más cercana antes de `pos` o, si no hay, la siguiente; sin menciones, el foco."""
    previas = [m for m in menciones if m[1] <= pos]
    if previas:
        return previas[-1][2]
    siguientes = [m for m in menciones if m[0] >= pos]
    return siguientes[0][2] if siguientes else foco


def _sede_explicita(plegado: str, inicio: int, ciudades: Sequence[str]) -> tuple[bool, int]:
    """¿«en <ciudad>» (también en listas: «en Madrid, Valencia y Sevilla») con palabra de sede en
    la cláusula? Devuelve también desde dónde mirar la negación."""
    m = re.search(r"\ben\s+([^.;:]*)$", plegado[:inicio])
    if m is None:
        return False, _inicio_clausula(plegado, inicio)
    resto = m.group(1)
    for c in sorted(ciudades, key=len, reverse=True):
        resto = re.sub(rf"(?<!\w){re.escape(fold(c))}(?!\w)", " ", resto)
    if not re.fullmatch(r"(\s|,|\by\b|\be\b)*", resto):
        return False, _inicio_clausula(plegado, inicio)
    desde = _inicio_clausula(plegado, m.start())
    return bool(_SEDE.search(plegado, desde, m.start())), desde


def _analizar(texto: str, brand: Brand, marcas: Sequence[Brand], vocab: _Vocabulario) -> _Analisis:
    """Términos y expresiones de riesgo de `texto` atribuidos a `brand`."""
    plegado = _plegar(texto)
    menciones = brand_mentions(texto, list(marcas))
    enmascarado = list(plegado)
    for a, b, _ in menciones:
        enmascarado[a:b] = " " * (b - a)
    limpio = "".join(enmascarado)

    def propio(pos: int) -> bool:
        return _duenyo(pos, menciones, brand.id) == brand.id

    def negado(desde: int, pos: int) -> bool:
        return bool(_NEGACION.search(limpio, desde, pos))

    terminos: list[_Termino] = []
    servicios = [(s.nombre, p) for s in vocab.servicios for p in s.patrones]
    for a, b, clave in _buscar(servicios, limpio):
        if propio(a):
            terminos.append(
                _Termino("servicio", clave, a, b, negado(_inicio_clausula(limpio, a), a))
            )
    for a, b, clave in _buscar(((c, re.escape(fold(c))) for c in vocab.ciudades), limpio):
        if propio(a):
            explicita, desde = _sede_explicita(limpio, a, vocab.ciudades)
            terminos.append(_Termino("sede", clave, a, b, negado(desde, a), explicita))
    profesionales = [(m.start(), m.end(), m.group()) for m in _PROFESIONAL_NOMBRE.finditer(texto)]
    profesionales += [
        (a, b, texto[a:b]) for a, b, _ in _buscar(((p, p) for p in _PROFESIONAL), limpio)
    ]
    for a, b, clave in _sin_solapes(profesionales):
        if propio(a) and limpio[a:b].strip() == plegado[a:b].strip():
            terminos.append(_Termino("profesional", clave, a, b))
    por_patron: tuple[tuple[TipoAfirmacion, tuple[str, ...]], ...] = (
        ("precio", _PRECIO),
        ("resultado_clinico", _RESULTADO),
    )
    for tipo, patrones in por_patron:
        for a, b, _ in _buscar(((p, p) for p in patrones), limpio):
            if propio(a):
                terminos.append(_Termino(tipo, texto[a:b], a, b))

    riesgos: list[str] = []
    for exp in EXPRESIONES_RIESGO:
        for m in re.finditer(exp.patron, limpio):
            previo = limpio[_inicio_clausula(limpio, m.start()) : m.start()]
            if propio(m.start()) and not _NEGACION_PREVIA.search(previo):
                riesgos.append(exp.id)
                break
    return _Analisis(tuple(terminos), tuple(riesgos))


# --- Extracción -----------------------------------------------------------------------------------


def evaluation_id(run: Run, brand: Brand) -> str:
    """Id de la evaluación de `brand` en `run` (convención de todo el sistema)."""
    return f"{run.id}:{brand.id}"


def _todas(brand: Brand, marcas: Iterable[Brand]) -> list[Brand]:
    out = {brand.id: brand}
    for m in marcas:
        out.setdefault(m.id, m)
    return list(out.values())


def _fragmentos(run: Run, brand: Brand, marcas: list[Brand]) -> list[tuple[int, int]]:
    """Fragmentos literales (spans) de las oraciones que nombran `brand`, en orden y sin repetir."""
    texto = run.texto_respuesta
    propias = [m for m in brand_mentions(texto, marcas) if m[2] == brand.id]
    out: list[tuple[int, int]] = []
    for a, b in _oraciones(texto):
        dentro = [m for m in propias if a <= m[0] < b]
        if dentro:
            out.append(_acotar(texto, a, b, dentro[0][0]))
    return out


def extraer_afirmaciones(
    runs: Iterable[Run],
    brand: Brand,
    brief: BriefSummary | None = None,
    *,
    marcas: Iterable[Brand] = (),
    ciudades: Iterable[str] = (),
) -> list[Afirmacion]:
    """Afirmaciones por reglas sobre `brand` en las respuestas que la nombran.

    Una afirmación por (oración, tipo). `marcas` son las demás del mercado: sirven para no atribuir
    a `brand` lo que se dice de otra. `ciudades` amplía el vocabulario de sedes. Solo se miran las
    ejecuciones que piden evaluar `brand` (las que tienen evaluación).
    """
    todas = _todas(brand, marcas)
    vocab = _vocabulario(brief, ciudades)
    out: list[Afirmacion] = []
    for run in runs:
        if brand.id not in run.marcas_a_evaluar:
            continue
        vistos: set[tuple[str, str]] = set()
        for a, b in _fragmentos(run, brand, todas):
            texto = run.texto_respuesta[a:b]
            analisis = _analizar(texto, brand, todas, vocab)
            tipos: list[TipoAfirmacion] = [t for t in TIPOS if analisis.de_tipo(t)]
            if not tipos and analisis.riesgos:
                tipos = ["otro"]
            for tipo in tipos:
                if (tipo, texto) in vistos:
                    continue
                vistos.add((tipo, texto))
                out.append(_afirmacion(run, brand, texto, tipo, len(vistos), "reglas"))
    return out


def _afirmacion(
    run: Run,
    brand: Brand,
    texto: str,
    tipo: TipoAfirmacion,
    n: int,
    origen: Literal["reglas", "llm"],
) -> Afirmacion:
    sufijo = "" if origen == "reglas" else "-llm"
    return Afirmacion(
        id=f"AF-{run.id}-{brand.id}-{n:02d}{sufijo}-{tipo}",
        texto=texto,
        tipo=tipo,
        brand_id=brand.id,
        evaluation_id=evaluation_id(run, brand),
        run_id=run.id,
        motor=run.motor,
        fuentes_citadas=[s.dominio for s in run.fuentes],
        origen=origen,
    )


# --- Capa opcional con LLM ------------------------------------------------------------------------


class AfirmacionLLM(BaseModel):
    """Una afirmación propuesta por el LLM: fragmento copiado literalmente y su tipo."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    texto: str = Field(min_length=1)
    tipo: TipoAfirmacion


class AfirmacionesLLM(BaseModel):
    """Salida del prompt `claims`: afirmaciones sobre la marca en UNA respuesta."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    afirmaciones: list[AfirmacionLLM] = []


def _marca_estado(b: Brand) -> dict[str, object]:
    return {"nombre": b.nombre, "aliases": list(b.aliases)}


def estado_claims(run: Run, brand: Brand, marcas: Iterable[Brand] = ()) -> dict[str, object]:
    """`state` del prompt `claims`: la respuesta del motor es DATO, nunca va en instrucciones."""
    return {
        "marca": _marca_estado(brand),
        "otras_marcas": [_marca_estado(m) for m in marcas if m.id != brand.id],
        "respuesta": run.texto_respuesta,
        "tipos": list(TIPOS),
    }


def afirmaciones_llm_por_reglas(estado: dict[str, object]) -> AfirmacionesLLM:
    """Salida reproducible del prompt `claims` con las reglas (la usa el LLM de demostración)."""
    marca = Brand.model_validate({**_dict(estado["marca"]), "id": "_foco", "rol": "foco"})
    otras = [
        Brand.model_validate({**_dict(m), "id": f"_otra{i}", "rol": "contexto"})
        for i, m in enumerate(_lista(estado.get("otras_marcas", [])))
    ]
    run = Run(
        id="_claims",
        study_id="_claims",
        prompt_id="_claims",
        motor="ChatGPT",
        repeticion=1,
        fecha=datetime(2000, 1, 1),
        texto_respuesta=str(estado["respuesta"]),
        marcas_a_evaluar=[marca.id],
    )
    return AfirmacionesLLM(
        afirmaciones=[
            AfirmacionLLM(texto=a.texto, tipo=a.tipo)
            for a in extraer_afirmaciones([run], marca, marcas=otras)
        ]
    )


def _dict(valor: object) -> dict[str, object]:
    if not isinstance(valor, dict):
        raise ValueError("estado de claims mal formado: se esperaba un objeto")
    return {str(k): v for k, v in valor.items()}


def _lista(valor: object) -> list[object]:
    if not isinstance(valor, list):
        raise ValueError("estado de claims mal formado: se esperaba una lista")
    return list(valor)


def afirmaciones_desde_llm(salida: AfirmacionesLLM, run: Run, brand: Brand) -> list[Afirmacion]:
    """Convierte la salida del LLM en `Afirmacion` (origen `llm`).

    Se descartan los fragmentos que no son literales de la respuesta (el LLM no puede inventar
    texto) y los repetidos.
    """
    out: list[Afirmacion] = []
    vistos: set[tuple[str, str]] = set()
    for propuesta in salida.afirmaciones:
        texto = propuesta.texto.strip()
        if not texto or texto not in run.texto_respuesta or (propuesta.tipo, texto) in vistos:
            continue
        vistos.add((propuesta.tipo, texto))
        out.append(_afirmacion(run, brand, texto, propuesta.tipo, len(vistos), "llm"))
    return out


def combinar_afirmaciones(
    reglas: Sequence[Afirmacion], llm: Sequence[Afirmacion]
) -> list[Afirmacion]:
    """Las de reglas más las del LLM que no repiten una de reglas (mismo tipo y evaluación, y un
    fragmento contiene al otro)."""
    out = list(reglas)
    for a in llm:
        repetida = any(
            r.evaluation_id == a.evaluation_id
            and r.tipo == a.tipo
            and (fold(a.texto) in fold(r.texto) or fold(r.texto) in fold(a.texto))
            for r in reglas
        )
        if not repetida and all(o.id != a.id for o in out):
            out.append(a)
    return out


# --- Verificación ---------------------------------------------------------------------------------


def _en_brief(clave: str, entradas: Sequence[str]) -> str | None:
    """La entrada del brief que contiene `clave` (plegada, con límite de palabra), si la hay."""
    patron = re.compile(rf"(?<!\w){re.escape(fold(clave))}(?!\w)")
    return next((e for e in entradas if patron.search(fold(e))), None)


def _servicio_en_brief(clave: str, vocab: _Vocabulario, brief: BriefSummary) -> str | None:
    entradas = [*brief.servicios_prioritarios, brief.subsector]
    servicio = next((s for s in vocab.servicios if s.nombre == clave), None)
    for termino in (clave, *(servicio.equivale_a if servicio else ())):
        if (dato := _en_brief(termino, entradas)) is not None:
            return dato
    return None


def _lista_es(valores: Iterable[str]) -> str:
    return ", ".join(f"«{v}»" for v in dict.fromkeys(valores))


def _verificar_hechos(
    tipo: TipoAfirmacion, analisis: _Analisis, vocab: _Vocabulario, brief: BriefSummary
) -> tuple[EstadoVerificacion, str, str | None]:
    terminos = analisis.de_tipo(tipo)
    if tipo == "servicio" and terminos:
        en_brief = {t.clave: _servicio_en_brief(t.clave, vocab, brief) for t in terminos}
        negados = [t for t in terminos if t.negado and en_brief[t.clave]]
        if negados:
            return (
                "incorrecta",
                f"Niega {_lista_es(t.clave for t in negados)}, que el brief recoge.",
                "; ".join(dict.fromkeys(str(en_brief[t.clave]) for t in negados)),
            )
        fuera = [t.clave for t in terminos if t.negado or not en_brief[t.clave]]
        if not fuera:
            return (
                "correcta",
                f"El brief recoge {_lista_es(en_brief)}.",
                "; ".join(dict.fromkeys(str(v) for v in en_brief.values())),
            )
        return (
            "no_verificable",
            f"El brief (servicios prioritarios y subsector) no dice nada de {_lista_es(fuera)}: "
            "no se puede confirmar ni descartar.",
            None,
        )
    if tipo == "sede" and terminos:
        ciudades_brief = ", ".join(brief.ciudades)
        en_brief = {t.clave: _en_brief(t.clave, brief.ciudades) for t in terminos}
        negadas = [t for t in terminos if t.negado and en_brief[t.clave]]
        if negadas:
            return (
                "incorrecta",
                f"Niega presencia en {_lista_es(t.clave for t in negadas)}, que el brief recoge.",
                f"Ciudades del brief: {ciudades_brief}",
            )
        ajenas = [
            t for t in terminos if t.sede_explicita and not t.negado and not en_brief[t.clave]
        ]
        if ajenas and brief.ciudades:
            return (
                "incorrecta",
                f"Sitúa una sede en {_lista_es(t.clave for t in ajenas)}, pero el brief solo "
                f"recoge {ciudades_brief}.",
                f"Ciudades del brief: {ciudades_brief}",
            )
        if all(en_brief[t.clave] and not t.negado for t in terminos):
            return (
                "correcta",
                f"{_lista_es(t.clave for t in terminos)} está entre las ciudades del brief.",
                f"Ciudades del brief: {ciudades_brief}",
            )
        return (
            "no_verificable",
            "Nombra una ciudad que el brief no recoge sin afirmar que tenga sede allí.",
            None,
        )
    if tipo == "profesional" and terminos:
        en_equipo = {t.clave: _en_brief(_apellido(t.clave), brief.equipo) for t in terminos}
        if all(en_equipo.values()):
            return (
                "correcta",
                f"El equipo del brief incluye {_lista_es(en_equipo)}.",
                "; ".join(dict.fromkeys(str(v) for v in en_equipo.values())),
            )
        return (
            "no_verificable",
            "El brief no recoge el equipo médico (nombres ni número de profesionales).",
            None,
        )
    motivos: dict[TipoAfirmacion, str] = {
        "precio": "El brief no trae precios ni financiación.",
        "resultado_clinico": "El brief no trae resultados clínicos.",
        "otro": "Afirmación general sin un dato del brief con qué compararla.",
    }
    return (
        "no_verificable",
        motivos.get(tipo, "No se reconoce ningún término de ese tipo en el fragmento."),
        None,
    )


def _apellido(nombre: str) -> str:
    """Último token de un nombre propio («Dra. Ana Ruiz» → «Ruiz»); el resto, tal cual."""
    if _PROFESIONAL_NOMBRE.fullmatch(nombre):
        return nombre.split()[-1]
    return nombre


def verificar_afirmacion(
    afirmacion: Afirmacion,
    brief: BriefSummary,
    brand: Brand,
    *,
    marcas: Iterable[Brand] = (),
    ciudades: Iterable[str] = (),
) -> Verificacion:
    """Contrasta `afirmacion` con el brief: incorrecta > riesgo > correcta / no_verificable.

    Se vuelve a analizar el fragmento, así que vale igual para afirmaciones de reglas o del LLM.
    """
    vocab = _vocabulario(brief, ciudades)
    analisis = _analizar(afirmacion.texto, brand, _todas(brand, marcas), vocab)
    estado, motivo, dato = _verificar_hechos(afirmacion.tipo, analisis, vocab, brief)
    expresiones = [e.expresion for e in EXPRESIONES_RIESGO if e.id in analisis.riesgos]
    if expresiones and estado != "incorrecta":
        motivo = (
            f"Contiene expresiones {ETIQUETA_RIESGO}: {_lista_es(expresiones)}. "
            f"No es un juicio legal. {motivo}"
        )
        estado = "riesgo_regulatorio"
    return Verificacion(
        afirmacion_id=afirmacion.id,
        estado=estado,
        motivo=motivo,
        dato_brief=dato,
        expresiones_riesgo=expresiones,
    )


def verificar(
    afirmaciones: Iterable[Afirmacion],
    brief: BriefSummary,
    brand: Brand,
    *,
    marcas: Iterable[Brand] = (),
    ciudades: Iterable[str] = (),
) -> list[Verificacion]:
    otras = list(marcas)
    ciud = list(ciudades)
    return [
        verificar_afirmacion(a, brief, brand, marcas=otras, ciudades=ciud) for a in afirmaciones
    ]


def hallazgo_exactitud(
    study_id: str,
    brand_id: str,
    afirmaciones: Sequence[Afirmacion],
    verificaciones: Sequence[Verificacion],
) -> HallazgoExactitud:
    """Resumen con recuentos. Sin afirmaciones, todo a 0: «0 inexactitudes» es resultado válido."""
    cuenta = {e: sum(1 for v in verificaciones if v.estado == e) for e in ESTADOS}
    return HallazgoExactitud(
        id=f"EXACT-{brand_id}",
        study_id=study_id,
        brand_id=brand_id,
        afirmaciones=list(afirmaciones),
        verificaciones=list(verificaciones),
        n_correctas=cuenta["correcta"],
        n_incorrectas=cuenta["incorrecta"],
        n_no_verificables=cuenta["no_verificable"],
        n_riesgo_regulatorio=cuenta["riesgo_regulatorio"],
        evaluation_ids=sorted({a.evaluation_id for a in afirmaciones}),
    )


def recuento(hallazgo: HallazgoExactitud) -> dict[TipoAfirmacion, dict[EstadoVerificacion, int]]:
    """Afirmaciones por tipo y estado (todos los tipos y estados, con ceros)."""
    tipo_de = {a.id: a.tipo for a in hallazgo.afirmaciones}
    out: dict[TipoAfirmacion, dict[EstadoVerificacion, int]] = {
        t: dict.fromkeys(ESTADOS, 0) for t in TIPOS
    }
    for v in hallazgo.verificaciones:
        out[tipo_de[v.afirmacion_id]][v.estado] += 1
    return out


def expresiones_a_revisar(hallazgo: HallazgoExactitud) -> dict[str, int]:
    """Cuántas afirmaciones contienen cada expresión de la lista (en el orden de la lista)."""
    out: dict[str, int] = {}
    for e in EXPRESIONES_RIESGO:
        n = sum(1 for v in hallazgo.verificaciones if e.expresion in v.expresiones_riesgo)
        if n:
            out[e.expresion] = n
    return out


# --- Mitigación -----------------------------------------------------------------------------------

_SIN_FUENTE = ""


def _fuentes_de(afirmacion: Afirmacion) -> list[str]:
    """La fuente del marcador `[n]` del fragmento; si no hay, todas las de la respuesta."""
    marcadas = [
        afirmacion.fuentes_citadas[int(n) - 1]
        for n in re.findall(r"\[(\d+)\]", afirmacion.texto)
        if 1 <= int(n) <= len(afirmacion.fuentes_citadas)
    ]
    return list(dict.fromkeys(marcadas or afirmacion.fuentes_citadas)) or [_SIN_FUENTE]


def _palanca_y_texto(
    dominio: str, fuente: Source | None, brand: Brand, problema: str
) -> tuple[Palanca, str]:
    marca = brand.nombre
    if dominio == _SIN_FUENTE:
        return (
            "entidad_datos",
            f"El motor no citó fuentes. Publicar el dato correcto de {marca} en su web con datos "
            f"estructurados (schema.org: sedes y servicios) y mantenerlo igual en los "
            f"directorios. {problema}",
        )
    tipo = fuente.tipo if fuente else None
    if brand.dominio and fold(dominio) == fold(brand.dominio):
        return "contenido", f"Corregir el contenido propio en {dominio}. {problema}"
    if tipo in ("Directorio / comparador", "Plataforma de reseñas"):
        return (
            "entidad_datos",
            f"Corregir la ficha de {marca} en {dominio} y revisar que nombre, sedes y servicios "
            f"coincidan en todos los directorios. {problema}",
        )
    if tipo == "Red social / foro":
        return (
            "comunidades",
            f"Aclarar el dato con una respuesta oficial de {marca} en {dominio}. {problema}",
        )
    return "autoridad_terceros", f"Solicitar a {dominio} que corrija el dato de {marca}. {problema}"


def acciones_mitigacion(
    afirmaciones: Sequence[Afirmacion],
    verificaciones: Sequence[Verificacion],
    brand: Brand,
    *,
    fuentes: Iterable[Source] = (),
) -> list[AccionMitigacion]:
    """Una acción por fuente de origen de las afirmaciones incorrectas, enlazada a sus evaluaciones.

    `fuentes` es el catálogo (dominio → tipo) para elegir la palanca: directorio o reseñas →
    `entidad_datos`; web propia → `contenido`; foro → `comunidades`; medio, ranking o desconocido →
    `autoridad_terceros`; sin fuente → `entidad_datos` (datos estructurados en la web).
    """
    catalogo = {s.dominio: s for s in fuentes}
    por_id = {a.id: a for a in afirmaciones}
    grupos: dict[str, list[tuple[Afirmacion, Verificacion]]] = {}
    for v in verificaciones:
        if v.estado != "incorrecta" or v.afirmacion_id not in por_id:
            continue
        a = por_id[v.afirmacion_id]
        for dominio in _fuentes_de(a):
            grupos.setdefault(dominio, []).append((a, v))
    acciones: list[AccionMitigacion] = []
    for i, dominio in enumerate(sorted(grupos), start=1):
        pares = grupos[dominio]
        problema = " ".join(dict.fromkeys(v.motivo for _, v in pares))
        palanca, descripcion = _palanca_y_texto(dominio, catalogo.get(dominio), brand, problema)
        acciones.append(
            AccionMitigacion(
                id=f"MIT-{brand.id}-{i:02d}-{slugify(dominio) or 'sin-fuente'}",
                afirmacion_ids=[a.id for a, _ in pares],
                fuente_dominio=dominio or None,
                palanca=palanca,
                descripcion=descripcion,
                evaluation_ids=sorted({a.evaluation_id for a, _ in pares}),
            )
        )
    return acciones


# --- Todo junto -----------------------------------------------------------------------------------


def evaluar_exactitud(
    study_id: str,
    brand: Brand,
    brief: BriefSummary,
    runs: Sequence[Run],
    *,
    marcas: Iterable[Brand] = (),
    ciudades: Iterable[str] = (),
    afirmaciones_llm: Sequence[Afirmacion] = (),
) -> tuple[HallazgoExactitud, list[AccionMitigacion]]:
    """Extracción por reglas (+ las del LLM que no repiten), verificación, hallazgo y mitigación.

    Solo tiene sentido para la marca del brief: el brief es la verdad con la que se compara. Para un
    competidor no hay datos propios y compararlo con este brief daría estados sin sentido.

    El catálogo de fuentes para la mitigación sale de las propias ejecuciones (`Run.fuentes`).
    """
    otras = list(marcas)
    ciud = list(ciudades)
    reglas = extraer_afirmaciones(runs, brand, brief, marcas=otras, ciudades=ciud)
    afirmaciones = combinar_afirmaciones(reglas, afirmaciones_llm)
    verificaciones = verificar(afirmaciones, brief, brand, marcas=otras, ciudades=ciud)
    hallazgo = hallazgo_exactitud(study_id, brand.id, afirmaciones, verificaciones)
    fuentes = [s for r in runs for s in r.fuentes]
    return hallazgo, acciones_mitigacion(afirmaciones, verificaciones, brand, fuentes=fuentes)
