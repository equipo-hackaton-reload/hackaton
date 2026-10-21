# ADR 0015 · Cuentas de usuario y propiedad de los estudios

- **Estado:** aceptado
- **Fecha:** 2026-10-21
- **Zona:** C (`interfaces/api/auth.py`, `application/accounts.py`, `application/security.py`,
  `adapters/repo/accounts.py`)

## Contexto

posiq. vende un seguimiento: línea base y re-mediciones trimestrales de la misma marca. Para eso
cada cliente tiene que ver solo sus estudios. Hasta ahora la API no tenía cuentas: el login era
solo del navegador y `GET /studies` listaba los estudios de todo el mundo.

## Decisión

1. **Cuentas con correo y contraseña, verificadas por código.** `POST /auth/register` crea el
   usuario sin verificar y emite un código de 6 dígitos; `POST /auth/verify` lo comprueba;
   `POST /auth/login` devuelve un token Bearer. El correo se normaliza a minúsculas; la contraseña
   tiene al menos 8 caracteres.
2. **Sin dependencias nuevas.** Contraseñas y códigos con `hashlib.scrypt` (sal aleatoria de 16
   bytes; n=2¹⁴, r=8, p=1 por defecto, configurables con `AUTH_SCRYPT_*`). El hash guarda sus
   parámetros (`scrypt$n$r$p$sal$hash`), así que subirlos no invalida los antiguos. Comparación en
   tiempo constante. Un login con un correo inexistente calcula un hash de relleno y devuelve el
   mismo 401 que una contraseña mala.
3. **Tokens opacos.** `secrets.token_urlsafe(32)`; en la base solo su sha256. Caducan a las
   `AUTH_TOKEN_TTL_H` horas (7 días). `POST /auth/logout` borra la sesión.
4. **Códigos de verificación.** Caducan a los 15 minutos; tras 5 fallos, 429 hasta pedir otro con
   `POST /auth/verify/reenviar` (que responde 202 exista o no el correo). **No hay proveedor de
   correo**: el código se escribe en el log del servidor (nivel WARNING). Con `AUTH_DEV_CODES`
   activo se devuelve además como `codigo_dev`; sin fijar, solo se activa con
   `LLM_PROVIDER=fixture`, para la demo y los tests.
5. **Propiedad fuera del modelo `Study`.** Una tabla `study_owner` (`study_id → user_id`) en la
   misma base que los estudios. `schemas.py` y `ports.py` no cambian; el puerto `AccountRepo` vive
   en `application/accounts.py`. `create_all` añade las tablas `user`, `session`, `verification` y
   `study_owner` sin tocar las existentes.
6. **Protección.** Todo exige `Authorization: Bearer` (401) salvo `/health`, `/auth/register`,
   `/auth/verify`, `/auth/verify/reenviar`, `/auth/login` y la documentación de FastAPI (`/docs`,
   `/openapi.json`). Un estudio ajeno responde **404, no 403**, con el mismo mensaje que uno que no
   existe, en lectura, `resume`, `remeasure`, `evaluations`, `traces` y `export`. La re-medición
   hereda el propietario del original.
7. **Estudios anteriores a las cuentas.** No tienen propietario y no los ve nadie, salvo el correo
   de `AUTH_DEMO_USER` si está definido. Una re-medición suya pasa a ser de ese usuario.
8. **Endurecimiento.** Los POST JSON (`/auth/*` y `resume`) exigen `Content-Type:
   application/json` (415). El brief de `POST /studies` tiene un máximo de `BRIEF_MAX_BYTES`
   (200 KB, 413). Registro, verificación, reenvío y login admiten `AUTH_RATE_LIMIT_POR_MIN`
   intentos por minuto y cliente (429).

## Consecuencias

- La web tiene que pedir login y mandar el token (zona D). Hasta entonces, la web contra la API
  real recibe 401; con mocks sigue funcionando.
- `scripts/demo_kit.py` registra, verifica (con `codigo_dev`) y entra como `demo@posiq.local`.
- **Limitaciones conocidas:** el límite de intentos vive en memoria del proceso (se pierde al
  reiniciar y no se comparte entre workers); no hay recuperación de contraseña ni correo real; las
  sesiones caducadas se borran solo cuando alguien intenta usarlas.
