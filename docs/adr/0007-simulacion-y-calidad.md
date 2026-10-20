# ADR 0007 · Simulación del impacto del plan y evaluación de calidad del sistema

- **Estado:** aceptado
- **Fecha:** 2026-10-21
- **Zona:** A (con la base del juez de la Zona B)

## Contexto

El Nivel 3 del doc 07 pide dos cosas:

- **Simular el impacto del plan (N3.4):** escenarios explícitos, el score recalculado con la misma
  fórmula, los supuestos a la vista y que quede claro que no predice visitas.
- **Evaluar la calidad del propio sistema (N3.5):** soporte de las afirmaciones, relevancia,
  viabilidad y cumplimiento del brief, con un juez contrastado con una rúbrica humana.

No hay datos reales del efecto de las acciones GEO: cualquier número que demos es un supuesto.

## Decisión: simulación (`domain/simulation.py`)

Modelo **explícito y conservador**, puro y determinista:

1. **Segmentos:** la población espontánea de la marca foco se reparte en fase × motor, suponiendo
   que fase y motor son independientes. Las ciudades son segmentos aparte.
2. **Alcance de una acción:**
   - **Qué acciones cuentan:** solo las enlazadas a hallazgos del estudio. La palanca `medicion`
     no mueve la visibilidad.
   - **Fase:** la `fase_embudo` de la acción; si no tiene, la de sus hallazgos; si tampoco, todas.
   - **Motores:** los `motores_objetivo`; si no hay, todos.
   - **Ciudad:** si la descripción nombra una ciudad con datos, solo ese segmento.
3. **Mejora por acción:** el rango (mínimo, esperado, máximo) de la tabla, sumado a la tasa
   espontánea de cada segmento al que apunta.
4. **Rendimientos decrecientes:** en cada segmento, la k-ésima acción aporta 0,6^k de su mejora.
   Además hay un **tope de +20 puntos por segmento** y la tasa no pasa del 95 %.
5. **Score:** se recalcula con `scoring.score_from_profile`, la misma fórmula y sin duplicarla.
   Se mantiene el perfil de las apariciones de hoy (peso de posición, fuerza y calidad de fuente
   medios). El resultado es el score actual más la diferencia, acotado a [0, 100].
6. **Fases:** la proyección es acumulada por fase del plan. Siempre va con los supuestos y una
   advertencia fija: es una estimación, no una predicción.

### `IMPACTO_POR_PALANCA` (mejora de la tasa espontánea del segmento, en puntos)

| Palanca | S (mín/esp/máx) | M (mín/esp/máx) | L (mín/esp/máx) |
|---|---|---|---|
| autoridad_terceros | 1 / 2,5 / 4 | 2 / 5 / 8 | 3 / 7,5 / 12 |
| contenido | 1 / 2 / 3,5 | 2 / 4 / 7 | 3 / 6 / 10,5 |
| entidad_datos | 0,5 / 1,5 / 2,5 | 1 / 3 / 5 | 1,5 / 4,5 / 7,5 |
| reputacion | 0,5 / 1 / 2 | 1 / 2 / 4 | 1,5 / 3 / 6 |
| comunidades | 0 / 0,8 / 1,5 | 0,5 / 1,5 / 3 | 0,8 / 2,3 / 4,5 |
| tecnico | 0 / 0,5 / 1 | 0 / 1 / 2 | 0 / 1,5 / 3 |
| medicion | 0 | 0 | 0 |

**Por qué este orden.** Sigue las palancas de la metodología del kit (§9) y lo que vemos en los
datos:

- **Autoridad en terceros** va primera porque los motores citan sobre todo rankings, medios y
  directorios. La brecha de fuentes con el líder es de las mayores del kit.
- **Contenido** que responde a los prompts reales va justo detrás.
- **Entidad y datos** ayudan a que el motor reconozca la marca, pero por sí solos no hacen que la
  recomiende.
- **Reputación y comunidades** influyen de forma más indirecta.
- **Lo técnico** es una condición necesaria, pero mueve poco la visibilidad.
- **La medición** no mueve la visibilidad: sirve para saber si lo demás funciona.

**Escala.** S = ½ M y L = 1,5 M. Los valores son deliberadamente bajos: una acción M mueve unos
pocos puntos el segmento al que apunta, y el tope de 20 puntos impide escenarios irreales.

## Decisión: evaluación de calidad

- **`domain/plan_questions.py`:** cinco preguntas tipadas por acción, en el mismo formato que
  `judge_questions`. Son cuatro Noul (`es_especifica`, `coherente_con_hallazgo`,
  `respeta_restricciones`, `realista_para_equipo`) y un Score de 4 niveles (`calidad_global`). El
  texto del plan viaja como dato.
- **`adapters/judge/plan_guard.py`:** reutiliza la base de los jueces (mismo cliente, caché,
  trazas y presupuesto) mediante `ask()`, ahora genérico para cualquier batería de preguntas. Si la
  confianza es baja, repregunta al fallback.
  - Devuelve un `PlanQuality` orientativo **que no bloquea nada**.
  - Una acción queda por debajo de umbral si falla un Noul o si su calidad es menor que 2.
- **`domain/evidence.py`:** cobertura de evidencia, es decir, hallazgos cuyos `evaluation_ids`
  existen y acciones cuyos `finding_ids` apuntan a hallazgos válidos.
- **`scripts/evaluate_system.py`:** junta la calibración del juez, la cobertura, la calidad del plan
  y la simulación, y guarda `docs/evaluacion/<fecha>.md`.
- Los modelos nuevos viven en `simulation_schemas.py` y `quality_schemas.py`. `schemas.py` y
  `ports.py` no cambian.

## Consecuencias

- **Lo que permite:** enseñar «qué pasaría si se ejecuta el plan» con un rango y sus supuestos, y
  cambiar la tabla sin tocar la fórmula del score.
- **La tabla es una hipótesis del equipo:** hay que revisarla cuando haya re-mediciones reales. La
  versión del modelo (`SIMULATION_VERSION`) va en el resultado.
- **Solo se simula la visibilidad espontánea.** No se modelan cambios de fuerza ni de fuente,
  aunque el doc 07 los menciona como escenarios posibles. Las apariciones nuevas heredan el perfil
  de las actuales.
- **Límites conocidos:** la independencia entre fase y motor y el solapamiento entre ciudad y fase
  son aproximaciones. El tope por segmento limita su efecto.
- **El juez de calidad todavía no está contrastado con una rúbrica humana** (lo pide N3.5). Queda
  pendiente, igual que la calibración del juez de menciones, porque hoy no hay claves.
