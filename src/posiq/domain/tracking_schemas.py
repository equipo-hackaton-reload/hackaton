"""Modelos del seguimiento con método: la serie temporal de mediciones de una marca (ADR 0016).

Viven fuera de `schemas.py` para no tocar el contrato compartido. Las cifras las calcula
`domain/tracking.py` (código determinista, bootstrap con semilla fija); estos modelos solo las
transportan. Los consumen la API de seguimiento (zona C) y la web (zona D).
"""

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from posiq.domain.schemas import BriefSummary, Market, Motor, UnidadCifra
from posiq.domain.stats_schemas import Intervalo, Significancia


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


QueCambia = Literal["perfil", "mercado"]
"""Parte de la configuración de la marca que cambia entre dos mediciones."""


class NucleoComun(_Model):
    """Comparación de un punto con el anterior sobre las preguntas comunes a los dos bancos.

    Solo existe si el banco de prompts cambió (creció o se recortó) y aún quedan preguntas comunes.
    La clave de una pregunta (`tracking.clave_pregunta`) es todo lo que se pregunta: plantilla,
    familia, fase, instanciación, perfil, ciudad, texto, marcas nombradas y prioridad (los mismos
    campos que la huella del banco, sin el id de instancia). Los cambios de la serie entre estos dos
    puntos se calculan sobre este núcleo (`CambioSerie.sobre_nucleo_comun`); el score del banco
    completo (`PuntoSerie.score`) se informa aparte y no se compara.
    """

    huella: str
    n_prompts_comunes: int = Field(ge=1)
    n_prompts_anterior: int = Field(ge=1)
    n_prompts_actual: int = Field(ge=1)
    score_anterior: float | None
    score_actual: float | None

    @model_validator(mode="after")
    def _coherente(self) -> Self:
        if self.n_prompts_comunes > min(self.n_prompts_anterior, self.n_prompts_actual):
            raise ValueError("el núcleo común no puede tener más preguntas que un banco")
        return self


class PuntoSerie(_Model):
    """Una medición de la serie: el estudio de una fecha con su score, su margen y su contexto.

    - `score`/`intervalo`: Score de Citación de la marca y su IC bootstrap al 95 % (None sin datos).
    - `posicion`: puesto en el ranking del mercado de ese estudio (1 = primero), de `n_marcas`.
    - `score_medio_competidores`: media del score del resto de marcas del mercado con datos.
      `diferencia_vs_competidores` = score − esa media (negativa = por debajo).
    - `banco_prompts`: huella del banco de prompts (`tracking.huella_banco`).
    - `modelos_motor`: modelo de cada motor según `Run.modelo` (solo los motores que lo declaran).
    - `comparable_con_anterior`: si se puede comparar con el punto anterior de la serie. El primero
      nunca lo es (es la línea base) y lo dice en `motivos_no_comparable`.
    - `avisos`: cosas que no rompen la comparabilidad pero hay que leer (p. ej. cambio de modelo).
    - `marcas_mercado`: brand_ids del mercado del estudio, ordenados (vacío = no consta). Si
      cambian respecto al punto anterior, el score y la aparición siguen siendo comparables, pero
      el puesto y la diferencia frente a los competidores no: `competidores_comparables = False` y
      el motivo («Cambian los competidores del mercado: …») va en `avisos`.
    - `juez`: quién evaluó las respuestas, «proveedor/modelo» (`tracking.juez_medicion`). Si cambia
      respecto al punto anterior, no es comparable («Cambia el juez …»). None = no consta.
    - `nucleo_comun`: si el banco cambió pero quedan preguntas comunes, la comparación con el
      anterior se hace sobre ellas (ver `NucleoComun`).
    - `version_perfil` / `version_mercado`: versión de la configuración de la marca vigente en la
      fecha de la medición (None = no consta). Un cambio de mercado hace no comparables el puesto y
      la diferencia frente a los competidores; un cambio de perfil no afecta al score.
    """

    study_id: str
    fecha: datetime
    score: float | None
    intervalo: Intervalo | None
    posicion: int | None = Field(default=None, ge=1)
    n_marcas: int = Field(ge=0)
    score_medio_competidores: float | None
    diferencia_vs_competidores: float | None
    version_metodologia: str
    score_version: str
    banco_prompts: str
    motores: list[Motor]
    modelos_motor: dict[Motor, str] = {}
    comparable_con_anterior: bool
    motivos_no_comparable: list[str] = []
    avisos: list[str] = []
    marcas_mercado: list[str] = []
    competidores_comparables: bool = True
    juez: str | None = None
    nucleo_comun: NucleoComun | None = None
    version_perfil: str | None = None
    version_mercado: str | None = None

    @model_validator(mode="after")
    def _motivos(self) -> Self:
        if self.comparable_con_anterior and self.motivos_no_comparable:
            raise ValueError("un punto comparable no lleva motivos de no comparabilidad")
        if not self.comparable_con_anterior and not self.motivos_no_comparable:
            raise ValueError("un punto no comparable necesita al menos un motivo")
        if self.nucleo_comun is not None and not self.comparable_con_anterior:
            raise ValueError("el núcleo común solo existe si el punto se compara con el anterior")
        return self


class CambioSerie(_Model):
    """Cambio de una métrica entre dos puntos consecutivos y comparables de la serie.

    `metrica`: `score`, `aparicion_espontanea:global`, `aparicion_espontanea:<Motor>`, `posicion`
    o `diferencia_vs_competidores`. `delta` = valor en `hasta` − valor en `desde` (en puntos de
    score, en fracción para las tasas y en puestos para la posición: negativo = mejora).
    `significativo` es True solo si hay `significancia` y su intervalo al 95 % excluye 0.
    `relativo_a_competidores`: la métrica compara la marca con el resto del mercado.
    `texto`: frase determinista en español (plantilla), con coma decimal.
    `sobre_nucleo_comun`: el cambio se calculó solo con las preguntas comunes a los dos bancos.
    """

    desde_study_id: str
    hasta_study_id: str
    metrica: str
    delta: float
    significancia: Significancia | None
    significativo: bool
    relativo_a_competidores: bool = False
    sobre_nucleo_comun: bool = False
    texto: str = Field(min_length=1)

    @model_validator(mode="after")
    def _coherente(self) -> Self:
        esperado = self.significancia.significativa if self.significancia else False
        if self.significativo != esperado:
            raise ValueError("significativo debe coincidir con la significancia (False si no hay)")
        if self.significancia is not None and self.significancia.delta != self.delta:
            raise ValueError("el delta debe ser el de la significancia")
        return self


class ValorIndicador(_Model):
    """Valor de un indicador en un estudio. None = no hay datos para calcularlo (nunca 0)."""

    study_id: str
    valor: float | None


class IndicadorAdelantado(_Model):
    """Indicador que se mueve antes que el score, con un valor por punto de la serie (en orden)."""

    clave: str
    nombre: str
    unidad: UnidadCifra
    valores: list[ValorIndicador]


class CambioConfiguracion(_Model):
    """Cambio de la configuración de la marca entre un punto y el anterior (marca vertical en el
    gráfico, en `study_id`). Solo se declara si las dos versiones constan y son distintas."""

    study_id: str
    que_cambia: list[QueCambia] = Field(min_length=1)
    texto: str = Field(min_length=1)

    @model_validator(mode="after")
    def _sin_repetidos(self) -> Self:
        if len(set(self.que_cambia)) != len(self.que_cambia):
            raise ValueError("que_cambia no admite repetidos")
        return self


class VersionPerfil(_Model):
    """Una versión del perfil de la marca, vigente desde `vigente_desde` (nunca se sobrescribe)."""

    version: str = Field(min_length=1)
    vigente_desde: datetime
    perfil: BriefSummary


class VersionMercado(_Model):
    """Una versión del mercado (competidores) de la marca, vigente desde `vigente_desde`."""

    version: str = Field(min_length=1)
    vigente_desde: datetime
    mercado: Market


class SerieMarca(_Model):
    """Serie temporal de una marca: puntos ordenados por fecha, cambios y resumen.

    `cambios` solo existen entre puntos consecutivos comparables. `cambios_significativos` es el
    subconjunto que sale del margen de error. `cambios_configuracion`: dónde cambian el perfil o el
    mercado (marcas verticales del gráfico). `resumen` (`tracking.construir_serie`): con un solo
    punto, «Línea base: aún no hay con qué comparar.»; por cada par no comparable, «No comparable
    con la medición anterior: <motivos>»; por cada cambio de competidores, su motivo; y los textos
    de los cambios significativos. «Sin cambios fuera del margen de error» solo si se calculó algún
    cambio y ninguno es significativo.
    """

    brand_id: str
    nombre: str
    puntos: list[PuntoSerie]
    cambios: list[CambioSerie]
    cambios_significativos: list[CambioSerie]
    indicadores: list[IndicadorAdelantado]
    resumen: list[str] = Field(min_length=1)
    cambios_configuracion: list[CambioConfiguracion] = []

    @model_validator(mode="after")
    def _coherente(self) -> Self:
        fechas = [p.fecha for p in self.puntos]
        if fechas != sorted(fechas):
            raise ValueError("los puntos de la serie van ordenados por fecha")
        ids = [p.study_id for p in self.puntos]
        if len(ids) != len(set(ids)):
            raise ValueError("la serie tiene estudios repetidos")
        if any(not c.significativo or c not in self.cambios for c in self.cambios_significativos):
            raise ValueError("cambios_significativos debe ser el subconjunto significativo")
        conocidos = set(ids)
        for c in self.cambios:
            if {c.desde_study_id, c.hasta_study_id} - conocidos:
                raise ValueError(f"cambio {c.metrica} entre estudios que no están en la serie")
        for ind in self.indicadores:
            if [v.study_id for v in ind.valores] != ids:
                raise ValueError(f"el indicador {ind.clave} necesita un valor por punto, en orden")
        for cc in self.cambios_configuracion:
            if cc.study_id not in conocidos:
                raise ValueError(f"cambio de configuración en {cc.study_id}, fuera de la serie")
        return self
