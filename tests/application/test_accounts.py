"""Hash de contraseñas, tokens, códigos de verificación y reglas de `AccountService`."""

from datetime import timedelta

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from posiq.adapters.repo.accounts import SqlAccountRepo
from posiq.application import accounts as acc
from posiq.application.accounts import (
    AccountService,
    EmailTaken,
    InvalidCode,
    InvalidCredentials,
    NotVerified,
    RateLimiter,
    RegisterBody,
    TooManyAttempts,
    dev_codes,
)
from posiq.application.security import (
    ScryptParams,
    hash_secret,
    new_code,
    new_token,
    token_hash,
    verify_secret,
)
from tests.application.fakes import kit_settings

FAST = ScryptParams(n=2**10)


def service(**kw: object) -> AccountService:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    return AccountService(SqlAccountRepo(engine), kit_settings(auth_scrypt_n=2**10, **kw))


def test_hash_has_salt_and_params_and_verifies() -> None:
    a, b = hash_secret("secreto-1", FAST), hash_secret("secreto-1", FAST)
    assert a != b  # sal aleatoria por hash
    assert a.startswith("scrypt$1024$8$1$")
    assert verify_secret("secreto-1", a) and verify_secret("secreto-1", b)
    assert not verify_secret("secreto-2", a)
    # Los parámetros viajan en el hash: se verifica con los suyos, no con los actuales.
    assert verify_secret("x" * 8, hash_secret("x" * 8, ScryptParams(n=2**11, r=4)))


@pytest.mark.parametrize("roto", ["", "plano", "bcrypt$1$2$3$a$b", "scrypt$x$8$1$a$b"])
def test_malformed_hash_never_verifies(roto: str) -> None:
    assert not verify_secret("lo-que-sea", roto)


def test_tokens_and_codes() -> None:
    token = new_token()
    assert len(token) >= 43 and token != new_token()
    assert token_hash(token) == token_hash(token) and len(token_hash(token)) == 64
    assert token_hash(token) != token
    codigos = {new_code() for _ in range(200)}
    assert all(len(c) == 6 and c.isdigit() for c in codigos)


def test_dev_codes_default_only_with_fixture() -> None:
    assert dev_codes(kit_settings(llm_provider="fixture"))
    assert not dev_codes(kit_settings(llm_provider="deepseek"))
    assert not dev_codes(kit_settings(llm_provider="fixture", auth_dev_codes=False))
    assert dev_codes(kit_settings(llm_provider="deepseek", auth_dev_codes=True))


def test_register_verify_login_and_logout() -> None:
    s = service()
    registro = s.register(RegisterBody(email="  Ana@Ejemplo.ES ", password="12345678"))
    assert registro.user.email == "ana@ejemplo.es" and not registro.user.verificado
    guardado = s.repo.get_user_by_email("ana@ejemplo.es")
    assert guardado is not None and "12345678" not in guardado.password_hash
    pendiente = s.repo.get_verification("ana@ejemplo.es")
    assert pendiente is not None and registro.codigo not in pendiente.codigo_hash

    with pytest.raises(EmailTaken):
        s.register(RegisterBody(email="ana@ejemplo.es", password="otra-clave"))
    with pytest.raises(NotVerified):
        s.login("ana@ejemplo.es", "12345678")

    assert s.verify("ana@ejemplo.es", registro.codigo).verificado
    assert s.repo.get_verification("ana@ejemplo.es") is None

    with pytest.raises(InvalidCredentials):
        s.login("ana@ejemplo.es", "mala-clave")
    with pytest.raises(InvalidCredentials):
        s.login("nadie@ejemplo.es", "12345678")

    sesion = s.login("ana@ejemplo.es", "12345678")
    assert s.repo.get_session(sesion.token) is None  # solo se guarda el hash
    assert s.user_for_token(sesion.token) == sesion.user
    s.logout(sesion.token)
    assert s.user_for_token(sesion.token) is None


def test_short_password_is_rejected() -> None:
    with pytest.raises(ValueError):
        RegisterBody(email="a@b.es", password="1234567")
    with pytest.raises(ValueError):
        RegisterBody(email="sin-arroba", password="12345678")


def test_code_attempts_are_limited_and_resend_resets_them() -> None:
    s = service()
    registro = s.register(RegisterBody(email="a@b.es", password="12345678"))
    malo = "000000" if registro.codigo != "000000" else "111111"
    for _ in range(acc.CODIGO_MAX_INTENTOS):
        with pytest.raises(InvalidCode):
            s.verify("a@b.es", malo)
    with pytest.raises(TooManyAttempts):
        s.verify("a@b.es", registro.codigo)  # ni siquiera el bueno: hay que pedir otro

    nuevo = s.resend("a@b.es")
    assert nuevo is not None
    assert s.verify("a@b.es", nuevo).verificado
    assert s.resend("a@b.es") is None  # ya verificado
    assert s.resend("nadie@b.es") is None


def test_expired_code_and_expired_session(monkeypatch: pytest.MonkeyPatch) -> None:
    s = service(auth_token_ttl_h=1)
    registro = s.register(RegisterBody(email="a@b.es", password="12345678"))
    real_now = acc.now_utc
    monkeypatch.setattr(acc, "now_utc", lambda: real_now() + timedelta(minutes=16))
    with pytest.raises(InvalidCode, match="caducado"):
        s.verify("a@b.es", registro.codigo)
    monkeypatch.setattr(acc, "now_utc", real_now)

    codigo = s.resend("a@b.es")
    assert codigo is not None
    s.verify("a@b.es", codigo)
    sesion = s.login("a@b.es", "12345678")
    assert s.user_for_token(sesion.token) is not None
    monkeypatch.setattr(acc, "now_utc", lambda: real_now() + timedelta(hours=2))
    assert s.user_for_token(sesion.token) is None


def test_ownership_and_demo_user() -> None:
    # Modo demo explícito: no depende de que el entorno exporte LLM_PROVIDER=fixture.
    s = service(auth_demo_user="Demo@posiq.local", llm_provider="fixture")
    a = s.register(RegisterBody(email="a@b.es", password="12345678")).user
    demo = s.register(RegisterBody(email="demo@posiq.local", password="12345678")).user
    s.repo.set_owner("s1", a.id)
    assert s.can_access(a, "s1") and not s.can_access(demo, "s1")
    # Estudios sin propietario (anteriores a las cuentas): solo los ve el usuario demo.
    assert s.can_access(demo, "antiguo") and not s.can_access(a, "antiguo")
    assert s.visible_ids(a, ["s1", "antiguo"]) == ["s1"]
    assert s.visible_ids(demo, ["s1", "antiguo"]) == ["antiguo"]
    assert service(llm_provider="deepseek").visible_ids(a, ["antiguo"]) == []


def test_rate_limiter_window() -> None:
    limiter = RateLimiter(2, ventana_s=60)
    assert limiter.hit("k") and limiter.hit("k")
    assert not limiter.hit("k")
    assert limiter.hit("otra")
    limiter.ventana_s = 0
    assert limiter.hit("k")


def test_rate_limiter_forgets_expired_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Las claves sin intentos en la ventana se borran: la memoria no crece con cada correo."""
    reloj = [1000.0]
    monkeypatch.setattr(acc.time, "monotonic", lambda: reloj[0])
    limiter = RateLimiter(1, ventana_s=60)
    for n in range(100):
        limiter.hit(f"correo:{n}@b.es")
    assert len(limiter) == 100
    reloj[0] += 61
    assert limiter.hit("otra")
    assert len(limiter) == 1
