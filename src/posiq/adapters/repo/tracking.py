"""`application.tracking.TrackingRepo` sobre SQLModel, en el mismo motor que `SqlStudyRepo`.

Tablas nuevas (`create_all` las crea si faltan, sin tocar las demás):

- `brand_config_version`: versiones del perfil y del mercado por usuario y marca. Solo se insertan:
  una versión nunca se sobrescribe.
- `study_config`: versiones con las que se midió un estudio y a qué estudio re-mide.
- `action_status`: historial del estado de las acciones del plan (una fila por cambio).
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import Engine
from sqlmodel import Field, Session, SQLModel, col, select

from posiq.application.tracking import (
    ConfigEstudio,
    EstadoAccionGuardado,
    TipoConfig,
    as_utc,
)


class BrandConfigVersionRow(SQLModel, table=True):
    __tablename__ = "brand_config_version"

    tipo: str = Field(primary_key=True)
    user_id: str = Field(primary_key=True)
    brand_id: str = Field(primary_key=True)
    version: str = Field(primary_key=True)
    vigente_desde: datetime
    data: str


class StudyConfigRow(SQLModel, table=True):
    __tablename__ = "study_config"

    study_id: str = Field(primary_key=True)
    version_perfil: str | None = None
    version_mercado: str | None = None
    remedicion_de: str | None = Field(default=None, index=True)


class ActionStatusRow(SQLModel, table=True):
    __tablename__ = "action_status"

    id: int | None = Field(default=None, primary_key=True)
    study_id: str = Field(index=True)
    action_id: str
    user_id: str
    estado: str
    nota: str | None = None
    actualizado_en: datetime


class SqlTrackingRepo:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        SQLModel.metadata.create_all(self.engine)

    @contextmanager
    def _session(self) -> Iterator[Session]:
        with Session(self.engine) as session:
            yield session
            session.commit()

    # Configuración versionada

    def config_versions(
        self, tipo: TipoConfig, user_id: str, brand_id: str
    ) -> list[tuple[str, datetime, str]]:
        query = (
            select(BrandConfigVersionRow)
            .where(
                BrandConfigVersionRow.tipo == tipo,
                BrandConfigVersionRow.user_id == user_id,
                BrandConfigVersionRow.brand_id == brand_id,
            )
            .order_by(col(BrandConfigVersionRow.vigente_desde))
        )
        with Session(self.engine) as s:
            return [(r.version, as_utc(r.vigente_desde), r.data) for r in s.exec(query)]

    def add_config_version(
        self,
        tipo: TipoConfig,
        user_id: str,
        brand_id: str,
        version: str,
        vigente_desde: datetime,
        data: str,
    ) -> None:
        """Inserta (nunca sustituye): una versión repetida lanza `IntegrityError`."""
        with self._session() as s:
            s.add(
                BrandConfigVersionRow(
                    tipo=tipo,
                    user_id=user_id,
                    brand_id=brand_id,
                    version=version,
                    vigente_desde=as_utc(vigente_desde),
                    data=data,
                )
            )

    # Configuración de cada estudio

    def set_study_config(self, study_id: str, config: ConfigEstudio) -> None:
        with self._session() as s:
            s.merge(StudyConfigRow(study_id=study_id, **config.model_dump()))

    def study_config(self, study_id: str) -> ConfigEstudio | None:
        with Session(self.engine) as s:
            row = s.get(StudyConfigRow, study_id)
        if row is None:
            return None
        return ConfigEstudio(
            version_perfil=row.version_perfil,
            version_mercado=row.version_mercado,
            remedicion_de=row.remedicion_de,
        )

    def remeasures_of(self, study_id: str) -> list[str]:
        query = select(StudyConfigRow).where(StudyConfigRow.remedicion_de == study_id)
        with Session(self.engine) as s:
            return [r.study_id for r in s.exec(query)]

    # Estado de las acciones del plan

    def add_action_status(
        self, study_id: str, action_id: str, user_id: str, estado: EstadoAccionGuardado
    ) -> None:
        with self._session() as s:
            s.add(
                ActionStatusRow(
                    study_id=study_id,
                    action_id=action_id,
                    user_id=user_id,
                    estado=estado.estado,
                    nota=estado.nota,
                    actualizado_en=as_utc(estado.actualizado_en),
                )
            )

    def action_statuses(self, study_id: str) -> dict[str, EstadoAccionGuardado]:
        query = (
            select(ActionStatusRow)
            .where(ActionStatusRow.study_id == study_id)
            .order_by(col(ActionStatusRow.id))
        )
        out: dict[str, EstadoAccionGuardado] = {}
        with Session(self.engine) as s:
            for r in s.exec(query):
                out[r.action_id] = EstadoAccionGuardado.model_validate(
                    {"estado": r.estado, "nota": r.nota, "actualizado_en": as_utc(r.actualizado_en)}
                )
        return out

    def action_history(self, study_id: str, action_id: str) -> list[EstadoAccionGuardado]:
        query = (
            select(ActionStatusRow)
            .where(ActionStatusRow.study_id == study_id, ActionStatusRow.action_id == action_id)
            .order_by(col(ActionStatusRow.id))
        )
        with Session(self.engine) as s:
            return [
                EstadoAccionGuardado.model_validate(
                    {"estado": r.estado, "nota": r.nota, "actualizado_en": as_utc(r.actualizado_en)}
                )
                for r in s.exec(query)
            ]
