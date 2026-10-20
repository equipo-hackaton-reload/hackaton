# Reto GEO · Sistema agéntico de visibilidad de marca en LLMs

**Hackathon EPS-UFV × reload.**

---

## 1. El reto en una frase

> Construir un **sistema agéntico** que, a partir del **brief de una marca**, analice en profundidad **cómo la ven, la citan y la recomiendan los LLMs** (frente a su competencia y según el momento del embudo de decisión del usuario) y genere una **propuesta de mejora con un plan de acción completo**: fases, entregables, tiempos, responsables y KPIs.

Un único input —el brief de la marca— y una única salida: la propuesta.

## 2. Por qué es relevante

Cada vez más personas preguntan a ChatGPT, Gemini, Perplexity o Claude *«¿qué clínica / hotel / aseguradora / máster me recomiendas?»* en lugar de buscar en Google y abrir diez enlaces. Si una marca no aparece en esas respuestas, para ese usuario **no existe**. Y aparecer no basta: importa en qué posición, si la recomiendan activamente, con qué argumentos y apoyándose en qué fuentes.

A esta disciplina se la llama **GEO** (*Generative Engine Optimization*): medir y mejorar la presencia de una marca en las respuestas de los motores de IA generativa. reload. la trabaja con sus clientes y quiere escalar y automatizar el proceso que va **del brief al plan de acción**.

## 3. Qué debe hacer el sistema

```
                     BRIEF DE MARCA
                              │
   ┌──────────────────────────▼──────────────────────────┐
   │ 1. Interpretar el brief (negocio, público, mercados) │
   │ 2. Preparar el estudio (competidores, prompts por    │
   │    fase del embudo, geografías)                      │
   │ 3. Consultar a los LLMs (con búsqueda web, varias    │
   │    repeticiones)                                     │
   │ 4. Evaluar las respuestas (¿aparece?, ¿en qué        │
   │    posición?, ¿cómo la mencionan?, ¿qué fuentes?)    │
   │ 5. Diagnosticar (visibilidad, competencia, embudo,   │
   │    motores, fuentes)                                 │
   │ 6. Definir la estrategia y el plan de acción         │
   │ 7. Redactar la propuesta final                       │
   └──────────────────────────┬──────────────────────────┘
                              ▼
      PROPUESTA DE MEJORA DE VISIBILIDAD EN LLMs
      (plan por fases · entregables · tiempos · KPIs)
```

El paso 3 se puede alimentar con los datos del kit (`ejecuciones.csv`), sin llamar a ninguna API. Los pasos 1, 2, 4, 5, 6 y 7 son el corazón del reto.

## 4. Alcance del MVP

Para que el trabajo sea demostrable en el hackathon, os proponemos tres niveles. **Todos los equipos deben cubrir el Nivel 1.**

### Nivel 1 · Imprescindible (MVP demostrable)
- Aceptar un **brief de marca** (texto libre, formulario o documento).
- Trabajar con los **datos del kit** (sin necesidad de APIs), **evaluar las respuestas** y producir un **diagnóstico** con, como mínimo:
  - visibilidad espontánea por motor de IA,
  - visibilidad por fase del embudo (descubrimiento, comparación, validación, decisión),
  - posición frente a la competencia,
  - calidad de las menciones y fuentes que alimentan las respuestas.
- Generar una **propuesta con plan de acción por fases** (acciones, entregables, tiempos, responsables, KPIs).
- Una **interfaz** (web, app, dashboard o flujo) que permita hacer una **demo de principio a fin con el brief de ejemplo** del kit.

### Nivel 2 · Deseable
- **Arquitectura agéntica explícita**: roles o agentes con responsabilidades claras, orquestación y trazabilidad de qué hizo cada uno.
- **Generar vuestros propios prompts** del embudo a partir del brief.
- **Evaluación propia y validada** de las respuestas: por ejemplo, un LLM-juez contrastado con una muestra revisada a mano.
- Priorización de acciones por **esfuerzo e impacto**.
- Exportación de la propuesta (Word, PDF o presentación).

### Nivel 3 · Extra (suma puntos)
- Ejecución **real** contra al menos dos APIs de LLM **con búsqueda web**.
- **Descubrimiento automático de competidores** a partir de las respuestas.
- **Re-medición** y seguimiento de la evolución en el tiempo.
- Simulación del impacto esperado del plan.
- Evaluación de la calidad del propio sistema (por ejemplo, un LLM-juez validado contra una muestra humana).
- Soporte multimarca o multisector.

## 5. Qué os entregamos y qué no

**Incluido en el kit** (carpeta `02_Kit_de_trabajo`):
- Un **brief de ejemplo** y la plantilla del brief.
- Para ese caso, un **estudio de visibilidad sintético completo**: banco de prompts, marcas y alias, catálogo de fuentes, 624 respuestas en bruto de 4 motores (sin evaluar) y una muestra de 15 ejecuciones ya evaluadas para calibrar vuestro evaluador.
- Documentación de **metodología GEO**, **diccionario de datos**, **flujo actual de reload.** y **arquitectura de referencia**, **guía de APIs y costes** y **formato del entregable**.

**No incluido**:
- Código de la solución ni de reload. Lo construís vosotros.
- Claves de API. El reto se puede resolver completo con los datos del kit; conectar APIs reales es un extra.
- Datos confidenciales. Todo el material es **sintético o ficticio**.

> **Importante:** las marcas, cifras y respuestas del kit son **inventadas**. Sirven para construir y probar el sistema, pero **no representan el comportamiento real** de ningún LLM ni de ninguna empresa. No las presentéis como datos reales.

## 6. Entregables de cada equipo

1. **Prototipo funcional** demostrable (con repositorio o paquete para poder reproducirlo).
2. **Documento de arquitectura** (1-2 páginas): diagrama, componentes y agentes, decisiones técnicas y alternativas descartadas, qué hace el LLM y qué hace el código, costes estimados, riesgos y limitaciones.
3. **Salida del sistema para el brief de ejemplo**: la propuesta generada.
4. **Presentación y demo** del trabajo (duración según el calendario de la organización).

## 7. Criterios de evaluación (propuesta, sobre 100)

| Criterio | Peso | Qué valoramos |
|---|---:|---|
| **Funcionalidad del MVP y demo** | 25 | Funciona de principio a fin con el brief de ejemplo; estabilidad |
| **Calidad del análisis GEO** | 20 | Rigor metodológico: distingue visibilidad espontánea de asistida, tiene en cuenta competencia, embudo, motores y fuentes; las cifras son correctas y trazables |
| **Calidad y accionabilidad del plan** | 20 | Plan por fases con entregables, tiempos, responsables y KPIs; acciones concretas, priorizadas y conectadas con los hallazgos (no genéricas) |
| **Arquitectura técnica y justificación** | 15 | Diseño coherente, decisiones argumentadas, separación clara entre lo que decide el LLM y lo que calcula el código, control de costes y errores |
| **UX y claridad de la salida** | 10 | La propuesta se entiende y se podría enviar a un cliente; visualización útil |
| **Innovación** | 5 | Ideas propias que mejoran el enfoque (más allá de lo pedido) |
| **Presentación** | 5 | Claridad, defensa del trabajo y gestión del tiempo |

**Señales de calidad que buscaremos:**
- Las cifras del diagnóstico **salen de los datos o del código**, no las inventa el LLM.
- El plan **responde a los hallazgos concretos** de la marca (no un plan genérico).
- Se reconocen y declaran **las limitaciones** (datos sintéticos, no determinismo, muestra pequeña).

## 8. Reglas del juego y buenas prácticas

- **Honestidad con los datos**: no inventéis cifras; indicad siempre el origen de cada número.
- **Trazabilidad**: cada hallazgo debe poder justificarse con una evidencia (tabla, respuesta, fuente).
- **Privacidad y legalidad**: respetad los términos de uso de cada API si las usáis.
- **Uso responsable de la IA**: validad lo que genera el LLM; tened cuidado con las alucinaciones, sobre todo en sectores sensibles (por ejemplo, el sanitario).
- **Costes**: si usáis APIs reales, estimad antes el coste y limitad el número de llamadas (ver la guía de APIs y costes).

## 9. Preguntas frecuentes

**¿Tenemos que llamar a ChatGPT, Gemini, etc.?** No. Con los datos del kit se puede resolver todo el reto. Llamar a APIs reales es un extra valorado.

**¿Podemos usar otras marcas o sectores?** Sí, como extra. Pero la demo base debe funcionar con el brief de ejemplo del kit.

**¿Hay una solución correcta?** Hay hallazgos que un buen análisis debería encontrar, pero no un único plan válido. Valoramos la calidad del razonamiento y la accionabilidad.

**¿Qué tecnología hay que usar?** La que queráis. Os pedimos que justifiquéis las decisiones en el documento de arquitectura.
