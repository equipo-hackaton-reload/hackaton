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

## Revisión posterior (fixes de #36)

9. **Intentos atómicos.** `AccountRepo.count_attempt` suma el intento con un solo
   `UPDATE verification SET intentos = intentos + 1 WHERE email = ? AND intentos < 5 RETURNING …`
   **antes** de comparar el código. Antes era lectura-modificación-escritura sin bloqueo y, con las
   rutas `def` en el threadpool, peticiones simultáneas comparaban más de 5 veces.
10. **Reenvíos limitados.** Reenviar da un código nuevo (con sus 5 intentos), pero cada cliente
    solo puede pedir 3 por hora para un correo (`REENVIOS_POR_HORA`; el cuarto, 429, exista o no
    el correo) y el correo 10 en total (`REENVIOS_POR_CORREO_HORA`). Cota: 55 comparaciones por
    correo y hora frente a un código de 6 dígitos. En login, verificación y reenvío el límite por
    minuto tiene tres claves: IP y ruta, IP y correo (`AUTH_RATE_LIMIT_POR_MIN`), y el correo desde
    cualquier IP con un umbral 5 veces mayor (`FACTOR_LIMITE_CORREO`); verificar y reenviar
    comparten las claves del correo. Las claves se comprueban en ese orden y con cortocircuito: una
    petición rechazada no se apunta en las siguientes, así que no gasta el cupo global del correo
    ni crea claves nuevas. `RateLimiter` borra las claves sin intentos en la ventana (una pasada
    por ventana), así que su memoria la acota el tráfico reciente y no los correos vistos.
    **Riesgo aceptado (bloqueo de cuentas ajenas).** Con los cupos solo por correo (revisión
    anterior), 8 peticiones por hora desde una IP dejaban a un tercero sin poder verificar y 10
    logins por minuto le cerraban el login. Ahora un atacante con una sola IP solo gasta su propio
    cupo; para bloquear el correo de otro necesita repartir las peticiones entre al menos 4 IPs
    por hora (reenvíos) o 5 por minuto (login). Sigue siendo posible quemar los 5 intentos del
    código pendiente o sustituirlo con un reenvío: no filtra nada y el dueño pide otro código. Se
    acepta para el prototipo; en producción, correo con enlace firmado, CAPTCHA tras el primer
    429 y límites en un almacén compartido (Redis) en lugar de la memoria del proceso.
11. **Enumeración.** `POST /auth/register` sigue respondiendo **409** si el correo existe: la web
    (PR #38) lo usa para ofrecer el login y `scripts/demo_kit.py` para saltarse el alta. **Riesgo
    aceptado**: revela qué correos están registrados, acotado por el límite de intentos por IP. Lo
    que sí se iguala es el tiempo: el alta de un correo existente calcula los mismos dos hashes
    scrypt que una nueva, y `/auth/verify/reenviar` calcula un hash también cuando el correo no
    existe o ya está verificado (responde 202 en ambos casos).
12. **Cuenta de demo solo en modo demo.** La contraseña de `demo@posiq.local` está en el repo
    (`scripts/demo_kit.py`). Esa cuenta y los privilegios de `AUTH_DEMO_USER` (ver los estudios
    sin propietario) solo existen con `demo_activo`: los códigos de desarrollo activos, que por
    defecto solo lo están con `LLM_PROVIDER=fixture`. Con el LLM real (y sin
    `AUTH_DEV_CODES=true` explícito), alta y login de esa cuenta responden 403
    `cuenta_demo_desactivada`, sus sesiones dejan de valer y `AUTH_DEMO_USER` se ignora con un
    aviso en el log. Así una base usada en la demo y luego en real no deja entrar con la
    contraseña publicada.
13. **Brief en streaming.** `POST /studies` lee el cuerpo por trozos y corta con 413 en cuanto pasa
    de `BRIEF_MAX_BYTES` (más 64 KB de margen en multipart), sin fiarse de `Content-Length`
    (que falta con `Transfer-Encoding: chunked`).

## Consecuencias

- La web tiene que pedir login y mandar el token (zona D). Hasta entonces, la web contra la API
  real recibe 401; con mocks sigue funcionando.
- `scripts/demo_kit.py` registra, verifica (con `codigo_dev`) y entra como `demo@posiq.local`.
- **Limitaciones conocidas:** el límite de intentos vive en memoria del proceso (se pierde al
  reiniciar y no se comparte entre workers), y lo mismo el de reenvíos por hora; no hay
  recuperación de contraseña ni correo real; las sesiones caducadas se borran solo cuando alguien
  intenta usarlas; el 409 del alta revela si un correo existe (riesgo aceptado, punto 11).
