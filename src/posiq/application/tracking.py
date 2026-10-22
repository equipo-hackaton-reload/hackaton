"""Seguimiento por marca (zona C): configuración versionada, serie, re-medición y acciones.

posiq. es la herramienta del consultor: cada usuario lleva varias marcas. El estudio inicial es la
línea base; cada re-medición añade un punto a la serie de la marca (`domain.tracking`).

- **Configuración versionada (ADR 0016):** el perfil de la marca y su mercado se editan por
  versiones con `vigente_desde`; nunca se sobrescriben. Si una marca aún no tiene versiones, la v1
  se crea con el brief y el mercado confirmado de su primer estudio, vigente desde esa fecha. Una
  re-medición usa la configuración VIGENTE y guarda en el estudio las versiones usadas: la serie
  marca dónde cambian (`SerieMarca.cambios_configuracion`).
- **Aviso de impacto:** al guardar una versión se dice qué pasará en la serie, con las reglas de
  comparabilidad del ADR 0016 (sin cifras: las cifras las calcula `domain/` al medir).
- **Caso sintético:** los estudios del kit son ficticios (`datos_sinteticos`). La serie nunca
  mezcla mediciones del kit con mediciones reales.

Este módulo no calcula cifras: la serie la construye `domain.tracking.construir_serie`.
"""

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from posiq.domain.schemas import Brand, BriefSummary, Market, ModoEstudio

EstadoAccion = Literal["pendiente", "en_curso", "hecha"]
TipoConfig = Literal["perfil", "mercado"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PerfilMarca(_Model):
    """Lo editable del perfil de la marca: la parte del brief que el consultor mantiene al día."""

    servicios: list[str] = []
    ciudades: list[str] = []
    publicos: list[str] = []
    posicionamiento_deseado: str = ""
    atributos_deseados: list[str] = []
    restricciones: list[str] = []
    presupuesto_anual_eur: tuple[int, int] | None = None

    @model_validator(mode="after")
    def _presupuesto(self) -> "PerfilMarca":
        p = self.presupuesto_anual_eur
        if p and (p[0] < 0 or p[0] > p[1]):
            raise ValueError("presupuesto_anual_eur debe ser (mínimo, máximo), no negativo")
        return self


class VersionPerfilMarca(_Model):
    version: str
    vigente_desde: datetime
    perfil: PerfilMarca


class VersionMercadoMarca(_Model):
    version: str
    vigente_desde: datetime
    marcas: list[Brand]


class PerfilBody(_Model):
    perfil: PerfilMarca


class MercadoBody(_Model):
    marcas: list[Brand] = Field(min_length=2)


class VersionCreada(_Model):
    version: str
    vigente_desde: datetime
    aviso_impacto: list[str]


class EstadoAccionGuardado(_Model):
    estado: EstadoAccion
    nota: str | None = None
    actualizado_en: datetime


class AccionBody(_Model):
    estado: EstadoAccion
    nota: str | None = Field(default=None, max_length=2000)


class AccionActualizada(EstadoAccionGuardado):
    action_id: str


class ConfigEstudio(_Model):
    """Versiones de la configuración con las que se midió un estudio, y a quién re-mide."""

    version_perfil: str | None = None
    version_mercado: str | None = None
    remedicion_de: str | None = None


# --- Puerto del repositorio -----------------------------------------------------------------------


class TrackingRepo(Protocol):
    def config_versions(
        self, tipo: TipoConfig, user_id: str, brand_id: str
    ) -> list[tuple[str, datetime, str]]:
        """(version, vigente_desde, json) en orden de `vigente_desde`."""
        ...

    def add_config_version(
        self,
        tipo: TipoConfig,
        user_id: str,
        brand_id: str,
        version: str,
        vigente_desde: datetime,
        data: str,
    ) -> None: ...

    def set_study_config(self, study_id: str, config: ConfigEstudio) -> None: ...

    def study_config(self, study_id: str) -> ConfigEstudio | None: ...

    def remeasures_of(self, study_id: str) -> list[str]: ...

    def add_action_status(
        self, study_id: str, action_id: str, user_id: str, estado: EstadoAccionGuardado
    ) -> None: ...

    def action_statuses(self, study_id: str) -> dict[str, EstadoAccionGuardado]:
        """El último estado de cada acción (el historial completo queda guardado)."""
        ...


# --- Reglas puras (sin cifras) --------------------------------------------------------------------


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def perfil_de_brief(brief: BriefSummary) -> PerfilMarca:
    return PerfilMarca(
        servicios=list(brief.servicios_prioritarios),
        ciudades=list(brief.ciudades),
        publicos=list(brief.publicos),
        posicionamiento_deseado=brief.posicionamiento_deseado,
        atributos_deseados=list(brief.atributos_deseados),
        restricciones=list(brief.restricciones),
        presupuesto_anual_eur=brief.presupuesto_anual_eur,
    )


def aplicar_perfil(brief: BriefSummary, perfil: PerfilMarca) -> BriefSummary:
    """El brief con el perfil vigente (lo demás, marca, sector, objetivos…, no cambia)."""
    return brief.model_copy(
        update={
            "servicios_prioritarios": list(perfil.servicios),
            "ciudades": list(perfil.ciudades),
            "publicos": list(perfil.publicos),
            "posicionamiento_deseado": perfil.posicionamiento_deseado,
            "atributos_deseados": list(perfil.atributos_deseados),
            "restricciones": list(perfil.restricciones),
            "presupuesto_anual_eur": perfil.presupuesto_anual_eur,
        }
    )


def cambia_el_banco(anterior: PerfilMarca, nuevo: PerfilMarca) -> bool:
    """Servicios, ciudades o públicos instancian las preguntas: si cambian, cambia el banco."""
    return (
        set(anterior.servicios) != set(nuevo.servicios)
        or set(anterior.ciudades) != set(nuevo.ciudades)
        or set(anterior.publicos) != set(nuevo.publicos)
    )


def siguiente_version(versiones: Sequence[str]) -> str:
    return f"v{len(versiones) + 1}"


def siguiente_inicio(ahora: datetime, ultimo: datetime | None) -> datetime:
    """`vigente_desde` estrictamente posterior a la versión anterior (dos no empiezan a la vez)."""
    ahora = as_utc(ahora)
    if ultimo is not None and ahora <= as_utc(ultimo):
        return as_utc(ultimo) + timedelta(microseconds=1)
    return ahora


def _lista(valores: Iterable[str]) -> str:
    return ", ".join(sorted(valores))


def aviso_perfil(
    anterior: PerfilMarca | None, nuevo: PerfilMarca, version: str, modo: ModoEstudio | None
) -> list[str]:
    """Qué pasa en la serie si este perfil queda vigente (reglas del ADR 0016)."""
    if anterior is None:
        return [f"Primera versión del perfil ({version}): será la referencia de la serie."]
    avisos: list[str] = []
    for campo, etiqueta in (
        ("servicios", "servicios"),
        ("ciudades", "ciudades"),
        ("publicos", "públicos"),
    ):
        antes, ahora = set(getattr(anterior, campo)), set(getattr(nuevo, campo))
        if ahora - antes:
            avisos.append(
                f"Añades {etiqueta} ({_lista(ahora - antes)}): la próxima re-medición tendrá "
                "preguntas nuevas; el score se comparará sobre el núcleo común de preguntas y el "
                "banco ampliado se informará aparte."
            )
        if antes - ahora:
            avisos.append(
                f"Quitas {etiqueta} ({_lista(antes - ahora)}): el banco se recorta; la "
                "comparación se hará sobre las preguntas comunes."
            )
    if (
        anterior.posicionamiento_deseado != nuevo.posicionamiento_deseado
        or anterior.atributos_deseados != nuevo.atributos_deseados
    ):
        avisos.append(
            "El posicionamiento y los atributos deseados no afectan al score ni a la "
            "comparabilidad: orientan la propuesta."
        )
    if (
        anterior.restricciones != nuevo.restricciones
        or anterior.presupuesto_anual_eur != nuevo.presupuesto_anual_eur
    ):
        avisos.append(
            "Las restricciones y el presupuesto no afectan al score: se aplican al plan de la "
            "próxima medición."
        )
    if not avisos:
        avisos.append("Sin cambios respecto a la versión vigente.")
    else:
        avisos.append(f"La serie marcará el cambio de perfil ({version}) en la próxima medición.")
    if modo == "kit" and cambia_el_banco(anterior, nuevo):
        avisos.append(
            "Caso sintético del reto: el kit responde siempre al mismo banco de preguntas; el "
            "cambio queda registrado, pero no altera las respuestas medidas."
        )
    return avisos


def aviso_mercado(
    anterior: Sequence[Brand] | None, nuevo: Sequence[Brand], version: str
) -> list[str]:
    """Qué pasa en la serie si este mercado queda vigente (reglas del ADR 0016)."""
    if anterior is None:
        return [f"Primera versión del mercado ({version}): será la referencia de la serie."]
    antes = {b.id: b for b in anterior}
    ahora = {b.id: b for b in nuevo}
    entran, salen = set(ahora) - set(antes), set(antes) - set(ahora)
    if not entran and not salen and all(antes[i] == ahora[i] for i in ahora):
        return ["Sin cambios respecto a la versión vigente."]
    partes = []
    if entran:
        partes.append(f"entran {_lista([ahora[i].nombre for i in entran])}")
    if salen:
        partes.append(f"salen {_lista([antes[i].nombre for i in salen])}")
    que = "; ".join(partes) if partes else "cambian los datos de las marcas"
    return [
        f"Cambia el mercado ({que}): el score y la aparición siguen siendo comparables; el "
        "puesto y la diferencia frente a los competidores no se compararán con las mediciones "
        "anteriores.",
        f"La serie marcará el cambio de mercado ({version}) en la próxima medición.",
    ]


def validar_mercado(brand_id: str, marcas: Sequence[Brand]) -> Market:
    """El mercado nuevo: ids únicos (lo valida `Market`) y con la marca del seguimiento dentro."""
    if brand_id not in {b.id for b in marcas}:
        raise ValueError(f"el mercado debe incluir la marca {brand_id}")
    return Market(marcas=list(marcas), confirmado_por_humano=True)
