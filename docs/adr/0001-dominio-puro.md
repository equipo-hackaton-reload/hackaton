# ADR 0001 · Dominio puro

- **Estado:** aceptado
- **Fecha:** 2026-10-20
- **Zona:** A

## Contexto

posiq. combina código determinista (detección, score, métricas, hallazgos) con LLM (brief, juez,
plan). El reto exige cifras con origen verificable y reproducibles, separar visibilidad espontánea
y asistida, y no inventar datos. Cinco personas trabajan en paralelo sobre los mismos contratos.

## Decisión

- `src/posiq/domain/` es puro: solo Pydantic, pandas y stdlib. No importa `adapters`,
  `application` ni `interfaces`, ni librerías de red o base de datos, y se prueba sin red.
- La única I/O es la lectura local del kit. Cada `load_*` de `kit_loader.py` es una envoltura de una
  línea sobre un `*_from_frame` puro, que es lo que reutilizan los demás.
- `schemas.py` es la única fuente de verdad. Usa las categorías del kit tal cual: fuerza de −1 a 3,
  los tipos de mención «Recomendación activa», «Comparación neutra» y «Pasiva», y los tipos de fuente
  del catálogo.
- Las preguntas del juez son datos en `judge_questions.py`, sin depender del SDK. Las usan igual el
  adaptador Jev y el fallback. Se pregunta una vez por marca y ejecución.
- La aparición y la posición las decide la detección por reglas, que es la definición de la
  metodología. El juez aporta tipo de mención, fuerza, sentimiento y apoyo en fuentes. Si el juez y
  las reglas discrepan en la aparición, la confianza baja a 0,5.
- Toda cifra (score, tasas, brechas) sale de `scoring.py` y `metrics.py`. Los hallazgos salen de
  reglas explícitas en `findings.py`, cada uno con `evaluation_ids` reales.

## Consecuencias

- Las métricas son reproducibles y comprobables con tests golden sobre el kit. El LLM solo redacta a
  partir de cifras ya calculadas.
- Cambiar una categoría o un campo es un `contract-change` que afecta a todas las zonas.
- Juzgar por marca supone más llamadas al juez: 2.928 en el kit frente a 624 si se juzgara por
  respuesta. Hay que vigilarlo con `BUDGET_EUR_MAX`.
- El kit no trae `perfil`, y el tipo de fuente por marca no se puede deducir de las fuentes de la
  ejecución. Cuando no se resuelve, queda `None` y el score usa la calidad media de las fuentes
  citadas en la ejecución.
