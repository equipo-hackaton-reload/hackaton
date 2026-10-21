# ADR 0010 · Mapa de fuentes del sector y oportunidades de fuente por marca

- **Estado:** aceptado
- **Fecha:** 2026-10-21
- **Zona:** A (`domain/source_map.py`; contratos en `domain/source_map_schemas.py`)

## Contexto

Saber qué fuentes citan los motores en un sector sirve para dos cosas:

- Decirle a una marca en qué fuentes la citan menos que a sus competidores.
- Dar un punto de partida a un cliente nuevo que todavía no tiene datos propios.

Hay dos problemas con los datos:

1. **`Evaluation.tipo_fuente` no vale.** En las evaluaciones de Alborada está vacío en el 92 %. Todo
   se calcula con `Run.fuentes` cruzado con el catálogo.
2. **Mezclar estudios de varias marcas puede exponer datos de un cliente.** Hay que agregar y
   anonimizar el mapa.

## Decisión

Módulo puro `domain/source_map.py`. Recibe los estudios ya cargados (`DatosEstudio`: mercado,
prompts, ejecuciones y evaluaciones) y no hace I/O.

### Definiciones

- **Cita:** un dominio en `Run.fuentes`. Si el mismo dominio sale dos veces en una ejecución,
  cuenta una vez.
- **Tipo de fuente:** el del catálogo, también por dominio padre (`blog.x.com` → `x.com`). Si el
  dominio no está en el catálogo, se usa el tipo que traiga la ejecución.
- **Marcas de una respuesta:** las marcas con `aparece` en esa ejecución que además estén en
  `Run.marcas_a_evaluar` (la misma elegibilidad que en `metrics`).
- **Web propia (`propio`):** un dominio de tipo «Web propia» en el catálogo, o el `Brand.dominio`
  de cualquier marca de los mercados (también con `www.` o como subdominio). Así se detecta la web
  de una marca aunque falte en el catálogo. El resto de fuentes es `ganado`.
- **Segmentos:** son los del resto del dominio. Se usan tres claves:
  - `tipo:espontaneo` y `tipo:asistido`, la separación de `metrics`.
  - `fase:<fase del embudo>`.
  - `ciudad:<Ciudad>`. Solo existe para los prompts que llevan ciudad.
- **Cuotas:** son la fracción de todas las citas, también las de fuentes que no entran en el mapa,
  así que pueden sumar menos de 1. Se calculan en tres ámbitos:
  - `cuota_citas`, sobre todas las citas del sector.
  - `por_motor`, sobre las citas de cada motor.
  - `por_segmento`, sobre las citas de cada segmento.

  Van redondeadas a 4 decimales.

### Anonimización

1. **Mínimo de dos marcas.** Una fuente entra en el mapa solo si la citan respuestas sobre al menos
   `MIN_MARCAS_SECTOR` = 2 marcas distintas. Para contarlas se unen las marcas de todas las
   respuestas que la citan. El umbral no se puede bajar: `min_marcas < 2` da error.
2. **Webs propias agregadas.** Un dominio «Web propia» identifica a una marca, así que todas las
   webs propias se suman en una sola entrada:
   - Su dominio es el centinela `WEBS_PROPIAS = "(webs propias)"`, con tipo «Web propia» y
     propiedad `propio`.
   - Ningún dominio de marca aparece en el mapa.
   - La regla 1 también se aplica a esta entrada.
3. **Solo recuentos y cuotas.** El mapa no dice qué marca acompaña a qué fuente. Se puede exportar
   a otro cliente del sector.

**Limitación:** si la web de una marca no está en el catálogo ni es el `Brand.dominio` de ninguna
marca de los mercados, se trata como una fuente ganada más. Con un solo estudio el mapa resume los
datos de las marcas de ese mercado. Por eso las fuentes de un cliente concreto solo se anonimizan
cuando hay varios estudios del sector.

### Oportunidades por marca (`oportunidades_fuente`)

Se miran solo las respuestas **espontáneas**, como en `metrics._source_gap`: interesa qué fuentes
acompañan a los competidores cuando el usuario no nombra a nadie.

- **`presencia_marca`:** de las respuestas espontáneas en las que aparece la marca, la fracción que
  cita la fuente. Vale 0 si la marca no aparece en ninguna.
- **`presencia_competidores`:** la media simple de esa fracción entre las demás marcas del mercado.
  Solo entran las que tienen al menos `MIN_APARICIONES_COMPETIDOR` = 5 apariciones espontáneas,
  para que no pese una marca con una sola respuesta.
- **Web propia:** «citar la fuente» quiere decir citar la web de cada marca. Para Alborada se mira
  `alboradavision.example` y para cada competidor, su propia web.
- **Cálculo:**
  - `gap` = competidores − marca. Solo se devuelven los gaps positivos.
  - `valor` = `cuota_sector` × `gap`.
  - Se ordenan por `valor`; a igualdad, por dominio o tipo.
- **Dos niveles:**
  - `nivel="dominio"`: cada fuente del mapa.
  - `nivel="tipo"`: las fuentes ganadas del mapa agrupadas por tipo. La cuota del tipo es la suma
    de las cuotas de sus fuentes.
- **`evaluation_ids`:** se toman las respuestas espontáneas que citan la fuente y en las que la
  marca no aparece. Las evidencias son las apariciones de los competidores en ellas y la evaluación
  de ausencia de la marca. Sin evidencias no hay oportunidad.

**Por qué no se reutiliza `_source_gap`:** compara recuentos con el líder y solo da dominios. Aquí
hace falta una fracción comparable entre marcas con distinto número de apariciones, frente a todos
los competidores y ponderada por la cuota del sector. `top_fuentes` es por marca y no agrega el
sector. Sí se reutilizan `findings.confidence_for` y la elegibilidad de `metrics`.

### Umbrales de `puntuacion` (fijos)

| Puntuación | `valor` | Lectura |
|---|---|---|
| Alta | ≥ 0,005 | p. ej. una fuente con el 5 % de las citas y 10 pp de brecha |
| Media | ≥ 0,002 | p. ej. 5 % de cuota y 4 pp de brecha |
| Baja | < 0,002 | la brecha cabe en el ruido de una muestra de ~100 respuestas |

**Justificación con el kit:** se calcularon las oportunidades de las 10 marcas, cada una como foco.

| Nivel | n | p50 | p75 | p90 | p95 | máx. | Alta / Media / Baja |
|---|---|---|---|---|---|---|---|
| dominio | 81 | 0,0010 | 0,0019 | 0,0030 | 0,0035 | 0,0084 | 2 / 16 / 63 |
| tipo | 33 | 0,0027 | 0,0055 | 0,0113 | 0,0118 | 0,0220 | 10 / 8 / 15 |

- **Alta** queda por encima del p95 por dominio: es la excepción.
- **Media** recoge aproximadamente el 20 % superior por dominio.
- Por tipo los valores son mayores porque las cuotas se suman.

Los umbrales son fijos, no percentiles: así no cambian al añadir estudios y se pueden comparar
entre mediciones.

### Hallazgo de web propia (`hallazgo_web_propia`)

- **Cifra:** las citas a la web de la marca divididas entre todas las citas de las respuestas en
  las que aparece, espontáneas y asistidas.
- **Comparación:** con la media de esa misma cuota en los competidores (cada uno con su web) y con
  el peso de todas las webs propias en esas respuestas.
- **Impacto:** L si la cuota es menos de la mitad de la media de los competidores, M si es menor
  que la media y S en otro caso.
- **Salida:** un `Finding` con `id="F-web-propia"` y `unidad="fraccion"`. Sus `evaluation_ids` son
  las apariciones de la marca (el denominador).
- **Fuera de `detect_findings`:** así se mantienen intactos los 7 hallazgos que fijan los golden.

### Punto de partida para un cliente nuevo (`punto_de_partida`)

- **Fuentes:** solo las ganadas. Las webs propias de otras marcas no le sirven a un cliente nuevo;
  su peso sale aparte en `cuota_webs_propias`.
- **Listas:** las `top_n` prioritarias del sector, por tipo y por motor.
- **Filtro del brief:** si el mapa tiene datos de sus ciudades, la relevancia es la cuota media en
  esas ciudades y se quitan las fuentes que no se citan en ninguna. Las ciudades sin datos salen en
  `avisos`.
- **Servicios:** el mapa no segmenta por servicio, así que no filtran; también sale un aviso.

## Resultados con el kit (oftalmología, 1 estudio, 624 ejecuciones, 1.631 citas, 10 marcas)

En el kit, todas las fuentes se citan con 8 marcas o más: la anonimización no quita ninguna.

**Top 5 fuentes del sector**

| # | Fuente | Tipo | Citas | Cuota |
|---|---|---|---|---|
| 1 | (webs propias), 10 dominios agregados | Web propia | 185 | 11,3 % |
| 2 | directoriomedico.example | Directorio / comparador | 141 | 8,6 % |
| 3 | diariosalud.example | Medio | 139 | 8,5 % |
| 4 | comparaclinicas.example | Directorio / comparador | 136 | 8,3 % |
| 5 | saludactual.example | Medio | 129 | 7,9 % |

Por tipo:

| Tipo | Cuota |
|---|---|
| Medio | 23,4 % |
| Ranking / institución | 21,9 % |
| Directorio / comparador | 17,0 % |
| Plataforma de reseñas | 16,5 % |
| Web propia | 11,3 % |
| Red social / foro | 9,8 % |

**Web propia de Alborada.** `alboradavision.example` recibe **33 de las 564 citas (5,9 %)** de las
201 respuestas en las que aparece Alborada. El conjunto de las webs propias recibe el 12,4 % de esas
citas, y la media de sus competidores es del 3,3 %. Alborada está por encima de esa media
(impacto S): su web no es el problema.

**Top 3 oportunidades de Alborada** (por dominio, respuestas espontáneas):

| # | Fuente | Cuota | Alborada | Competidores | Valor | Puntuación |
|---|---|---|---|---|---|---|
| 1 | wikipedia.org | 5,7 % | 11,8 % | 17,2 % | 0,0031 | Media |
| 2 | comparaclinicas.example | 8,3 % | 21,5 % | 22,0 % | 0,0004 | Baja |
| 3 | rankingclinicas.example | 5,3 % | 14,0 % | 14,3 % | 0,0002 | Baja |

Por tipo, las dos oportunidades son Media:

| Tipo | Valor |
|---|---|
| Directorio / comparador | 0,0032 |
| Ranking / institución | 0,0031 |

**Lectura.** Cuando Alborada aparece, las fuentes que la acompañan son casi las mismas que las de
la media de sus competidores. Su problema principal es que aparece menos, no con qué fuentes
aparece. La brecha concreta con el líder sigue en el hallazgo `F-fuente-lider` (`_source_gap`).

## Consecuencias

- **Para C (Walter):** `SqlStudyRepo` hoy no puede listar estudios por sector, porque el sector
  solo está dentro del JSON del brief. Para enchufar el mapa hace falta:
  - Una consulta `StudyRepo.list_by_sector(sector) -> list[Study]`. Lo ideal es una columna
    `sector` indexada o un filtro sobre `brief.sector`.
  - Cargar de cada estudio su mercado confirmado, prompts, ejecuciones y evaluaciones, y construir
    un `DatosEstudio`.
  - Pasar los estudios y el catálogo a `mapa_fuentes(sector, estudios, catalogo)`.
- **Contratos:** `schemas.py`, `ports.py` y `source_map_schemas.py` no cambian.
  `FuentePrioritaria` y `PuntoDePartida` viven en `source_map.py`.
- **Cifras protegidas:** la cifra canónica (25,93) y los 7 hallazgos de `detect_findings` no
  cambian. Lo fija `tests/golden/test_source_map_golden.py`.
