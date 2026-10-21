# ADR 0009 · Escenarios del plan

- **Estado:** aceptado
- **Fecha:** 2026-10-21
- **Zona:** A

## Contexto

El consultor tiene que poder decir «con este presupuesto, este equipo y estas prioridades, ¿qué
parte del plan hacemos y qué pasa con el score?». Los contratos ya están en `develop`
(`domain/scenario_schemas.py`: `EntradaEscenario`, `AccionAplazada`, `EscenarioPlan`). Falta la
función que los rellena.

Dos límites del contrato condicionan el diseño:

- `Action` **no tiene coste**. Solo tiene `esfuerzo` S/M/L. El sistema no puede estimar euros.
- `Finding` tiene `impacto` S/M/L (no hay «gravedad»).

## Decisión

`domain/scenarios.py` es puro y determinista. La simulación la hace `simulation.simulate_plan`, que
no se toca.

### Firmas

```python
build_scenario(plan, findings, metrics, entrada, nombre="personalizado",
               *, detalle_desactivada=..., medicion_cubre=True) -> EscenarioPlan
build_preset(nombre, plan, findings, metrics) -> EscenarioPlan  # minimo_viable | equilibrado | completo
build_presets(plan, findings, metrics) -> list[EscenarioPlan]   # los tres, en ese orden
minimal_cover(plan, objetivos: Iterable[str]) -> list[str]      # ids de acciones, en orden del plan
```

`build_scenario` lanza `ValueError` si `acciones_activas` o `costes_declarados` nombran acciones que
no están en el plan, o si el plan repite ids de acción (la API debería traducirlo a 422). Las
comparaciones con el presupuesto toleran 10⁻⁶ € de redondeo.

### Orden de evaluación

1. Las acciones se recorren en **orden topológico de `dependencias`**. Entre las que están listas,
   va primero la que va antes en el plan (fase y, dentro de la fase, posición). Así cada acción se
   decide después de las acciones de las que depende, aunque vayan más tarde en el plan.
2. Las dependencias que no son acciones del plan se ignoran: no hay nada que mantener ni aplazar.
3. Las acciones de un ciclo de dependencias, y las que dependen de ellas, se deciden al final, en
   orden del plan, y se aplazan por `dependencia` («bloqueada por un ciclo de dependencias»).

### Precedencia de motivos

Se registra el primer motivo que se cumple:

| # | Motivo | Cuándo |
|---|---|---|
| 1 | `desactivada` | No está en `acciones_activas` (None = todas activas). |
| 2 | `dependencia` | Alguna dependencia del plan no se mantiene. Es en cascada. El `detalle` nombra cada dependencia y su motivo, p. ej. «depende de A0-2 (aplazada: desactivada), que no se mantiene». |
| 3 | `fuera_de_prioridad` | Hay `prioridad` y la palanca de la acción no está en ella. |
| 4 | `fuera_de_presupuesto` | La acción tiene coste en `costes_declarados` y no cabe en lo que queda de `presupuesto_eur`. |
| 5 | `capacidad` | Sus puntos (S = 1, M = 2, L = 3) no caben en lo que queda de `capacidad`. |

Las decisiones del consultor (activar o priorizar) van antes que los recursos. Una acción aplazada
no consume presupuesto ni capacidad. El llenado es **voraz en el orden de evaluación**: si una acción
grande no cabe, una posterior más pequeña puede caber.

### Presupuesto: nunca se inventan costes

- Solo consumen presupuesto las acciones con coste declarado por el consultor.
- **Las acciones sin coste declarado se mantienen y no consumen presupuesto.** Un presupuesto sin
  ningún coste declarado no aplaza nada.
- `coste_declarado_eur` suma los costes declarados de las mantenidas. Es `None` si ninguna mantenida
  tiene coste declarado.
- Un coste declarado sin presupuesto solo se suma.

### Cobertura y simulación

- `hallazgos_sin_cubrir`: hallazgos (en el orden recibido) a los que no apunta ninguna acción
  mantenida.
- `simulacion`: `simulate_plan` sobre una copia del plan con **las mismas fases** y solo las
  acciones mantenidas. Las fases vacías siguen dando su proyección acumulada. Con todas las
  acciones, el resultado es idéntico al de `simulate_plan(plan, …)`.
- `intervalo`: hoy es `None`. El IC del score llega con `feature/A-rigor-estadistico` (ADR 0008,
  todavía no en `develop`). Se enchufará en `build_scenario`, en el `EscenarioPlan(...)` final:
  `intervalo=<IC del score proyectado esperado>`. No hace falta cambiar contratos.

### Preajustes

Ninguno fija presupuesto, costes, capacidad ni prioridad. Cada uno solo decide `acciones_activas`
y pasa por `build_scenario`, así que los motivos son los mismos que en un escenario personalizado.
Las acciones que un preajuste deja fuera salen como `desactivada`, con un detalle que lo explica.

**Recubrimiento mínimo (`minimal_cover`).** Es el conjunto de acciones de **menor esfuerzo total**
que cubre unos hallazgos objetivo, con todas sus dependencias. Es exacto, no voraz:

- **Búsqueda:** se ramifica sobre el primer objetivo sin cubrir. Se prueba cada acción que lo cubre
  junto con el cierre transitivo de sus dependencias. Toda solución óptima contiene, para ese
  objetivo, una de esas acciones y su cierre, así que la búsqueda es completa. Se poda cuando un
  conjunto parcial ya no mejora el mejor encontrado.
- **Desempate:** con igual esfuerzo gana la solución de menos acciones. Si sigue el empate, gana la
  de índices del plan menores en orden lexicográfico. El resultado no depende del orden de los
  hallazgos.
- **Qué acciones entran:** solo las ejecutables, es decir, fuera de ciclos. Los objetivos que
  ninguna acción ejecutable cubre se ignoran y quedan en `hallazgos_sin_cubrir`.
- **La medición no cubre:** una acción de palanca `medicion` no cuenta como cobertura de ningún
  hallazgo, porque no mueve la visibilidad (la simulación le da efecto 0). Sí entra si otra acción
  elegida depende de ella. Un hallazgo que solo enlazan acciones de medición no es objetivo de
  ningún preajuste y queda en `hallazgos_sin_cubrir`.
- **Tamaño:** la profundidad es como mucho el número de hallazgos (de 3 a 7 en una propuesta), así
  que el coste es trivial.

| Preajuste | Regla exacta |
|---|---|
| `minimo_viable` | `minimal_cover` de los hallazgos del **nivel de impacto más alto que el plan puede cubrir** (L si hay alguno cubrible; si no, M; si no, S). |
| `equilibrado` | `minimal_cover` de **todos los hallazgos de impacto L y M**. Los S quedan fuera salvo que los cubra de paso una acción elegida. |
| `completo` | Todas las acciones (entrada vacía). |

**Qué es cubrir.** Hay dos reglas según quién decide las acciones:

- **En un escenario personalizado** rige la definición del contrato: un hallazgo está cubierto si
  una acción mantenida apunta a él, también si es de medición (`build_scenario`,
  `medicion_cubre=True`).
- **En los tres preajustes** (`completo` incluido) la medición no cubre: `hallazgos_sin_cubrir` se
  calcula sin ella (`medicion_cubre=False`). Decir que la línea base «cubre» la brecha con el líder
  sería engañoso.

### Ejemplos

Ejemplo sintético (en `tests/domain/test_scenarios.py`). Hay dos hallazgos L (L1, L2), uno M y uno S:

| Acción | Fase | Esfuerzo | Cubre | Depende de |
|---|---|---|---|---|
| BASE | 0 | M | L1 | |
| BARATA | 0 | S | L2 | BASE |
| GRANDE | 1 | L | L1, L2, M1 | |
| M | 1 | S | M1 | |
| S | 1 | S | S1 | |

- **`minimo_viable`:** los objetivos son L1 y L2. BASE + BARATA cuesta 3 puntos, igual que GRANDE,
  y gana GRANDE por tener menos acciones. Para cubrir solo L2 sin GRANDE hace falta BARATA, que
  arrastra BASE.
- **`equilibrado`:** los objetivos son L1, L2 y M1. GRANDE (3) es mejor que BASE + BARATA + M (4).
- **`completo`:** las cinco acciones.

**Alborada** (`tests/golden/test_scenarios_golden.py`, plan de ejemplo y hallazgos del kit; score
actual 25,93). El score es el final (mínimo / esperado / máximo):

| Preajuste | Mantenidas | Esfuerzo | Sin cubrir | Score final |
|---|---|---|---|---|
| `minimo_viable` | A0-2, A1-2, A2-3 | 5 | F-caida-embudo, F-recomendacion-debil | 26,56 / 27,67 / 28,84 |
| `equilibrado` | A0-2, A1-1, A1-2, A2-3 | 7 | — | 26,83 / 28,20 / 29,78 |
| `completo` | las 9 | 16 | — | 27,77 / 30,77 / 33,95 (= la canónica 25,9 → 30,8) |

Cómo se llega a cada preajuste:

- **`minimo_viable`:** los hallazgos L son F-motor-debil, F-ciudad-barcelona y F-brecha-lider, y el
  mínimo son 5 puntos.
  - Para F-motor-debil, A0-2 (M) empata con A3-2 (M) y gana A0-2 por orden del plan.
  - Para F-ciudad-barcelona, A1-2 (S).
  - Para F-brecha-lider, A2-3 (M). También lo enlazan A0-1 y A3-1, pero son de medición y no
    cubren. A2-3 cubre además F-asistida-vs-espontanea.
- **`equilibrado`:** los 7 hallazgos son L o M y el mínimo son 7 puntos.
  - A1-1 es la única acción que cubre F-caida-embudo y F-recomendacion-debil, y arrastra A0-2.
  - A2-3 es la única que cubre F-asistida-vs-espontanea.
  - Con A1-2 queda todo cubierto. A0-1 (la medición base) queda fuera porque no hace falta para
    cubrir nada.

## Consecuencias

- **Permite** a la API (zona C) ofrecer un endpoint de escenarios. La entrada sería un
  `EntradaEscenario` o el nombre de un preajuste, y la salida un `EscenarioPlan`, sin LLM. Encaja
  con la vista de la #24: cada `EscenarioPlan` se envuelve en `EscenarioGuardado(id, elegido,
  escenario)` de `application/diferencial.py`.
- **Los preajustes optimizan la cobertura de hallazgos por esfuerzo, no el score.** Al no contar
  la medición como cobertura, ningún preajuste se llena de acciones que no mueven nada. La
  contrapartida es que el mínimo viable y el equilibrado de Alborada dejan fuera la medición base
  (A0-1). El consultor puede añadirla con un escenario personalizado. Si se quisiera optimizar el
  score, sería otro preajuste.
- **El llenado voraz por capacidad o presupuesto no es óptimo**, pero es predecible y explicable:
  sigue el orden del plan, que ya refleja la secuencia que propone el consultor.
- **`intervalo` sigue en `None`** hasta que llegue el IC del score (ADR 0008).
