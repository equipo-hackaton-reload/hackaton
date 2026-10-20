"""Errores comunes de los adaptadores."""

from pydantic import SecretStr


class MissingCredentialError(RuntimeError):
    """Falta la clave de un proveedor. Se lanza al llamar, nunca al construir el adaptador."""

    def __init__(self, variable: str, adaptador: str) -> None:
        super().__init__(
            f"{adaptador}: falta la variable de entorno {variable}. Defínela en .env "
            f"(ver .env.example) antes de hacer llamadas."
        )
        self.variable = variable


def require_secret(secret: SecretStr, variable: str, adaptador: str) -> str:
    """Valor de `secret` o `MissingCredentialError` si está vacío."""
    value = secret.get_secret_value()
    if not value:
        raise MissingCredentialError(variable, adaptador)
    return value
