# Diccionario de datos

Descripción de todos los ficheros del kit. Todos los ficheros del caso están en la carpeta `caso_oftalmologia`.

> **Datos sintéticos.** Todas las marcas, dominios y respuestas son inventados. Reproducen la **estructura** y los **patrones** de un estudio real, pero no el comportamiento real de ningún LLM.

## 0. Notas técnicas rápidas

- Los CSV están en **UTF-8 con BOM**. Para leerlos sin problemas en Python (pandas): `encoding="utf-8-sig"`. Excel los abre bien.
- Separador: coma. Los textos con comas o saltos de línea van entrecomillados.
- Las columnas con varios valores usan ` | ` (barra con espacios) como separador en `marcas.csv` y `Marcas a evaluar`, y `, ` (coma + espacio) en las listas de dominios.

## 1. Mapa de ficheros y cómo se relacionan

```
 marcas.csv ─────────────┐
 banco_prompts.csv ──┐   │
                     ▼   ▼
              ejecuciones.csv ───────► (vuestro sistema evalúa)
              (ENTRADA en bruto)
                     │ Fuentes citadas
                     ▼
              fuentes_catalogo.csv
```

| Fichero | Para qué sirve | Filas |
|---|---|---:|
| `marcas.csv` | Las 10 marcas del estudio, su nivel, rol, dominio y alias | 10 |
| `banco_prompts.csv` | Las 25 plantillas de prompt del banco | 25 |
| `ejecuciones.csv` | **Entrada en bruto**: cada respuesta de cada motor, tal y como la devolvería la API. **Sin evaluar** | 624 |
| `fuentes_catalogo.csv` | Catálogo de dominios y su tipo y calidad | 25 |
| `muestra_evaluada.csv` | **15 ejecuciones ya evaluadas** (ver sección 5) para entender el esquema y calibrar vuestro evaluador | 133 |

**Las respuestas no vienen evaluadas.** Detectar las marcas, medir la posición y la fuerza de la recomendación, el sentimiento y el tipo de fuente es parte de vuestro trabajo. En la sección 5 tenéis el esquema de evaluación recomendado y una muestra ya evaluada.

**Volumen del estudio:** 25 plantillas → **52 prompts instanciados** × 4 motores × 3 repeticiones = **624 ejecuciones**.

## 2. `marcas.csv`

| Columna | Descripción |
|---|---|
| `Marca` | Nombre completo de la marca |
| `Nivel` | `foco` (4 marcas con prompts propios) o `contexto` (6 marcas detectadas en las mismas respuestas) |
| `Rol` | Papel de la marca en el estudio: marca del brief, líder de referencia, competidor directo o contexto (con el líder real del mercado indicado) |
| `Dominio_propio` | Dominio de la web de la marca (ficticio, `.example`) |
| `Alias` | Otros nombres con los que puede aparecer en un texto, separados por ` | ` |

## 3. `banco_prompts.csv`

| Columna | Descripción |
|---|---|
| `Prompt_ID` | Identificador único. Formato `SECTOR-FAMILIA-nº` (p. ej. `OFT-DP-01`) |
| `Sector` | Sector y subsector |
| `Familia` | Una de las 9 familias de prompt (ver metodología) |
| `Intención` | Fase del embudo: Descubrimiento, Comparación, Validación o Decisión |
| `Prioridad` | `P1` críticos · `P2` profundidad |
| `Uso` | `Publicable` (resultados que se pueden comunicar) o `Diagnóstico` (uso interno) |
| `Instanciación` | `generico`, `ciudad`, `marca` o `par` |
| `Prompt (plantilla)` | Texto con marcadores `[MARCA_A]`, `[MARCA_B]` o `[CIUDAD]` |
| `Notas de instanciación` | Cómo se instancia y qué marcas se evalúan |

## 4. `ejecuciones.csv` · la entrada en bruto

Es el fichero que **simula lo que devolvería el paso de consulta a los LLMs**. Contiene el texto de cada respuesta **sin evaluar**.

| Columna | Descripción |
|---|---|
| `Ejecucion_ID` | Identificador único de la ejecución (`EJ-0001`…) |
| `Sector` | Sector del estudio |
| `Prompt_ID` | Plantilla de la que procede |
| `Familia`, `Intención` | Familia del prompt y fase del embudo |
| `Prompt ejecutado` | Texto exacto enviado al motor (ya instanciado) |
| `Motor` | `ChatGPT`, `Gemini`, `Perplexity` o `Claude` |
| `Repetición` | 1, 2 o 3 |
| `Marcas a evaluar` | Marcas cuya aparición se evalúa en esta ejecución, separadas por ` | ` (todas las del sector, o solo una o dos si el prompt las nombra) |
| `Respuesta completa` | Texto de la respuesta (estilo propio de cada motor) |
| `Fuentes citadas` | Dominios que el motor ha consultado o citado. **Vacío** si no lanzó búsqueda |
| `Fecha/hora` | Marca temporal sintética |

## 5. Esquema de evaluación recomendado

Es el formato con el que trabaja reload.: una fila por **marca evaluada en cada ejecución**. No recibís el registro completo: lo tenéis que producir vosotros a partir de `ejecuciones.csv`. Sí recibís `muestra_evaluada.csv`, con **15 ejecuciones ya evaluadas** (133 filas) con exactamente este esquema. Cubre los cuatro motores, los cuatro tipos de prompt y las cuatro fases del embudo, y casos límite: una respuesta sin búsqueda, una mención por desconocimiento, una mención negativa y una consulta sobre Barcelona. Usadla para entender cómo se evalúa y para **calibrar vuestro evaluador**: evaluad esas 15 ejecuciones con vuestro sistema y comparad. Podéis ampliar o simplificar el esquema si lo justificáis.

| # | Columna | Descripción |
|---:|---|---|
| 1 | `Sector` | |
| 2 | `Marca` | Marca evaluada en esta fila |
| 3 | `Prompt_ID` | Plantilla |
| 4 | `Intención` | Fase del embudo |
| 5 | `Prompt ejecutado` | Texto exacto del prompt |
| 6 | `Motor` | |
| 7 | `Repetición` | |
| 8 | `Aparece (1/0)` | 1 si el nombre o un alias de la marca aparece en la respuesta |
| 9 | `Posición` | Orden de primera aparición entre las marcas del sector presentes (1 = la primera). Vacío si no aparece |
| 10 | `Peso posición` | 3 si posición 1 · 2 si posición 2-3 · 1 si 4 o más · 0 si no aparece |
| 11 | `Tipo de mención` | `Recomendación activa`, `Comparación neutra` o `Pasiva`. Vacío si no aparece |
| 12 | `Fuente citada` | Lista de dominios de la **ejecución** (se repite en todas las marcas de esa ejecución) |
| 13 | `Respuesta completa` | Texto de la respuesta (se repite en todas las marcas de esa ejecución) |
| 14 | `Fecha/hora` | |
| 15 | `Notas` | Incluye `DATOS SINTÉTICOS`; indica si la ejecución se evaluó para varias marcas |
| 16 | `Fuerza recomendación (-1 a 3)` | 3 · 2 · 1 · **0 si no aparece** · -1 si hay advertencia o percepción negativa |
| 17 | `Sentimiento` | `positivo`, `neutro` o `negativo`. Vacío si no aparece |
| 18 | `Tipo de fuente` | Tipo de fuente en la que se apoya el motor para esa marca (ver catálogo). `Sin fuente` si no hay búsqueda o se admite no conocer la marca |
| 19 | `Fuera de territorio` | Aviso de respuesta de otra categoría. **Vacío en este kit** |
| 20 | `Ejecucion_ID` | Clave para cruzar con `ejecuciones.csv` |

### Cosas que conviene saber

- **La respuesta se repite** en cada fila de la misma ejecución. Si agregáis texto, deduplicad por `Ejecucion_ID`.
- **No todas las filas son comparables.** En los prompts de tipo `marca` solo se evalúa esa marca (y aparece casi siempre); en los de tipo `par` solo las dos marcas enfrentadas; en `generico` y `ciudad`, las 10 marcas. Ver *visibilidad espontánea vs asistida* en la metodología.
- **«Aparece = 1» no siempre es buena señal**: una respuesta puede nombrar una marca para decir que no la conoce (tipo `Pasiva`, fuerza `1`, fuente `Sin fuente`).
- **`Fuente citada` es de la ejecución, `Tipo de fuente` es de la marca.** Una misma respuesta puede apoyar a una marca en un ranking y a otra en su propia web.

## 6. `fuentes_catalogo.csv`

| Columna | Descripción |
|---|---|
| `Dominio` | Dominio que puede aparecer en `Fuentes citadas` |
| `Tipo_de_fuente` | Ranking / institución · Medio · Web propia · Directorio / comparador · Plataforma de reseñas · Red social / foro |
| `Calidad_de_fuente_0_1` | Peso de calidad usado en el score (ver metodología) |

Los dominios con extensión `.example` son ficticios. Algunos (por ejemplo `wikipedia.org`, `google.com`, `reddit.com`, `trustpilot.com`, `tripadvisor.es`, `booking.com`, `youtube.com`) son plataformas reales usadas solo como **tipo de fuente genérico**: el dataset no afirma nada sobre ellas.

## 7. Ideas para empezar con los datos

- Estudiar `muestra_evaluada.csv` y evaluar con vuestro sistema las respuestas de `ejecuciones.csv` (detección de marcas con alias, posición, fuerza, sentimiento y fuente) y calcular el **score** con la fórmula de la metodología.
- Separar **visibilidad espontánea y asistida** y comprobar cómo cambia el relato.
- Buscar **dónde se cae la marca**: por motor, por fase del embudo, por familia de prompt y por ciudad.
- Comparar el **perfil de fuentes** de la marca con el de sus competidores.
