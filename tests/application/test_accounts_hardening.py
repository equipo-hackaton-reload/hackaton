"""Revisión de #36: intentos atómicos, reenvíos limitados, tiempo uniforme y cuenta de demo."""

import threading
import time
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from posiq.adapters.repo.accounts import SqlAccountRepo
from posiq.adapters.repo.sql import SqlStudyRepo
from posiq.application import accounts as acc
from posiq.application.accounts import (
    DEMO_EMAIL,
    AccountService,
    DemoDisabled,
    InvalidCode,
    RegisterBody,
    TooManyAttempts,
    demo_activo,
)
from tests.application.fakes import kit_settings


def service(repo: SqlAccountRepo | None = None, **kw: object) -> AccountService:
    if repo is None:
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        repo = SqlAccountRepo(engine)
    return AccountService(repo, kit_settings(auth_scrypt_n=2**10, **kw))


def file_repo(tmp_path: Path) -> SqlAccountRepo:
    return SqlAccountRepo(SqlStudyRepo(f"sqlite:///{(tmp_path / 'c.db').as_posix()}").engine)


def otro(codigo: str) -> str:
    return "000000" if codigo != "000000" else "111111"


# --- 1. Intentos atómicos ----------------------------------------------------------------------


def test_concurrent_verifications_never_compare_more_than_the_maximum(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """20 hilos a la vez con un código malo: como mucho 5 comparaciones, el resto 429."""
    s = service(file_repo(tmp_path))
    registro = s.register(RegisterBody(email="a@b.es", password="12345678"))
    comparaciones: list[int] = []
    cerrojo = threading.Lock()
    real_verify = acc.verify_secret

    def lenta(secreto: str, guardado: str) -> bool:
        with cerrojo:
            comparaciones.append(1)
        time.sleep(0.05)  # ensancha la ventana de carrera de la versión anterior
        return real_verify(secreto, guardado)

    monkeypatch.setattr(acc, "verify_secret", lenta)
    salida = threading.Barrier(20)
    resultados: list[str] = []

    def intento() -> None:
        salida.wait()
        try:
            s.verify("a@b.es", otro(registro.codigo))
        except (InvalidCode, TooManyAttempts) as exc:
            with cerrojo:
                resultados.append(type(exc).__name__)

    hilos = [threading.Thread(target=intento) for _ in range(20)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert len(comparaciones) == acc.CODIGO_MAX_INTENTOS
    assert resultados.count("InvalidCode") == acc.CODIGO_MAX_INTENTOS
    assert resultados.count("TooManyAttempts") == 20 - acc.CODIGO_MAX_INTENTOS
    with pytest.raises(TooManyAttempts):  # ni siquiera el bueno
        s.verify("a@b.es", registro.codigo)
    pendiente = s.repo.get_verification("a@b.es")
    assert pendiente is not None and pendiente.intentos == acc.CODIGO_MAX_INTENTOS


def test_the_attempt_counts_before_comparing(monkeypatch: pytest.MonkeyPatch) -> None:
    s = service()
    registro = s.register(RegisterBody(email="a@b.es", password="12345678"))
    vistos: list[int] = []

    def mira(secreto: str, guardado: str) -> bool:
        pendiente = s.repo.get_verification("a@b.es")
        assert pendiente is not None
        vistos.append(pendiente.intentos)
        return False

    monkeypatch.setattr(acc, "verify_secret", mira)
    with pytest.raises(InvalidCode):
        s.verify("a@b.es", registro.codigo)
    assert vistos == [1]  # al comparar, el intento ya estaba guardado


def test_count_attempt_is_conditional(tmp_path: Path) -> None:
    repo = file_repo(tmp_path)
    s = service(repo)
    s.register(RegisterBody(email="a@b.es", password="12345678"))
    assert [v.intentos for v in (repo.count_attempt("a@b.es", 2) for _ in range(2)) if v] == [1, 2]
    assert repo.count_attempt("a@b.es", 2) is None
    assert repo.count_attempt("nadie@b.es", 2) is None


# --- 2. Reenvíos ----------------------------------------------------------------------------------


def test_resend_is_limited_per_email_and_hour_even_for_unknown_emails() -> None:
    s = service()
    s.register(RegisterBody(email="a@b.es", password="12345678"))
    for _ in range(acc.REENVIOS_POR_HORA):
        assert s.resend("a@b.es") is not None
    with pytest.raises(TooManyAttempts):
        s.resend("a@b.es")
    for _ in range(acc.REENVIOS_POR_HORA):
        assert s.resend("nadie@b.es") is None
    with pytest.raises(TooManyAttempts):  # mismo trato exista o no: no revela nada
        s.resend("nadie@b.es")


def test_resend_bounds_comparisons_per_email_and_hour() -> None:
    s = service()
    registro = s.register(RegisterBody(email="a@b.es", password="12345678"))
    fallos = 0
    codigos = [registro.codigo]
    while True:
        for _ in range(acc.CODIGO_MAX_INTENTOS + 1):
            try:
                s.verify("a@b.es", otro(codigos[-1]))
            except InvalidCode:
                fallos += 1
            except TooManyAttempts:
                break
        try:
            nuevo = s.resend("a@b.es")
        except TooManyAttempts:
            break
        assert nuevo is not None
        codigos.append(nuevo)
    assert fallos == (1 + acc.REENVIOS_POR_HORA) * acc.CODIGO_MAX_INTENTOS


# --- 3. Tiempo uniforme ---------------------------------------------------------------------------


def contar_hashes(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    llamadas: list[int] = []
    real_hash = acc.hash_secret

    def contado(secreto: str, params: object = None) -> str:
        llamadas.append(1)
        return real_hash(secreto, params)  # type: ignore[arg-type]

    monkeypatch.setattr(acc, "hash_secret", contado)
    return llamadas


def test_resend_does_the_same_work_whether_the_email_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = service()
    s.register(RegisterBody(email="a@b.es", password="12345678"))
    llamadas = contar_hashes(monkeypatch)
    s.resend("a@b.es")
    existe = len(llamadas)
    s.resend("nadie@b.es")
    assert existe == 1 and len(llamadas) - existe == existe


def test_register_does_the_same_work_whether_the_email_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = service()
    llamadas = contar_hashes(monkeypatch)
    s.register(RegisterBody(email="a@b.es", password="12345678"))
    nuevo = len(llamadas)
    with pytest.raises(acc.EmailTaken):
        s.register(RegisterBody(email="a@b.es", password="12345678"))
    assert nuevo == 2 and len(llamadas) - nuevo == nuevo


# --- 5. Cuenta de demo ----------------------------------------------------------------------------


def test_demo_mode_follows_dev_codes() -> None:
    assert demo_activo(kit_settings(llm_provider="fixture"))
    assert not demo_activo(kit_settings(llm_provider="deepseek"))
    assert not demo_activo(kit_settings(llm_provider="fixture", auth_dev_codes=False))
    assert demo_activo(kit_settings(llm_provider="deepseek", auth_dev_codes=True))


def test_demo_account_does_not_exist_with_the_real_llm(tmp_path: Path) -> None:
    repo = file_repo(tmp_path)
    # En la demo (fixture) la cuenta se crea y entra; también ve los estudios sin propietario.
    demo = service(repo, llm_provider="fixture", auth_demo_user=DEMO_EMAIL)
    registro = demo.register(RegisterBody(email=DEMO_EMAIL, password="posiq-demo-alborada"))
    demo.verify(DEMO_EMAIL, registro.codigo)
    sesion = demo.login(DEMO_EMAIL, "posiq-demo-alborada")
    assert demo.is_demo(sesion.user) and demo.can_access(sesion.user, "antiguo")

    # La misma base con el LLM real: ni login, ni sesión, ni alta, ni estudios sin propietario.
    real = service(repo, llm_provider="deepseek", auth_demo_user=DEMO_EMAIL)
    assert not real.demo
    with pytest.raises(DemoDisabled):
        real.login(DEMO_EMAIL, "posiq-demo-alborada")
    assert real.user_for_token(sesion.token) is None
    assert not real.is_demo(sesion.user) and not real.can_access(sesion.user, "antiguo")
    with pytest.raises(DemoDisabled):
        real.register(RegisterBody(email=DEMO_EMAIL, password="12345678"))
    assert real.resend(DEMO_EMAIL) is None


def test_auth_demo_user_is_ignored_outside_demo_mode() -> None:
    s = service(llm_provider="deepseek", auth_demo_user="jefa@empresa.es")
    with pytest.raises(DemoDisabled):
        s.register(RegisterBody(email="jefa@empresa.es", password="12345678"))
    normal = service(llm_provider="deepseek")
    registro = normal.register(RegisterBody(email="ana@empresa.es", password="12345678"))
    assert normal.verify("ana@empresa.es", registro.codigo).verificado
