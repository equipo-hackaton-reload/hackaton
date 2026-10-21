# ADR 0011 · Exactitud de marca: afirmaciones, verificación, riesgo regulatorio y mitigación

- **Estado:** aceptado
- **Fecha:** 2026-10-21
- **Zona:** A (`domain/accuracy.py`), con la capa LLM en C (`application/accuracy.py`), el prompt en
  E (`prompts/claims.v1.md`) y una rama del `FixtureLLM` en B

## Contexto

Que un asistente nombre la marca no basta: lo que dice de ella tiene que ser cierto. Una sede que no
existe o un servicio negado pierde pacientes. En sanidad, además, frases como «resultados
garantizados» o «la mejor clínica» deben revisarse antes de reutilizarlas. Los contratos
(`Afirmacion`, `Verificacion`, `HallazgoExactitud`, `AccionMitigacion`, `ETIQUETA_RIESGO`) ya
están en `domain/accuracy_schemas.py`. Este ADR fija cómo se rellenan.

Regla 1: los números los calcula código determinista. La IA, si se usa, solo lee y propone
fragmentos.

## Decisión

### 1. Extracción por reglas (`extraer_afirmaciones`)

- Solo se miran las ejecuciones que piden evaluar la marca. Dentro de ellas, las **oraciones que
  la nombran**, con la misma detección del score (nombre y alias, sin acentos).
- Una afirmación es un par **(oración, tipo)**. Su `texto` es el fragmento **literal** de la
  respuesta: la oración, acotada a 300 caracteres alrededor de la marca si es más larga.
  `evaluation_id = run_id:brand_id`, que es la convención de todo el sistema. `fuentes_citadas`
  son los dominios de `Run.fuentes`.
- Vocabulario por tipo:
  - **servicio:** `SERVICIOS_CONOCIDOS` (20 servicios de oftalmología, con equivalencias: LASIK →
    cirugía refractiva) más los `servicios_prioritarios` del brief.
  - **sede:** `CIUDADES_CONOCIDAS` (capitales de provincia y grandes ciudades) más las ciudades del
    brief y las que pase quien llama. El kit solo trae Madrid y Barcelona; sin una lista más
    amplia no se podría detectar una sede que el brief no recoge.
  - **profesional:** «Dr./Dra. Nombre», «N oftalmólogos», «equipo médico».
  - **precio:** importes en €, «gratis», «precios ajustados», «financiación», «low cost».
  - **resultado clínico:** «tasa de éxito», «N % de éxito», «visión perfecta», «garantiza
    resultados»…
  - **otro:** oración que no tiene ninguno de los anteriores pero sí una expresión a revisar.
- **Atribución:** un término cuenta para la marca solo si la marca más cercana que lo precede en
  la oración (o, si no hay ninguna antes, la siguiente) es la del estudio. Así, «Tramuntana tiene
  centros en Valencia, mientras que Alborada…» no le atribuye Valencia a Alborada. Los términos
  dentro del nombre de una marca («Centro Lasik…») no cuentan.
- **Anáforas** («Es la que más recomendaría»): las reglas no las atribuyen. Es conservador y deja
  fuera parte de lo que se dice de la marca; la capa LLM puede recuperarlas.

### 2. Verificación conservadora (`verificar_afirmacion`)

Se compara con el `BriefSummary` y nada más. Orden: **incorrecta > riesgo_regulatorio > correcta /
no_verificable**.

| Tipo | correcta | incorrecta | no_verificable |
|---|---|---|---|
| servicio | todos sus servicios están en servicios prioritarios o subsector | niega un servicio del brief («no ofrece cirugía refractiva») | alguno no está en el brief, o se niega algo que el brief no recoge |
| sede | todas sus ciudades están en el brief | niega una ciudad del brief, o afirma una sede («sede / centro / clínica… en X») en una ciudad que el brief no recoge | nombra una ciudad sin afirmar sede («pacientes de Sevilla…»), o el brief no trae ciudades |
| profesional | el nombre está en `equipo` del brief | nunca | lo demás: el brief no recoge el equipo médico (`equipo` describe el equipo de marketing) |
| precio, resultado clínico, otro | nunca | nunca | siempre: el brief no trae precios ni resultados |

`dato_brief` es la entrada del brief contra la que se comparó. Vale `None` cuando no hay con qué
comparar. **Nunca es `incorrecta` por falta de dato.**

El mismo análisis vale para las afirmaciones del LLM: se vuelve a analizar el fragmento.

### 3. Riesgo regulatorio: la lista (`EXPRESIONES_RIESGO`)

La etiqueta es `ETIQUETA_RIESGO` = «a revisar por la clínica». Es una lista explícita de
expresiones que la clínica debería revisar antes de reutilizarlas o de dejar que se asocien a su
marca. Parte de las restricciones del brief de Alborada: la publicidad sanitaria está regulada,
no se pueden prometer resultados ni hacer comparativas denigratorias.
**No es un juicio de legalidad**: el motivo lo dice siempre y nunca usa «ilegal».

| Categoría | Expresiones |
|---|---|
| Garantía de resultado | garantiza / garantizado · garantía de resultado / éxito · resultado / éxito asegurado |
| Ausencia de riesgo | sin riesgo / riesgo cero / libre de riesgos · totalmente seguro · sin efectos secundarios / sin complicaciones |
| Absolutos | 100 % / cien por cien · para siempre · visión perfecta |
| Superlativos | el / la / los / las mejor(es) · número uno / n.º 1 · la opción más recomendada / recomendable · líder indiscutible |
| Comparaciones con otros centros | mejor que · más barato / seguro / eficaz / rápido que · superior a otros / a la competencia |

- Se busca en la oración, solo si la expresión es de la marca (misma atribución) y no va negada
  en su cláusula («no garantiza» no cuenta).
- **Casos frontera decididos.** «La opción más recomendada / recomendable» entra como superlativo:
  en el kit suele ir con una comparación explícita («…; la otra resulta una alternativa»). En
  cambio, «No se aprecian riesgos relevantes en las fuentes» **no** entra: habla de las fuentes,
  no promete que la intervención no tenga riesgo.
- Una afirmación correcta con una expresión de la lista pasa a `riesgo_regulatorio`, pero conserva
  `dato_brief`. En una incorrecta, las expresiones se listan y el estado sigue siendo `incorrecta`.

### 4. Mitigación (`acciones_mitigacion`)

Solo para afirmaciones **incorrectas**:

- **Fuente:** la del marcador `[n]` del fragmento (`fuentes_citadas[n-1]`). Si no hay marcador,
  cada fuente de la respuesta. Si el motor no citó ninguna, `fuente_dominio = None`.
- **Una acción por fuente.** Agrupa todas las afirmaciones que vienen de ella y lleva sus
  `afirmacion_ids` y `evaluation_ids`.

| Fuente | Palanca | Acción |
|---|---|---|
| Directorio / comparador, plataforma de reseñas | `entidad_datos` | corregir la ficha en X y que nombre, sedes y servicios coincidan en todos los directorios |
| Web propia de la marca | `contenido` | corregir el contenido propio |
| Red social / foro | `comunidades` | respuesta oficial que aclare el dato |
| Medio, ranking, dominio fuera del catálogo | `autoridad_terceros` | pedir la corrección |
| Sin fuente | `entidad_datos` | dato correcto en la web con datos estructurados (schema.org: sedes y servicios) y coherente en directorios |

### 5. Capa opcional con LLM

- `application/accuracy.extraer_afirmaciones_llm(llm, runs, brand, *, study_id, marcas)`. Hace una
  llamada `LLM.structured(AfirmacionesLLM, "claims.v1", state)` por cada ejecución que nombra la
  marca, y cada llamada deja su `Trace`. La respuesta del motor va en `state["respuesta"]`: es DATO
  y nunca entra en las instrucciones.
- El LLM solo devuelve `(texto, tipo)`. El dominio **descarta** los fragmentos que no son literales
  de la respuesta y los que repiten uno de reglas (`combinar_afirmaciones`). La verificación y los
  recuentos los hace siempre el código.
- Va en `application/` porque compone un puerto (`LLM`) con el dominio, y `domain/` no hace I/O.
- En fixture, `FixtureLLM` responde con las mismas reglas (`afirmaciones_llm_por_reglas`): es
  determinista y, combinado, no añade nada a las reglas. Lo comprueba
  `tests/application/test_accuracy_llm.py`.

## Resultado con el kit de Alborada (datos reales, solo reglas)

`evaluar_exactitud` sobre las 624 ejecuciones del kit, con el `BriefSummary` de Alborada. Fijado
en `tests/golden/test_accuracy_golden.py`:

- **276 afirmaciones** en 193 evaluaciones (ejecuciones donde se nombra a Alborada).
- **0 inexactitudes.** El kit no dice nada falso de Alborada. No se fabrican errores en los datos
  de demo; los casos de error están solo en `tests/domain/test_accuracy.py`, con respuestas
  sintéticas marcadas.

| Tipo | correcta | incorrecta | no verificable | a revisar por la clínica | total |
|---|---|---|---|---|---|
| servicio | 62 | 0 | 131 | 2 | 195 |
| profesional | 0 | 0 | 62 | 0 | 62 |
| otro | 0 | 0 | 0 | 19 | 19 |
| sede, precio, resultado clínico | 0 | 0 | 0 | 0 | 0 |
| **total** | **62** | **0** | **193** | **21** | **276** |

- **21 afirmaciones con expresiones «a revisar por la clínica»**, todas por «la opción más
  recomendada / recomendable» (p. ej. «Si priorizas la cercanía, Clínica Alborada Visión es la
  opción más recomendable; la otra resulta una alternativa a considerar»).
- **Correctas (62):** «especializada en cirugía refractiva y cataratas», que cuadra con los
  servicios prioritarios y el subsector.
- **No verificables (193):**
  - «Valoración preoperatoria completa» y «seguimiento personalizado»: el brief completo los recoge
    como diferenciales, pero el `BriefSummary` no tiene ese campo.
  - «Equipo médico muy bien valorado»: el `BriefSummary` no recoge el equipo médico. Su `equipo`
    describe el equipo de marketing.
  - Ampliar el `BriefSummary` (diferenciales, sedes, equipo médico) convertiría muchas en
    verificables. Es un `contract-change`: no se ha hecho aquí.
- **Sin sedes:** ninguna respuesta del kit sitúa a Alborada en una ciudad.

## Consecuencias

- La exactitud es reproducible y auditable: fragmento literal, motivo, dato del brief y
  evaluación de origen.
- Es conservadora a propósito: prefiere `no_verificable` a una falsa inexactitud. Por eso «0
  inexactitudes» significa «nada contradice el brief», no «todo está confirmado».
- Las reglas no resuelven anáforas, ni negaciones complejas («solo tiene sede en Madrid»), ni
  sinónimos fuera del vocabulario. La capa LLM puede proponer más fragmentos, pero no cambia
  cómo se verifican.
- Las listas (`SERVICIOS_CONOCIDOS`, `CIUDADES_CONOCIDAS`, `EXPRESIONES_RIESGO`) son de
  oftalmología y España. Para otro sector, se amplían en el dominio con sus tests.
