"""Configuración versionada por marca y estado de las acciones (ADR 0016).

Complementa a `application.seguimiento` (lista de marcas y serie): perfil y mercado versionados por
usuario y marca, con `vigente_desde` y `aviso_impacto`; la re-medición con la configuración VIGENTE
(guardando las versiones usadas) y el estado de las acciones del plan. Recibe siempre los estudios
que el usuario puede ver (la API los filtra por propietario), así que nunca mezcla dos consultores.
"""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from posiq.application.accounts import now_utc
from posiq.application.deps import db
from posiq.application.runner import RemeasureError, StudyRunner
from posiq.application.tracking import (
    ConfigEstudio,
    PerfilMarca,
    TipoConfig,
    TrackingRepo,
    VersionCreada,
    VersionMercadoMarca,
    VersionPerfilMarca,
    aplicar_perfil,
    aviso_mercado,
    aviso_perfil,
    cambia_el_banco,
    perfil_de_brief,
    siguiente_inicio,
    siguiente_version,
    validar_mercado,
)
from posiq.domain.schemas import Brand, BriefSummary, Market, ModoEstudio, Study


class BrandNotFound(KeyError):
    """La marca no tiene ningún estudio visible para el usuario (la API responde 404)."""


class RemeasureConflict(RemeasureError):
    """Ya hay una re-medición en curso del mismo estudio, o dos ediciones de la configuración a la
    vez."""


def _de_la_marca(studies: Sequence[Study], brand_id: str) -> list[Study]:
    return sorted((s for s in studies if s.brand_id == brand_id), key=lambda s: (s.creado_en, s.id))


def modo_de_la_serie(studies: Sequence[Study]) -> ModoEstudio:
    """Modo de la serie: el de la última medición completada (o del último estudio). La serie no
    mezcla el caso sintético del kit con mediciones reales."""
    completados = [s for s in studies if s.estado == "completado"]
    return (completados or list(studies))[-1].modo


class TrackingService:
    def __init__(self, repo: TrackingRepo, runner: StudyRunner) -> None:
        self.repo = repo
        self.runner = runner
        self.remidiendo: set[str] = set()

    # --- Configuración versionada -----------------------------------------------------------------

    async def _iniciales(self, user_id: str, studies: Sequence[Study], brand_id: str) -> None:
        """v1 del perfil y del mercado desde el primer estudio de la marca, si aún no hay."""
        propios = _de_la_marca(studies, brand_id)
        if not propios:
            raise BrandNotFound(brand_id)
        if not await db(self.repo.config_versions, "perfil", user_id, brand_id):
            base = next((s for s in propios if s.brief.marca), None)
            if base is not None:
                await self._insertar(
                    "perfil",
                    user_id,
                    brand_id,
                    "v1",
                    base.creado_en,
                    perfil_de_brief(base.brief).model_dump_json(),
                )
        if not await db(self.repo.config_versions, "mercado", user_id, brand_id):
            for s in propios:
                values, _ = await self.runner.state(s.id)
                market = values.get("market")
                if market is not None and market.confirmado_por_humano:
                    await self._insertar(
                        "mercado", user_id, brand_id, "v1", s.creado_en, market.model_dump_json()
                    )
                    break

    async def _insertar(
        self,
        tipo: TipoConfig,
        user_id: str,
        brand_id: str,
        version: str,
        desde: datetime,
        data: str,
    ) -> bool:
        try:
            await db(self.repo.add_config_version, tipo, user_id, brand_id, version, desde, data)
        except IntegrityError:  # otra petición creó la misma versión a la vez
            return False
        return True

    async def perfiles(
        self, user_id: str, studies: Sequence[Study], brand_id: str
    ) -> list[VersionPerfilMarca]:
        await self._iniciales(user_id, studies, brand_id)
        filas = await db(self.repo.config_versions, "perfil", user_id, brand_id)
        return [
            VersionPerfilMarca(
                version=v, vigente_desde=desde, perfil=PerfilMarca.model_validate_json(data)
            )
            for v, desde, data in filas
        ]

    async def mercados(
        self, user_id: str, studies: Sequence[Study], brand_id: str
    ) -> list[VersionMercadoMarca]:
        await self._iniciales(user_id, studies, brand_id)
        filas = await db(self.repo.config_versions, "mercado", user_id, brand_id)
        return [
            VersionMercadoMarca(
                version=v, vigente_desde=desde, marcas=Market.model_validate_json(data).marcas
            )
            for v, desde, data in filas
        ]

    async def guardar_perfil(
        self, user_id: str, studies: Sequence[Study], brand_id: str, perfil: PerfilMarca
    ) -> VersionCreada:
        anteriores = await self.perfiles(user_id, studies, brand_id)
        version = siguiente_version([v.version for v in anteriores])
        desde = siguiente_inicio(now_utc(), anteriores[-1].vigente_desde if anteriores else None)
        if not await self._insertar(
            "perfil", user_id, brand_id, version, desde, perfil.model_dump_json()
        ):
            raise RemeasureConflict("otra edición del perfil se guardó a la vez; vuelve a leerlo")
        modo = modo_de_la_serie(_de_la_marca(studies, brand_id))
        anterior = anteriores[-1].perfil if anteriores else None
        return VersionCreada(
            version=version,
            vigente_desde=desde,
            aviso_impacto=aviso_perfil(anterior, perfil, version, modo),
        )

    async def guardar_mercado(
        self, user_id: str, studies: Sequence[Study], brand_id: str, marcas: list[Brand]
    ) -> VersionCreada:
        market = validar_mercado(brand_id, marcas)
        anteriores = await self.mercados(user_id, studies, brand_id)
        version = siguiente_version([v.version for v in anteriores])
        desde = siguiente_inicio(now_utc(), anteriores[-1].vigente_desde if anteriores else None)
        if not await self._insertar(
            "mercado", user_id, brand_id, version, desde, market.model_dump_json()
        ):
            raise RemeasureConflict("otra edición del mercado se guardó a la vez; vuelve a leerlo")
        anterior = anteriores[-1].marcas if anteriores else None
        return VersionCreada(
            version=version,
            vigente_desde=desde,
            aviso_impacto=aviso_mercado(anterior, marcas, version),
        )

    # --- Re-medición ---------------------------------------------------------------------------

    def en_curso(self, study_id: str) -> bool:
        """¿Hay una re-medición de `study_id` sin terminar (ni completada ni con error)?"""
        if study_id in self.remidiendo:
            return True
        for sid in self.repo.remeasures_of(study_id):
            try:
                nuevo = self.runner.repo.get_study(sid)
            except KeyError:
                continue
            if self.runner.estado(nuevo) not in ("completado", "error"):
                return True
        return False

    async def remeasure(
        self,
        user_id: str,
        studies: Sequence[Study],
        original: Study,
    ) -> Study:
        """Re-mide `original` con la configuración VIGENTE y guarda las versiones usadas.

        La confirmación del coste la hace antes la API (`POST /studies/{id}/remeasure`).
        `RemeasureConflict` (409) si ya hay una re-medición en curso del mismo estudio;
        `RemeasureError` (409) si el original no está completado.
        """
        if original.estado != "completado":
            raise RemeasureError(
                f"solo se re-mide un estudio completado; {original.id} está «{original.estado}»"
            )
        if self.en_curso(original.id):
            raise RemeasureConflict(f"ya hay una re-medición en curso de {original.id}")
        self.remidiendo.add(original.id)
        try:
            perfiles = await self.perfiles(user_id, studies, original.brand_id)
            mercados = await self.mercados(user_id, studies, original.brand_id)
            values, _ = await self.runner.state(original.id)
            brief: BriefSummary | None = values.get("brief")
            market: Market | None = None
            reutilizar = True
            if brief is not None and perfiles:
                vigente = perfiles[-1].perfil
                reutilizar = original.modo == "kit" or not cambia_el_banco(
                    perfil_de_brief(brief), vigente
                )
                brief = aplicar_perfil(brief, vigente)
            if mercados:
                market = validar_mercado(original.brand_id, mercados[-1].marcas)
            study = await self.runner.prepare_remeasure(
                original.id, brief=brief, market=market, reutilizar_prompts=reutilizar
            )
            await db(
                self.repo.set_study_config,
                study.id,
                ConfigEstudio(
                    version_perfil=perfiles[-1].version if perfiles else None,
                    version_mercado=mercados[-1].version if mercados else None,
                    remedicion_de=original.id,
                ),
            )
            return study
        finally:
            self.remidiendo.discard(original.id)
