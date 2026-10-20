"""`ports.StudyRepo` sobre SQLModel (SQLite por `DATABASE_URL`).

Una tabla por tipo de resultado. Las claves son compuestas (`study_id`, `id`) porque los ids de
`Run`, `Evaluation` y `Finding` solo son únicos dentro de un estudio. El modelo completo se guarda
como JSON en `data`; las columnas sueltas (`brand_id`, `creado_en`, `estado`…) son solo para
filtrar y ordenar. Las tablas se crean con `create_all`, sin migraciones (Alembic, post-hackathon).
"""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Engine, delete, event
from sqlmodel import Field, Session, SQLModel, col, create_engine, select

from posiq.domain.schemas import (
    Evaluation,
    Finding,
    Metrics,
    MetricsDelta,
    Plan,
    Proposal,
    Run,
    Study,
    Trace,
)


class StudyRow(SQLModel, table=True):
    __tablename__ = "study"

    id: str = Field(primary_key=True)
    brand_id: str = Field(index=True)
    modo: str
    estado: str
    creado_en: datetime = Field(index=True)
    data: str


class RunRow(SQLModel, table=True):
    __tablename__ = "run"

    study_id: str = Field(primary_key=True)
    id: str = Field(primary_key=True)
    data: str


class EvaluationRow(SQLModel, table=True):
    __tablename__ = "evaluation"

    study_id: str = Field(primary_key=True)
    id: str = Field(primary_key=True)
    run_id: str
    brand_id: str
    data: str


class MetricsRow(SQLModel, table=True):
    __tablename__ = "metrics"

    study_id: str = Field(primary_key=True)
    data: str
    delta: str | None = None


class FindingRow(SQLModel, table=True):
    __tablename__ = "finding"

    study_id: str = Field(primary_key=True)
    id: str = Field(primary_key=True)
    orden: int
    data: str


class PlanRow(SQLModel, table=True):
    __tablename__ = "plan"

    study_id: str = Field(primary_key=True)
    data: str


class ProposalRow(SQLModel, table=True):
    __tablename__ = "proposal"

    study_id: str = Field(primary_key=True)
    data: str


class TraceRow(SQLModel, table=True):
    __tablename__ = "trace"

    study_id: str = Field(primary_key=True)
    seq: int = Field(primary_key=True)
    nodo: str
    coste_eur: float
    data: str


def _utc(value: datetime) -> datetime:
    """Todo en UTC para que fechas de distintas zonas se ordenen bien (sin zona = UTC)."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _sqlite_wal(conn: Any, _record: Any) -> None:
    """WAL: el checkpointer de LangGraph (misma base) lee mientras el repositorio escribe."""
    conn.execute("PRAGMA journal_mode=WAL")


def _json(model: BaseModel) -> str:
    """Sin campos calculados: con `extra="forbid"` no se podrían volver a validar."""
    return model.model_dump_json(exclude_computed_fields=True)


class SqlStudyRepo:
    """Repositorio de estudios. `url` es una URL de SQLAlchemy (p. ej. `sqlite:///./posiq.db`)."""

    def __init__(self, url: str | None = None, *, engine: Engine | None = None) -> None:
        if engine is None:
            if url is None:
                raise ValueError("SqlStudyRepo necesita `url` o `engine`")
            args = {"check_same_thread": False, "timeout": 30} if url.startswith("sqlite") else {}
            engine = create_engine(url, connect_args=args)
            if url.startswith("sqlite") and ":memory:" not in url and url != "sqlite://":
                event.listen(engine, "connect", _sqlite_wal)
        self.engine = engine
        SQLModel.metadata.create_all(self.engine)

    @contextmanager
    def _session(self) -> Iterator[Session]:
        with Session(self.engine) as session:
            yield session
            session.commit()

    # --- Escritura --------------------------------------------------------------------------------

    def save_study(self, study: Study) -> None:
        with self._session() as s:
            s.merge(
                StudyRow(
                    id=study.id,
                    brand_id=study.brand_id,
                    modo=study.modo,
                    estado=study.estado,
                    creado_en=_utc(study.creado_en),
                    data=_json(study),
                )
            )

    def save_runs(self, study_id: str, runs: Sequence[Run]) -> None:
        self._check(study_id, runs)
        with self._session() as s:
            for r in runs:
                s.merge(RunRow(study_id=study_id, id=r.id, data=_json(r)))

    def save_evaluations(self, study_id: str, evals: Sequence[Evaluation]) -> None:
        self._check(study_id, evals)
        with self._session() as s:
            for e in evals:
                s.merge(
                    EvaluationRow(
                        study_id=study_id,
                        id=e.id,
                        run_id=e.run_id,
                        brand_id=e.brand_id,
                        data=_json(e),
                    )
                )

    def save_metrics(
        self, study_id: str, metrics: Metrics, delta: MetricsDelta | None = None
    ) -> None:
        self._check(study_id, [metrics, *([delta] if delta else [])])
        with self._session() as s:
            s.merge(
                MetricsRow(
                    study_id=study_id, data=_json(metrics), delta=_json(delta) if delta else None
                )
            )

    def save_findings(self, study_id: str, findings: Sequence[Finding]) -> None:
        self._check(study_id, findings)
        with self._session() as s:
            s.exec(delete(FindingRow).where(col(FindingRow.study_id) == study_id))  # type: ignore[call-overload]
            for i, f in enumerate(findings):
                s.add(FindingRow(study_id=study_id, id=f.id, orden=i, data=_json(f)))

    def save_plan(self, study_id: str, plan: Plan) -> None:
        self._check(study_id, [plan])
        with self._session() as s:
            s.merge(PlanRow(study_id=study_id, data=_json(plan)))

    def save_proposal(self, study_id: str, proposal: Proposal) -> None:
        self._check(study_id, [proposal])
        with self._session() as s:
            s.merge(ProposalRow(study_id=study_id, data=_json(proposal)))

    def save_traces(self, study_id: str, traces: Sequence[Trace]) -> None:
        self._check(study_id, traces)
        with self._session() as s:
            s.exec(delete(TraceRow).where(col(TraceRow.study_id) == study_id))  # type: ignore[call-overload]
            for i, t in enumerate(traces):
                s.add(
                    TraceRow(
                        study_id=study_id, seq=i, nodo=t.nodo, coste_eur=t.coste_eur, data=_json(t)
                    )
                )

    # --- Lectura ----------------------------------------------------------------------------------

    def get_study(self, study_id: str) -> Study:
        with Session(self.engine) as s:
            row = s.get(StudyRow, study_id)
        if row is None:
            raise KeyError(study_id)
        return Study.model_validate_json(row.data)

    def list_studies(self, brand_id: str | None = None) -> list[Study]:
        query = select(StudyRow).order_by(col(StudyRow.creado_en).desc())
        if brand_id is not None:
            query = query.where(StudyRow.brand_id == brand_id)
        with Session(self.engine) as s:
            return [Study.model_validate_json(r.data) for r in s.exec(query)]

    def latest_metrics(self, brand_id: str, before: datetime | None = None) -> Metrics | None:
        query = (
            select(MetricsRow)
            .join(StudyRow, col(StudyRow.id) == col(MetricsRow.study_id))
            .where(StudyRow.brand_id == brand_id)
            .order_by(col(StudyRow.creado_en).desc())
        )
        if before is not None:
            query = query.where(col(StudyRow.creado_en) < _utc(before))
        with Session(self.engine) as s:
            row = s.exec(query).first()
        return Metrics.model_validate_json(row.data) if row else None

    # Lecturas de detalle (no forman parte del puerto: las usan la API y los tests).

    def get_runs(self, study_id: str) -> list[Run]:
        return self._all(RunRow, Run, study_id)

    def get_evaluations(self, study_id: str) -> list[Evaluation]:
        return self._all(EvaluationRow, Evaluation, study_id)

    def get_findings(self, study_id: str) -> list[Finding]:
        """En el orden en que se guardaron (por impacto, como los devuelve el dominio)."""
        query = (
            select(FindingRow)
            .where(FindingRow.study_id == study_id)
            .order_by(col(FindingRow.orden))
        )
        with Session(self.engine) as s:
            return [Finding.model_validate_json(r.data) for r in s.exec(query)]

    def get_traces(self, study_id: str) -> list[Trace]:
        query = select(TraceRow).where(TraceRow.study_id == study_id).order_by(col(TraceRow.seq))
        with Session(self.engine) as s:
            return [Trace.model_validate_json(r.data) for r in s.exec(query)]

    def get_metrics(self, study_id: str) -> tuple[Metrics, MetricsDelta | None] | None:
        with Session(self.engine) as s:
            row = s.get(MetricsRow, study_id)
        if row is None:
            return None
        delta = MetricsDelta.model_validate_json(row.delta) if row.delta else None
        return Metrics.model_validate_json(row.data), delta

    def get_plan(self, study_id: str) -> Plan | None:
        with Session(self.engine) as s:
            row = s.get(PlanRow, study_id)
        return Plan.model_validate_json(row.data) if row else None

    def get_proposal(self, study_id: str) -> Proposal | None:
        with Session(self.engine) as s:
            row = s.get(ProposalRow, study_id)
        return Proposal.model_validate_json(row.data) if row else None

    # --- Internos ---------------------------------------------------------------------------------

    def _all[M: BaseModel](self, table: Any, model: type[M], sid: str) -> list[M]:
        query = select(table).where(table.study_id == sid).order_by(col(table.id))
        with Session(self.engine) as s:
            return [model.model_validate_json(r.data) for r in s.exec(query)]

    @staticmethod
    def _check(study_id: str, items: Sequence[BaseModel]) -> None:
        ajenos = sorted({getattr(i, "study_id", study_id) for i in items} - {study_id})
        if ajenos:
            raise ValueError(f"resultados de otros estudios {ajenos} al guardar {study_id}")
