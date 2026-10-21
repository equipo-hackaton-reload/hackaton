"""Las tablas de cuentas se crean sobre una base anterior sin tocar sus estudios."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import inspect

from posiq.adapters.repo.accounts import SqlAccountRepo
from posiq.adapters.repo.sql import SqlStudyRepo
from posiq.application.accounts import EmailTaken, UsuarioGuardado
from posiq.application.deps import new_study


def user(email: str = "a@b.es", uid: str = "u1") -> UsuarioGuardado:
    return UsuarioGuardado(
        id=uid, email=email, password_hash="h", creado_en=datetime.now(UTC), verificado=False
    )


def test_account_tables_are_added_to_an_existing_database(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'old.db').as_posix()}"
    studies = SqlStudyRepo(url)
    antiguo = new_study("kit")
    studies.save_study(antiguo)

    accounts = SqlAccountRepo(SqlStudyRepo(url).engine)
    tablas = set(inspect(accounts.engine).get_table_names())
    assert {"user", "session", "verification", "study_owner", "study"} <= tablas
    assert [s.id for s in SqlStudyRepo(url).list_studies()] == [antiguo.id]
    assert accounts.owner_of(antiguo.id) is None and accounts.owners() == {}


def test_users_are_unique_by_email_and_owners_persist(tmp_path: Path) -> None:
    repo = SqlAccountRepo(SqlStudyRepo(f"sqlite:///{(tmp_path / 'a.db').as_posix()}").engine)
    repo.add_user(user())
    with pytest.raises(EmailTaken):
        repo.add_user(user(uid="u2"))
    guardado = repo.get_user_by_email("a@b.es")
    assert guardado is not None and guardado.creado_en.tzinfo is not None
    repo.save_user(guardado.model_copy(update={"verificado": True}))
    assert (repo.get_user("u1") or guardado).verificado

    repo.set_owner("s1", "u1")
    repo.set_owner("s1", "u1")  # idempotente
    assert repo.owner_of("s1") == "u1" and repo.owners() == {"s1": "u1"}
