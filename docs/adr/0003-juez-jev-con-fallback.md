# ADR 0003 · Juez Jev con fallback LLM y política de confianza en código

- **Estado:** aceptado
- **Fecha:** 2026-10-21
- **Zona:** B

## Contexto

Cada marca elegible de cada ejecución necesita tipo de mención, fuerza, sentimiento y apoyo en
fuentes. En el kit son 2.928 evaluaciones. La metodología pide un juez que se pueda validar contra
una muestra etiquetada. El reto exige trazar el coste y degradar con elegancia cuando falla un
proveedor. Las preguntas del juez son contrato de la Zona A (`domain/judge_questions.py`).

## Decisión

- **Juez principal: Jev (TypeSafe System One).** Es barato (0,04 $/M de entrada) y devuelve
  respuestas tipadas con su confianza.
- **Fallback: las mismas preguntas respondidas por un LLM** compatible con OpenAI (DeepSeek), a
  través de `system-one-adapter`.
- **Nunca se redefinen las preguntas en los adaptadores:** ambos jueces envían `JUDGE_QUESTIONS` tal
  cual, y la combinación con la detección por reglas la hace `answers_to_evaluation`.
- **La política de confianza vive en código** y usa los umbrales de settings. La confianza que
  decide es el mínimo de `mentioned`, `mention_type` y `strength`, que son las preguntas que mueven
  el score; en un Noul, la distancia a 0,5 hace de confianza. Si el juez y las reglas discrepan
  sobre la aparición, la confianza se limita a 0,5.
  - Con confianza ≥ ACCEPT, la evaluación se acepta.
  - Entre FALLBACK y ACCEPT, se acepta y se marca con `necesita_revision`, un campo nuevo de
    `Evaluation` y por tanto un cambio de contrato.
  - Por debajo de FALLBACK, se delega en el juez LLM.
- **`build_judge(settings, market)`** devuelve Jev con fallback si hay `TYPESAFE_API_KEY`, o solo el
  juez LLM si no la hay. `market` es necesario para calcular la posición entre las marcas presentes.
- **Cada llamada deja una `Trace`** (modelo, versión de las preguntas, tokens, coste y duración) que
  alimenta el `Budget` del estudio.
- **Las respuestas se cachean en disco** por estado y versión de las preguntas.
- **Los reintentos con espera creciente ante 408, 429 y 5xx** los hace el SDK, y un semáforo limita
  la concurrencia de los lotes.

## Consecuencias

- **El juez se puede sustituir** sin tocar el dominio ni la orquestación (contrato `ports.Judge`).
- **Cambiar un umbral no exige rehacer llamadas:** gracias a la caché, la política se reaplica
  sobre las respuestas guardadas.
- **La calibración** (`scripts/calibrate_judge.py`) mide el juez en bruto sobre las 133 etiquetas,
  con el split de calibración y reserva del doc 07, y deja el informe en `docs/calibracion/`.
- **La aparición y la posición siguen siendo de las reglas:** el juez solo puede bajar la
  confianza, no cambiarlas.
- **`evaluate()` es síncrono y usa `asyncio.run`:** dentro de un bucle de eventos (FastAPI, grafo
  asíncrono) hay que llamar a `aevaluate` o a `aevaluate_many`.
