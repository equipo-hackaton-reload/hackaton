# ADR 0019 · Auditoría técnica GEO de la web de la marca

- **Estado:** aceptado (contrato). Las piezas A–E se implementan en PRs posteriores.
- **Fecha:** 2026-10-21
- **Zona:** A (contrato `domain/web_audit_schemas.py` y `WebFetcher` en `ports.py`, `contract-change`).
  El diseño cubre también B, C, D y E.

## Contexto

posiq. mide si los asistentes de IA nombran a la marca. Pero no comprueba si los motores **pueden
leer** su web: robots.txt que bloquea a GPTBot, una portada que solo pinta texto con JavaScript, sin
JSON-LD de Organization, sin sitemap... Son causas técnicas, baratas de arreglar y verificables.

Encaja en el modelo de negocio. La propuesta es la puerta de entrada y el seguimiento es el ingreso
recurrente («posiq. no vende un score; vende un seguimiento con método»). La auditoría da:

- una línea base técnica;
- acciones `tecnico` con evidencia literal;
- un indicador adelantado que se vuelve a medir en cada ciclo (ADR 0016).

También responde al feedback del mentor sobre la capa determinista (ADR 0014): la auditoría es 100 %
determinista. Las descargas son I/O en un adaptador, el análisis es código puro y la IA solo redacta
el plan con las cifras ya calculadas.

## Decisión

### Capas

| Capa | Pieza | Zona | Qué hace |
|---|---|---|---|
| Contrato | `domain/web_audit_schemas.py`, `ports.WebFetcher` | A | **Este PR.** Modelos, catálogo, pesos, puntuación y puerto |
| Dominio | `domain/web_audit.py` | A | Analiza las `RespuestaWeb` (sin I/O) y construye `AuditoriaWeb` y `Finding` |
| Adaptador | `adapters/web/{httpx_fetcher,fixture}.py` | B | Descarga y fixture para el modo kit |
| Grafo y API | nodo `web_audit` y `GET /studies/{id}` | C | Orquesta, deja la `Trace` y expone el resultado |
| Web | tarjeta «¿Pueden los motores leer tu web?» | D | Pinta bloques, comprobaciones y evidencias |
| Plan y Word | `prompts/plan`, `adapters/export` | E | Acciones `tecnico` y sección en el Word |

`schemas.py` **no cambia**.

### Contrato (`web_audit_schemas.py`)

- **`RespuestaWeb`**: lo que devuelve `WebFetcher.get`. Lleva:
  - `url` y `url_final`;
  - `accept` pedido y `estado_http` (None si no hubo respuesta; entonces `error` es obligatorio);
  - `contenido`, truncado a `MAX_CONTENIDO_CHARS` = 500.000, y `truncado` (también si la lectura
    se cortó en `MAX_BYTES_DESCARGA`);
  - `cabeceras`, solo las de `CABECERAS_RELEVANTES` (`content-type`, `link`, `x-robots-tag`,
    `content-signal`, `last-modified`) y en minúsculas;
  - `duracion_ms` y `obtenido_en`.

  Un 4xx o 5xx no es un error del fetcher.
- **`AccesoBot`**: bot, motor (validado contra `BOT_MOTOR`), `permitido` (None sin robots.txt
  legible), `grupo_propio` y la `regla` literal que decide.
- **`SenalContenido`**: la línea Content-Signal literal y `ai_train`, `search` y `ai_input`.
- **`Comprobacion`**:
  - `id` de `CATALOGO`, con `bloque` y `peso` validados contra él;
  - `estado`: `ok`, `falla`, `no_aplica` o `error`;
  - `detalle`;
  - `evidencia` literal (máx. 500 caracteres; obligatoria en `ok` y `falla`);
  - `recurso`, la URL consultada;
  - `motores_afectados`, solo si falla.
- **`PuntuacionBloque`**: puntuación 0-100 (o None) y recuentos por estado.
- **`AuditoriaWeb`**:
  - una comprobación por id del catálogo y un acceso por bot;
  - `bloques` y `puntuacion` **recalculados en el validador** con `puntuar_bloque` y
    `puntuar_total`: nadie puede publicar una puntuación que no salga de las comprobaciones;
  - además `senal_contenido`, `tipos_schema`, `texto_visible_chars`, `tiempo_respuesta_ms`,
    `recursos` (resumen de cada descarga, sin cuerpo), `fetcher`, `origen` (`real` o `fixture`),
    `version` = `web_audit.v1` y `finding_ids`.

### Puerto `WebFetcher` (`ports.py`)

```python
class WebFetcher(Protocol):
    name: str

    def get(self, url: str, *, dominio: str, accept: str | None = None) -> RespuestaWeb: ...
```

- No lanza por errores de red ni por 4xx/5xx: los devuelve en `estado_http` y `error`.
- Hace GET sin ejecutar JavaScript, sigue redirecciones (a mano y revalidadas) y registra el
  tiempo de respuesta y las cabeceras relevantes.
- `dominio` es `Brand.dominio`: el fetcher solo descarga ese host y sus subdominios. Los requisitos
  de seguridad (destino, IP, redirecciones, tamaño y tiempo) son parte del contrato y están en
  «Grafo, trazas y API → Seguridad».

### Recursos que se descargan (`RECURSOS`)

`/robots.txt`, `/sitemap.xml`, `/` dos veces (normal y con `Accept: text/markdown`), `/llms.txt` y
siete rutas `/.well-known/`:

- `api-catalog`
- `openid-configuration`
- `oauth-authorization-server`
- `oauth-protected-resource`
- `mcp/server-card.json`
- `agent-skills/index.json`
- `ai-catalog.json`

Además:

- Se siguen las URLs `Sitemap:` de robots.txt (si no hay ninguna, se usa `/sitemap.xml`), pero
  solo las que cumplen `url_permitida(url, Brand.dominio)`: un `Sitemap:` a otro host (p. ej.
  `http://169.254.169.254/...`) se ignora y no se descarga.
- Se descargan hasta `MAX_PAGINAS_SITEMAP` = 3 páginas del sitemap que cumplan `url_permitida`,
  para buscar JSON-LD. Se eligen en el orden del sitemap.

En total son unas 16 descargas por auditoría.

### Bloques, comprobaciones y pesos (deterministas)

Los pesos son fijos y documentados, no percentiles: así no cambian entre clientes y se pueden
comparar entre mediciones.

| Bloque | Peso | Comprobación (peso en el bloque) |
|---|---|---|
| Descubrimiento | 25 | `robots_txt` (30): existe, no es HTML y tiene un grupo `User-agent:` · `sitemap` (25): XML `urlset`/`sitemapindex` con `<loc>` · `sitemap_en_robots` (15) · `cabeceras_link` (15): `Link` RFC 8288 con `canonical`/`alternate` · `markdown_negociado` (15): con `Accept: text/markdown` responde `text/markdown` |
| Contenido | 35 | `texto_sin_js` (30): ≥ 500 caracteres visibles sin JS · `jsonld_organization` (15) · `organization_sameas` (10) · `jsonld_faqpage` (10) · `jsonld_howto` (5) · `jsonld_article` (10): Article con `dateModified` · `jsonld_person` (5) · `jsonld_breadcrumb` (5) · `llms_txt` (10): título `# ` y al menos una URL |
| Acceso de bots de IA | 25 | `bots_ia_sin_bloqueo` (60) · `bots_ia_reglas_explicitas` (25): grupo propio para cada bot que alimenta a un motor medido · `content_signal` (15): `ai-train`, `search` y `ai-input` declarados |
| Rendimiento | 10 | `tiempo_respuesta` (100): portada 2xx en ≤ 2.000 ms. LCP, INP y CLS quedan fuera de alcance |
| Agentes / API | 5 | `api_catalog` (20) · `oauth_discovery` (15) · `oauth_protected_resource` (15) · `mcp_server_card` (20) · `agent_skills` (15) · `ai_catalog` (15). Informativo: para una clínica pesa poco y **no genera hallazgos** |

**Por qué estos pesos:**

- **Contenido pesa más.** Sin texto legible ni datos estructurados no hay nada que citar.
- **Descubrimiento y acceso van detrás.** Un bot bloqueado anula al motor entero, pero es una sola
  línea de arreglo.
- **Rendimiento** solo cuenta como umbral grueso.
- **Agentes/API** son preparación para agentes, no visibilidad hoy.

**Puntuación:**

- **Bloque** = 100 × Σ pesos `ok` / Σ pesos `ok`+`falla`.
- `no_aplica` y `error` no entran en el denominador: no se castiga lo que no se pudo ver.
- Si no queda ninguna comprobación evaluada, el bloque vale None.
- **Total** = media de los bloques con puntuación, ponderada por su peso y renormalizada a los
  bloques evaluados. Si ningún bloque tiene puntuación, el total es None.
- Las cifras se redondean a 2 decimales.

**Bots auditados (`BOT_MOTOR`):**

| Motor | Bots |
|---|---|
| ChatGPT | GPTBot, OAI-SearchBot, ChatGPT-User |
| Claude | ClaudeBot, Claude-SearchBot, Claude-Web |
| Perplexity | PerplexityBot, Perplexity-User |
| Gemini | Google-Extended |
| Sin motor medido | Applebot-Extended, CCBot |

Los bots sin motor medido se auditan y se muestran, pero no fijan `motores_afectados`.

**Reglas de `estado` (para `web_audit.py`):**

- **`error`:** sin respuesta (red) o con 5xx en el recurso que decide.
- **`falla`:** un 404, 410 o 403 en un recurso que debería existir. La evidencia es «HTTP 404».
- **`no_aplica`** solo cuando la comprobación depende de otra que no se cumple:
  - `organization_sameas` sin Organization;
  - `sitemap_en_robots` sin robots.txt;
  - `bots_ia_*` sin robots.txt: robots.txt ya falla y, sin él, todo está permitido.
- **robots.txt:** se interpreta según RFC 9309, con agrupación por `User-agent`, la regla más
  específica y `Allow` frente a `Disallow` del mismo largo. Decide si se puede rastrear `/`.

### Hallazgos técnicos (`Finding` normales, fuera de `detect_findings`)

Se generan como `F-web-propia` (ADR 0010), fuera de `detect_findings`: los 7 hallazgos del golden
no cambian. Los genera `web_audit.hallazgos_web(auditoria, evaluaciones, runs, brand_id)`.

- **`F-web-bots-bloqueados`** (impacto L): algún bot que alimenta a un motor medido tiene la
  portada prohibida.
  - `cifra` = número de motores afectados (`recuento`).
  - En la descripción, la regla literal.
- **`F-web-<bloque>`** para descubrimiento, contenido y rendimiento: si la puntuación del bloque
  es < 50.
  - Impacto L si es < 30; M en otro caso.
  - `cifra` = puntuación del bloque (`puntos`) y `origen_cifra` = `web_audit.v1:<bloque>`.
- **Acceso de bots:** solo genera `F-web-bots-bloqueados`.
- **Agentes/API:** nunca genera hallazgos.
- **`evaluation_ids`**, con el criterio del ADR 0010: las evaluaciones **espontáneas** de la marca
  foco en las que la marca **no aparece**, de las ejecuciones de los `motores_afectados` del
  hallazgo (la unión de los de sus comprobaciones en falla).
  - Si no hay ninguna, el hallazgo no se emite: sin evidencia no hay hallazgo.
  - La prueba técnica va en `Comprobacion.evidencia`. La descripción cita el id de la comprobación.
- **`confianza`:** 0,9 si la evidencia es literal (robots.txt, cabecera o JSON-LD) y 0,7 si
  depende de un umbral (texto sin JS, tiempo).

### Modo kit y demo

- Los dominios del kit son `.example`: no se pueden descargar.
- `Settings.web_audit: Literal["off", "fixture", "real"]` vale `off` por defecto. En modo kit,
  `real` se degrada a `fixture`.
- **`fixture`:** `FixtureWebFetcher` (B) sirve respuestas fijas por dominio desde
  `tests/fixtures/web/<dominio>/`, con `origen="fixture"`. Los hallazgos de una auditoría fixture
  **no entran en `findings` ni en el plan**: viajan aparte en `state["auditoria_web"]` y se
  muestran como ejemplo.
- Las cifras canónicas no cambian: 25,93, 8.ª de 10, 25,9 → 30,8, los 7 hallazgos y las 9
  acciones de Alborada. Lo fija un test e2e con `web_audit=fixture`.
- **`real`** (con dominio real): los hallazgos se añaden a `findings` antes de `plan`.

### Grafo, trazas y API (C)

- **Nodo `web_audit`:** va entre `judge` y `analyze` (necesita las evaluaciones para
  `evaluation_ids`). Es `external=True`, con la política de reintentos del grafo. Si
  `Brand.dominio` es None o `web_audit=off`, devuelve `auditoria_web=None`.
- **Trazas:** cada descarga deja una `Trace` con:
  - `nodo="web_audit"` y `modelo="http:<fetcher.name>"`;
  - `prompt_version="web_audit.v1"`;
  - `tokens_in=tokens_out=0` y `coste_eur=0`;
  - `duracion_ms` = la de la respuesta (0 si no la hubo).
- **`GET /estimate`:** no cambia (coste 0).
- **`GET /studies/{id}`:** añade `auditoria_web: AuditoriaWeb | null`. Contenedor en
  `application/diferencial.py`.
- **Checkpointer:** admite los modelos de `web_audit_schemas`.
- **Seguridad (requisitos del contrato `WebFetcher.get`; los tests del PR de B los prueban):**
  `Brand.dominio` lo escribe cualquier usuario registrado, así que el dominio y su DNS se tratan
  como hostiles (SSRF hacia la red interna o los metadatos de la nube, y denegación de servicio).
  - **Destino:** `get(url, *, dominio, accept)` solo conecta si
    `web_audit_schemas.url_permitida(url, dominio)`: esquema `http`/`https`, sin credenciales en
    la URL, puerto por defecto (80/443) y host = `Brand.dominio` o un subdominio suyo. Vale para
    las rutas fijas, las URLs `Sitemap:`, las páginas del sitemap y **cada `Location`**. Si no se
    cumple: `estado_http=None`, `error="url_no_permitida"`, sin conexión.
  - **Redirecciones:** se siguen a mano (no con `follow_redirects` del cliente), como mucho
    `MAX_REDIRECCIONES` = 5 saltos, revalidando en cada uno el destino y la IP. Pasado el máximo:
    `error="demasiadas_redirecciones"`.
  - **IP y DNS rebinding:** en cada salto el host se resuelve **una vez**; si alguna de las IPs no
    cumple `web_audit_schemas.ip_permitida` se rechaza (`error="ip_no_permitida"`). Se rechazan
    privadas, loopback, link-local (incluido 169.254.169.254), CGNAT (100.64/10), ULA (fc00::/7),
    multicast, reservadas, no especificadas, las IPv4 mapeadas en IPv6 (`::ffff:10.0.0.1`) y las
    IPv6 que encapsulan IPv4 (NAT64, 6to4, Teredo). La conexión se hace **a la IP ya validada**
    (transporte con la IP fijada y `Host`/SNI del nombre original), sin segunda resolución.
  - **Tamaño:** el cuerpo se lee en streaming y se corta a `MAX_BYTES_DESCARGA` = 2 MB **contados
    tras descomprimir** (una bomba gzip se corta igual), con `truncado=True`. Nunca `resp.text` del
    cuerpo entero. Después el texto se trunca a `MAX_CONTENIDO_CHARS`.
  - **Tiempo:** `TIMEOUT_TOTAL_RECURSO_S` = 10 s es el tope **total** por recurso (conexión,
    redirecciones y lectura completa), no por lectura: un servidor que manda un byte cada 9 s se
    corta a los 10 s (`error="timeout"`). Con unas 16 descargas, una auditoría dura como mucho
    unos 160 s.
  - User-agent propio (`posiq-audit/1`).
  - El contenido es DATO: nunca entra en instrucciones de un LLM. Lo que vuelve al usuario
    (`evidencia`, `detalle`) sale solo de respuestas que pasaron todos estos filtros.
  - **Tests exigidos en el PR de B:** `Sitemap:` y `Location` a otro host o a una IP interna no se
    descargan; más de 5 redirecciones; DNS que resuelve a 10.x / 127.0.0.1 / `::ffff:127.0.0.1`;
    la conexión usa la IP validada; cuerpo comprimido que descomprime por encima del límite;
    servidor lento cortado por el tope total.

### Web (D)

Tarjeta «¿Pueden los motores leer tu web?»:

- puntuación total y por bloque (barras 0-100; «sin datos» si es None);
- lista de comprobaciones con su estado (`ok` / `falla` / `no aplica` / `no verificable`) y la
  evidencia literal desplegable;
- la tabla de bots con su motor y la regla;
- con `origen="fixture"`, la etiqueta «Ejemplo (modo kit)».

### Plan y Word (E)

- **`prompts/plan`:** recibe los hallazgos técnicos ya calculados. Las acciones que los cubren
  usan la palanca `tecnico` y citan sus `finding_ids`. El LLM no inventa cifras: usa las de la
  auditoría.
- **Textos por motor:** la relación con cada motor sirve para redactar el plazo esperado. No son
  cifras del producto.
  - **Perplexity** rastrea en tiempo real: el efecto llega en semanas.
  - **Gemini** se apoya en el índice y el Knowledge Graph de Google (schema, Organization/sameAs,
    Google Business Profile).
  - **ChatGPT** depende más de la presencia en fuentes externas (directorios, medios,
    Wikipedia/Wikidata, Reddit/LinkedIn) y tarda meses.

  Esto justifica la cadencia **trimestral** del seguimiento.
- **Word:** sección «Preparación técnica de la web», con la puntuación por bloque, las
  comprobaciones que fallan y su evidencia, y la nota de origen si es fixture.

### Seguimiento (ADR 0016)

La puntuación total de la auditoría es un indicador adelantado más de la serie. Se re-mide con la
misma `version` del catálogo. Si el catálogo cambia (`web_audit.v2`), la serie lo marca como **no
comparable** en ese indicador.

### Implementación del dominio (`domain/web_audit.py`)

- `analizar_web(respuestas, *, study_id, brand_id, dominio, origen, fetcher, obtenido_en,
  sitemaps, paginas)` (alias `auditar`) y `hallazgos_web(auditoria, evaluaciones, runs, *,
  prompts, brand_id=None)` (alias `hallazgos_tecnicos`). `prompts` hace falta para saber qué
  evaluación es espontánea.
- Agentes/API: una comprobación que falla no lleva `motores_afectados` (es informativa).
- 406 también es `falla` (la portada no tiene variante markdown).
- `content_signal` se evalúa también con la cabecera `Content-Signal` aunque falte robots.txt.

## Consecuencias

- **`contract-change` aditivo:** `ports.py` gana `WebFetcher` e importa `RespuestaWeb`. Ningún
  dependiente existente cambia. Las reglas de destino e IP (`url_permitida`, `ip_permitida`) y los
  límites (`MAX_BYTES_DESCARGA`, `TIMEOUT_TOTAL_RECURSO_S`, `MAX_REDIRECCIONES`) viven en
  `domain/web_audit_schemas.py`, puros y probados, para que el adaptador y su fixture los
  compartan.
- **Dependencias:** B añadirá `httpx` (ya transitiva) como dependencia directa al implementar el
  adaptador. El dominio no la necesita.
- **Guía GEO como checklist:** la guía se usa para decidir qué comprobar. Sus estadísticas no se
  convierten en cifras del producto.
- **Límites:**
  - Sin ejecutar JavaScript no se ve lo que pinta una SPA. Es justo lo que queremos medir, porque
    los rastreadores de IA tampoco lo ejecutan.
  - Solo se auditan la portada y 3 páginas.
  - El tiempo de respuesta es un único GET, no un estudio de rendimiento.
