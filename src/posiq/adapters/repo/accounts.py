"""`application.accounts.AccountRepo` sobre SQLModel, en el mismo motor que `SqlStudyRepo`.

Tablas nuevas `user`, `session`, `verification` y `study_owner`. `create_all` las crea si faltan
sin tocar las que ya existen, así que una base anterior a las cuentas sigue valiendo: sus estudios
quedan sin propietario (ADR 0015).
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import Engine, delete, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, Session, SQLModel, col, select

from posiq.application.accounts import EmailTaken, Sesion, UsuarioGuardado, Verificacion, as_utc


class UserRow(SQLModel, table=True):
    __tablename__ = "user"

    id: str = Field(primary_key=True)
    email: str = Field(index=True, unique=True)
    nombre: str | None = None
    verificado: bool = False
    password_hash: str
    creado_en: datetime


class SessionRow(SQLModel, table=True):
    __tablename__ = "session"

    token_hash: str = Field(primary_key=True)
    user_id: str = Field(index=True)
    expira_en: datetime


class VerificationRow(SQLModel, table=True):
    __tablename__ = "verification"

    email: str = Field(primary_key=True)
    codigo_hash: str
    expira_en: datetime
    intentos: int = 0


class StudyOwnerRow(SQLModel, table=True):
    __tablename__ = "study_owner"

    study_id: str = Field(primary_key=True)
    user_id: str = Field(index=True)


def _user(row: UserRow) -> UsuarioGuardado:
    return UsuarioGuardado(
        id=row.id,
        email=row.email,
        nombre=row.nombre,
        verificado=row.verificado,
        password_hash=row.password_hash,
        creado_en=as_utc(row.creado_en),
    )


class SqlAccountRepo:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        SQLModel.metadata.create_all(self.engine)

    @contextmanager
    def _session(self) -> Iterator[Session]:
        with Session(self.engine) as session:
            yield session
            session.commit()

    # Usuarios

    def add_user(self, user: UsuarioGuardado) -> None:
        try:
            with self._session() as s:
                s.add(UserRow(**user.model_dump()))
        except IntegrityError as exc:
            raise EmailTaken() from exc

    def save_user(self, user: UsuarioGuardado) -> None:
        with self._session() as s:
            s.merge(UserRow(**user.model_dump()))

    def get_user(self, user_id: str) -> UsuarioGuardado | None:
        with Session(self.engine) as s:
            row = s.get(UserRow, user_id)
        return _user(row) if row else None

    def get_user_by_email(self, email: str) -> UsuarioGuardado | None:
        with Session(self.engine) as s:
            row = s.exec(select(UserRow).where(UserRow.email == email)).first()
        return _user(row) if row else None

    # Verificaciones

    def save_verification(self, verificacion: Verificacion) -> None:
        with self._session() as s:
            s.merge(VerificationRow(**verificacion.model_dump()))

    def get_verification(self, email: str) -> Verificacion | None:
        with Session(self.engine) as s:
            row = s.get(VerificationRow, email)
        return Verificacion.model_validate(row.model_dump()) if row else None

    def count_attempt(self, email: str, maximo: int) -> Verificacion | None:
        """`UPDATE … SET intentos = intentos + 1 WHERE … AND intentos < maximo RETURNING …`.

        Una sola sentencia: la base serializa las escrituras, así que dos peticiones concurrentes
        nunca leen el mismo contador (la lectura-modificación-escritura anterior sí podía).
        """
        tabla = VerificationRow.__table__  # type: ignore[attr-defined]
        sentencia = (
            update(tabla)
            .where(tabla.c.email == email, tabla.c.intentos < maximo)
            .values(intentos=tabla.c.intentos + 1)
            .returning(tabla.c.email, tabla.c.codigo_hash, tabla.c.expira_en, tabla.c.intentos)
        )
        with self.engine.begin() as conn:
            fila = conn.execute(sentencia).mappings().first()
        return Verificacion.model_validate(dict(fila)) if fila else None

    def delete_verification(self, email: str) -> None:
        with self._session() as s:
            s.exec(delete(VerificationRow).where(col(VerificationRow.email) == email))  # type: ignore[call-overload]

    # Sesiones

    def add_session(self, sesion: Sesion) -> None:
        with self._session() as s:
            s.add(SessionRow(**sesion.model_dump()))

    def get_session(self, token_hash: str) -> Sesion | None:
        with Session(self.engine) as s:
            row = s.get(SessionRow, token_hash)
        return Sesion.model_validate(row.model_dump()) if row else None

    def delete_session(self, token_hash: str) -> None:
        with self._session() as s:
            s.exec(delete(SessionRow).where(col(SessionRow.token_hash) == token_hash))  # type: ignore[call-overload]

    # Propiedad de estudios

    def set_owner(self, study_id: str, user_id: str) -> None:
        with self._session() as s:
            s.merge(StudyOwnerRow(study_id=study_id, user_id=user_id))

    def owner_of(self, study_id: str) -> str | None:
        with Session(self.engine) as s:
            row = s.get(StudyOwnerRow, study_id)
        return row.user_id if row else None

    def owners(self) -> dict[str, str]:
        with Session(self.engine) as s:
            return {r.study_id: r.user_id for r in s.exec(select(StudyOwnerRow))}
