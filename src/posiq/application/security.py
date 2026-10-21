"""Primitivas de seguridad de las cuentas, sin dependencias nuevas (solo la biblioteca estándar).

- Contraseñas y códigos de verificación: `hashlib.scrypt` con sal aleatoria de 16 bytes. El hash
  guarda sus parámetros (`scrypt$n$r$p$sal$hash`, en base64 url), así que subir `n` en `Settings`
  no invalida los hashes antiguos. Por defecto n=2**14, r=8, p=1 (≈16 MiB y unas decenas de ms por
  hash), el mínimo que recomienda OWASP para scrypt.
- Comparación en tiempo constante (`hmac.compare_digest`).
- Tokens de sesión: `secrets.token_urlsafe(32)`; en la base solo se guarda su sha256.
- Códigos de verificación: 6 dígitos con `secrets.randbelow`.
"""

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass

PREFIJO = "scrypt"
SAL_BYTES = 16
HASH_BYTES = 32


@dataclass(frozen=True)
class ScryptParams:
    n: int = 2**14
    r: int = 8
    p: int = 1

    @property
    def maxmem(self) -> int:
        # scrypt usa unos 128·n·r·p bytes; margen para que OpenSSL no lo rechace.
        return 256 * self.n * self.r * self.p + 1024 * 1024


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _scrypt(secreto: str, sal: bytes, params: ScryptParams) -> bytes:
    return hashlib.scrypt(
        secreto.encode("utf-8"),
        salt=sal,
        n=params.n,
        r=params.r,
        p=params.p,
        maxmem=params.maxmem,
        dklen=HASH_BYTES,
    )


def hash_secret(secreto: str, params: ScryptParams | None = None) -> str:
    """Hash scrypt con sal aleatoria: `scrypt$n$r$p$sal$hash`."""
    params = params or ScryptParams()
    sal = secrets.token_bytes(SAL_BYTES)
    digest = _scrypt(secreto, sal, params)
    return f"{PREFIJO}${params.n}${params.r}${params.p}${_b64(sal)}${_b64(digest)}"


def verify_secret(secreto: str, guardado: str) -> bool:
    """True si `secreto` corresponde a `guardado`; False ante cualquier hash mal formado."""
    try:
        prefijo, n, r, p, sal, digest = guardado.split("$")
        if prefijo != PREFIJO:
            return False
        params = ScryptParams(int(n), int(r), int(p))
        calculado = _scrypt(secreto, _unb64(sal), params)
        return hmac.compare_digest(calculado, _unb64(digest))
    except (ValueError, TypeError):
        return False


def new_token() -> str:
    """Token de sesión opaco (43 caracteres url-safe, 256 bits)."""
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    """sha256 del token: lo único que se guarda. Un token robado de la base no sirve."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_code() -> str:
    """Código de verificación de 6 dígitos (con ceros a la izquierda)."""
    return f"{secrets.randbelow(10**6):06d}"
