"""Esquemas del dominio de posiq.: única fuente de verdad de los datos que circulan entre nodos.

Contrato compartido: cambiarlo requiere PR con etiqueta `contract-change` (ver CONTRIBUTING.md).
Las categorías siguen el diccionario de datos y la metodología del kit (`data/kit/03_*`).
"""

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

# --- Categorías -----------------------------------------------------------------------------------

Rol = Literal["foco", "contexto", "lider"]
FaseEmbudo = Literal["descubrimiento", "comparacion", "validacion", "decision"]
Familia = Literal[
    "Descubrimiento genérico",
    "Descubrimiento por perfil",
    "Localización",
    "Comparación de opciones",
    "Comparación de marcas",
    "Validación reputacional",
    "Fuentes y citación",
    "Decisión final",
    "Precio y valor",
]
Instanciacion = Literal["generico", "ciudad", "marca", "par"]
TipoVisibilidad = Literal["espontaneo", "asistido"]
Prioridad = Literal["P1", "P2"]
Uso = Literal["Publicable", "Diagnóstico"]
Motor = Literal["ChatGPT", "Gemini", "Perplexity", "Claude"]
TipoMencion = Literal["Recomendación activa", "Comparación neutra", "Pasiva"]
Sentimiento = Literal["positivo", "neutro", "negativo"]
TipoFuenteCatalogo = Literal[
    "Ranking / institución",
    "Medio",
    "Web propia",
    "Directorio / comparador",
    "Plataforma de reseñas",
    "Red social / foro",
]
TipoFuente = TipoFuenteCatalogo | Literal["Sin fuente"]
OrigenEvaluacion = Literal["jev", "fallback", "humano"]
OrigenDatos = Literal["kit", "api"]
ModoEstudio = Literal["kit", "real"]
EstadoEstudio = Literal[
    "en_curso",
    "esperando_revision_competidores",
    "esperando_revision_plan",
    "completado",
]
Talla = Literal["S", "M", "L"]
Palanca = Literal[
    "autoridad_terceros",
    "entidad_datos",
    "contenido",
    "reputacion",
    "comunidades",
    "tecnico",
    "medicion",
]

ESPONTANEAS: frozenset[str] = frozenset({"generico", "ciudad"})


def tipo_de_instanciacion(instanciacion: Instanciacion) -> TipoVisibilidad:
    """`generico`/`ciudad` no nombran la marca (espontáneo); `marca`/`par` sí (asistido)."""
    return "espontaneo" if instanciacion in ESPONTANEAS else "asistido"


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# --- Marca, brief y mercado -----------------------------------------------------------------------


class Brand(_Model):
    id: str
    nombre: str
    aliases: list[str] = []
    rol: Rol
    dominio: str | None = None
    rol_detalle: str = ""


class BriefSummary(_Model):
    """Ficha estructurada del brief. `ciudades` va ordenada por prioridad (primera = principal)."""

    marca: str
    sector: str
    subsector: str
    servicios_prioritarios: list[str]
    publicos: list[str]
    ciudades: list[str]
    competidores_declarados: list[str]
    presupuesto_anual_eur: tuple[int, int] | None = None
    equipo: list[str]
    restricciones: list[str]
    objetivos: list[str]
    audiencia_del_entregable: str
    tono: str

    @model_validator(mode="after")
    def _presupuesto_ordenado(self) -> Self:
        if (
            self.presupuesto_anual_eur
            and self.presupuesto_anual_eur[0] > self.presupuesto_anual_eur[1]
        ):
            raise ValueError("presupuesto_anual_eur debe ser (mínimo, máximo)")
        return self


class Market(_Model):
    marcas: list[Brand]
    confirmado_por_humano: bool = False

    @model_validator(mode="after")
    def _ids_unicos(self) -> Self:
        ids = [b.id for b in self.marcas]
        if len(ids) != len(set(ids)):
            raise ValueError("Market.marcas tiene ids repetidos")
        return self


class Study(_Model):
    """Un estudio: una medición de una marca en una fecha. Todo resultado lleva su `study_id`."""

    id: str
    brand_id: str
    brief: BriefSummary
    modo: ModoEstudio
    creado_en: datetime
    version_metodologia: str
    score_version: str
    estado: EstadoEstudio = "en_curso"


# --- Prompts, fuentes y ejecuciones ---------------------------------------------------------------


class PromptTemplate(_Model):
    id: str
    familia: Familia
    fase_embudo: FaseEmbudo
    instanciacion: Instanciacion
    texto: str
    prioridad: Prioridad
    uso: Uso = "Publicable"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tipo(self) -> TipoVisibilidad:
        return tipo_de_instanciacion(self.instanciacion)


class PromptInstance(_Model):
    """Prompt ya instanciado. `marca_nombrada` es `[MARCA_A]`; `marca_nombrada_b`, `[MARCA_B]`."""

    id: str
    template_id: str
    familia: Familia
    fase_embudo: FaseEmbudo
    instanciacion: Instanciacion
    perfil: str | None = None
    ciudad: str | None = None
    texto: str
    marca_nombrada: str | None = None
    marca_nombrada_b: str | None = None
    prioridad: Prioridad

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tipo(self) -> TipoVisibilidad:
        return tipo_de_instanciacion(self.instanciacion)


class Source(_Model):
    """Dominio citado. `tipo` y `calidad` son None si el dominio no está en el catálogo."""

    dominio: str
    tipo: TipoFuenteCatalogo | None = None
    calidad: float | None = Field(default=None, ge=0, le=1)


class Run(_Model):
    """Un prompt lanzado a un motor en una repetición. `fuentes` vacía = sin búsqueda web."""

    id: str
    study_id: str
    prompt_id: str
    motor: Motor
    modelo: str | None = None
    repeticion: int = Field(ge=1)
    fecha: datetime
    texto_respuesta: str
    fuentes: list[Source] = []
    marcas_a_evaluar: list[str] = Field(min_length=1)
    coste_eur: float = Field(default=0.0, ge=0)
    tokens: int | None = Field(default=None, ge=0)
    origen: OrigenDatos = "kit"


# --- Evaluación -----------------------------------------------------------------------------------


class Detection(_Model):
    """Detección por reglas de una marca en un texto. `span` = primera aparición (inicio, fin)."""

    brand_id: str
    posicion: int = Field(ge=1)
    span: tuple[int, int]
    menciones: int = Field(default=1, ge=1)


def peso_posicion(posicion: int | None) -> int:
    """Peso de la metodología: 1.ª = 3 · 2.ª-3.ª = 2 · 4.ª o más = 1 · no aparece = 0."""
    if posicion is None:
        return 0
    if posicion == 1:
        return 3
    return 2 if posicion <= 3 else 1


class Evaluation(_Model):
    """Una marca evaluada en una ejecución (una fila de `muestra_evaluada.csv`).

    `fuerza` sigue el kit: 3 principal · 2 positiva secundaria · 1 neutra · 0 no aparece ·
    -1 aparece con advertencia o percepción negativa. `tipo_fuente` None = no resuelto.
    `necesita_revision`: el juez respondió con confianza entre los umbrales de fallback y de
    aceptación; la evaluación se usa, pero conviene que la revise una persona.
    """

    id: str
    study_id: str
    run_id: str
    brand_id: str
    aparece: bool
    posicion: int | None = Field(default=None, ge=1)
    tipo_mencion: TipoMencion | None = None
    fuerza: int = Field(ge=-1, le=3)
    sentimiento: Sentimiento | None = None
    tipo_fuente: TipoFuente | None = None
    apoyada_en_fuente: bool = False
    confianza: float = Field(ge=0, le=1)
    origen: OrigenEvaluacion
    necesita_revision: bool = False

    @model_validator(mode="after")
    def _coherente_con_aparicion(self) -> Self:
        if self.aparece:
            if self.posicion is None:
                raise ValueError("una marca que aparece necesita posicion")
            if self.fuerza == 0:
                raise ValueError("fuerza 0 está reservada a «no aparece»")
        else:
            if self.posicion is not None or self.fuerza != 0:
                raise ValueError("si no aparece: posicion vacía y fuerza 0")
            if self.tipo_mencion or self.sentimiento:
                raise ValueError("si no aparece: sin tipo_mencion ni sentimiento")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def peso_posicion(self) -> int:
        return peso_posicion(self.posicion)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def por_desconocimiento(self) -> bool:
        """El motor la nombra para decir que no la conoce: Pasiva, fuerza 1 y sin fuente."""
        return (
            self.aparece
            and self.tipo_mencion == "Pasiva"
            and self.fuerza == 1
            and self.tipo_fuente == "Sin fuente"
        )


# --- Métricas -------------------------------------------------------------------------------------


class ScoreBreakdown(_Model):
    """Score de Citación de una marca (opcionalmente en un motor). None = sin datos (n = 0)."""

    brand_id: str
    motor: Motor | None = None
    n_evaluaciones: int = Field(ge=0)
    aparicion: float | None = None
    posicion: float | None = None
    fuerza: float | None = None
    calidad_fuente: float | None = None
    score: float | None = Field(default=None, ge=0, le=100)
    score_version: str


Dimension = Literal["global", "motor", "fase", "ciudad", "perfil", "familia"]


class VisibilityCell(_Model):
    """Visibilidad de una marca en un segmento. `tasa` None = sin datos, nunca 0 %."""

    brand_id: str
    tipo: TipoVisibilidad
    dimension: Dimension
    valor: str
    n: int = Field(ge=0)
    apariciones: int = Field(ge=0)
    tasa: float | None = Field(default=None, ge=0, le=1)
    fuerza_media: float | None = None
    evaluation_ids: list[str] = []


class MentionQuality(_Model):
    """Calidad de las menciones de una marca: recuentos sobre sus apariciones."""

    brand_id: str
    tipo: TipoVisibilidad
    apariciones: int = Field(ge=0)
    fuerza_media: float | None = None
    por_tipo_mencion: dict[str, int] = {}
    por_sentimiento: dict[str, int] = {}
    por_desconocimiento: int = 0
    negativas: int = 0
    desconocimiento_ids: list[str] = []
    negativas_ids: list[str] = []


class SourceStat(_Model):
    """Dominio citado en ejecuciones donde la marca aparece."""

    brand_id: str
    dominio: str
    tipo: TipoFuenteCatalogo | None = None
    calidad: float | None = None
    apariciones: int = Field(ge=0)


class SourceGap(_Model):
    """Dominio que acompaña al líder más que a la marca foco (ejecuciones espontáneas)."""

    dominio: str
    tipo: TipoFuenteCatalogo | None = None
    con_lider: int = Field(ge=0)
    con_marca: int = Field(ge=0)
    brecha: int
    lider_sin_marca: int = Field(ge=0)
    evaluation_ids: list[str] = []


class Metrics(_Model):
    """Métricas del estudio. La visibilidad espontánea y la asistida van SIEMPRE separadas.

    `comparado_con` es el `study_id` de una medición anterior con la que se compara, si la hay.
    """

    study_id: str
    comparado_con: str | None = None
    score_version: str
    marca_foco_id: str
    lider_id: str | None
    score_global: ScoreBreakdown
    scores: list[ScoreBreakdown]
    scores_por_motor: list[ScoreBreakdown]
    ranking: list[str]
    visibilidad: list[VisibilityCell]
    calidad_menciones: list[MentionQuality]
    top_fuentes: list[SourceStat]
    brecha_fuentes: list[SourceGap]
    n_ejecuciones: dict[str, int]

    def cell(
        self, brand_id: str, tipo: TipoVisibilidad, dimension: Dimension, valor: str
    ) -> VisibilityCell | None:
        for c in self.visibilidad:
            if (c.brand_id, c.tipo, c.dimension, c.valor) == (brand_id, tipo, dimension, valor):
                return c
        return None

    def cells(
        self, brand_id: str, tipo: TipoVisibilidad, dimension: Dimension
    ) -> list[VisibilityCell]:
        return [
            c
            for c in self.visibilidad
            if c.brand_id == brand_id and c.tipo == tipo and c.dimension == dimension
        ]

    def score_of(self, brand_id: str) -> ScoreBreakdown | None:
        return next((s for s in self.scores if s.brand_id == brand_id), None)


class VisibilityDelta(_Model):
    """Cambio de la tasa de un segmento entre dos mediciones. `delta` None si falta un lado."""

    brand_id: str
    tipo: TipoVisibilidad
    dimension: Dimension
    valor: str
    tasa_actual: float | None
    tasa_anterior: float | None
    delta: float | None
    n_actual: int = Field(ge=0)
    n_anterior: int = Field(ge=0)


class MetricsDelta(_Model):
    """Diferencia entre dos mediciones de la misma marca (base de la re-medición).

    `comparable` es False si cambia la versión del score; `avisos` explica cada incompatibilidad.
    """

    study_id: str
    comparado_con: str
    marca_foco_id: str
    score_actual: float | None
    score_anterior: float | None
    score_delta: float | None
    visibilidad_delta: list[VisibilityDelta]
    comparable: bool
    avisos: list[str] = []


# --- Hallazgos, plan y propuesta ------------------------------------------------------------------


class Finding(_Model):
    id: str
    study_id: str
    titulo: str
    descripcion: str
    fase_embudo: FaseEmbudo | None = None
    impacto: Talla
    confianza: float = Field(ge=0, le=1)
    cifra: float
    origen_cifra: str
    evaluation_ids: list[str] = Field(min_length=1)


class Objective(_Model):
    kpi: str
    valor_actual: float
    valor_objetivo: float
    plazo_semanas: int = Field(ge=1)


class Action(_Model):
    """Acción del plan. `restricciones_revisadas` lista las restricciones del brief que respeta."""

    id: str
    descripcion: str
    finding_ids: list[str] = Field(min_length=1)
    palanca: Palanca
    fase_embudo: FaseEmbudo | None = None
    motores_objetivo: list[Motor] = []
    esfuerzo: Talla
    impacto: Talla
    responsable: str
    dependencias: list[str] = []
    entregables: list[str] = Field(min_length=1)
    plazo_semanas: int = Field(ge=1)
    kpi: str
    restricciones_revisadas: list[str] = []


class Phase(_Model):
    nombre: str
    semanas: int = Field(ge=1)
    objetivo: str
    acciones: list[Action]


class Plan(_Model):
    """Plan por fases. Sus acciones pertenecen al estudio del plan (`study_id`)."""

    study_id: str
    objetivos: list[Objective]
    fases: list[Phase]
    presupuesto_estimado_eur: float = Field(ge=0)
    respeta_restricciones: bool

    @property
    def acciones(self) -> list[Action]:
        return [a for f in self.fases for a in f.acciones]


def validate_plan_against_brief(plan: Plan, brief: BriefSummary) -> list[str]:
    """Violaciones del plan frente al brief. No lanza: devuelve una lista (vacía si cumple).

    - El presupuesto estimado supera el máximo del brief.
    - Una acción no declara en `restricciones_revisadas` alguna restricción del brief.
    - El plan se declara a sí mismo como no respetuoso con las restricciones.
    """
    violaciones: list[str] = []
    if (
        brief.presupuesto_anual_eur
        and plan.presupuesto_estimado_eur > brief.presupuesto_anual_eur[1]
    ):
        violaciones.append(
            f"presupuesto estimado {plan.presupuesto_estimado_eur:.0f} € supera el máximo "
            f"del brief ({brief.presupuesto_anual_eur[1]} €)"
        )
    for accion in plan.acciones:
        for restriccion in brief.restricciones:
            if restriccion not in accion.restricciones_revisadas:
                violaciones.append(f"acción {accion.id} ignora la restricción «{restriccion}»")
    if not plan.respeta_restricciones:
        violaciones.append("el plan declara que no respeta las restricciones del brief")
    return violaciones


class Contexto(_Model):
    marca: str
    sector: str
    motores: list[Motor]
    fecha: datetime
    origen_datos: OrigenDatos
    datos_sinteticos: bool
    limitaciones: list[str] = Field(min_length=1)


class Diagnostico(_Model):
    texto: str
    metrics: Metrics


class Competencia(_Model):
    texto: str
    ranking: list[str]


class Estrategia(_Model):
    texto: str
    objetivos: list[Objective]
    prioridades: list[str]


class Medicion(_Model):
    kpis: list[str] = Field(min_length=1)
    metodologia: str
    cadencia: str


class Riesgo(_Model):
    riesgo: str
    mitigacion: str


class Hito(_Model):
    semana: int = Field(ge=0)
    descripcion: str


class HojaRuta(_Model):
    hitos: list[Hito]
    responsabilidades: dict[str, list[str]]
    presupuesto_eur: float = Field(ge=0)
    seguimiento: str


class Proposal(_Model):
    """Las 10 secciones del formato del entregable (doc 06), todas del mismo estudio."""

    study_id: str
    resumen_ejecutivo: str
    contexto: Contexto
    diagnostico: Diagnostico
    competencia: Competencia
    hallazgos: list[Finding] = Field(min_length=3, max_length=7)
    estrategia: Estrategia
    plan: Plan
    medicion: Medicion
    riesgos: list[Riesgo] = Field(min_length=1)
    hoja_ruta: HojaRuta

    @model_validator(mode="after")
    def _mismo_estudio(self) -> Self:
        ajenos = [f.id for f in self.hallazgos if f.study_id != self.study_id]
        if ajenos:
            raise ValueError(f"hallazgos de otro estudio: {ajenos}")
        if self.plan.study_id != self.study_id:
            raise ValueError("el plan (y sus acciones) es de otro estudio")
        if self.diagnostico.metrics.study_id != self.study_id:
            raise ValueError("las métricas del diagnóstico son de otro estudio")
        return self

    @model_validator(mode="after")
    def _acciones_enlazadas(self) -> Self:
        ids = {f.id for f in self.hallazgos}
        for accion in self.plan.acciones:
            sueltos = set(accion.finding_ids) - ids
            if sueltos:
                raise ValueError(
                    f"acción {accion.id} enlaza hallazgos inexistentes: {sorted(sueltos)}"
                )
        return self


# --- Trazas ---------------------------------------------------------------------------------------


class Trace(_Model):
    study_id: str
    nodo: str
    modelo: str
    prompt_version: str
    tokens_in: int = Field(ge=0)
    tokens_out: int = Field(ge=0)
    coste_eur: float = Field(ge=0)
    duracion_ms: int = Field(ge=0)
    fecha: datetime
