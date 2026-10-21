# ADR 0014 · Capa determinista frente a no determinista en el juez

- **Estado:** aceptado
- **Fecha:** 2026-10-21
- **Zona:** B (amplía el ADR 0003)

## Contexto

Cada evaluación de una marca en una respuesta de un motor combina dos tipos de juicio. Uno es
comprobable con código: ¿aparece la marca?, ¿en qué posición? El otro es semántico: ¿es una
recomendación o una mención de pasada?, ¿con qué fuerza?, ¿con qué tono? Hay que poder defender
qué cifra sale de cada sitio y qué pasa cuando las dos capas no están de acuerdo.

## Decisión

| Capa | Qué decide | Determinista |
|---|---|---|
| **Reglas** (`domain/detection.py`) | Aparición y posición, por alias y orden en el texto. Es el suelo del score y la referencia que audita al juez | Sí: el mismo texto da siempre lo mismo |
| **Jev** (TypeSafe System One, `jev-1.13`) | Tipo de mención, fuerza, sentimiento y apoyo en fuentes, con probabilidades calibradas por pregunta | No, pero acotado: versión fijada, caché en disco por estado y versión de las preguntas |
| **LLM de fallback** (DeepSeek vía `system-one-adapter`) | Las MISMAS preguntas cuando Jev duda | No, menos que Jev; solo actúa por debajo del umbral |
| **Persona** | Toda evaluación marcada con `necesita_revision` | — |

**Política** (en código, umbrales en `settings`). La confianza es el mínimo de `mentioned`,
`mention_type` y `strength`.

- Con confianza ≥ 0,80 (`JUDGE_CONFIDENCE_ACCEPT`), se acepta.
- Entre 0,55 y 0,80, se acepta y se marca para revisión.
- Por debajo de 0,55 (`JUDGE_CONFIDENCE_FALLBACK`), se delega en el LLM de fallback.

**Al discrepar.** Si Jev contradice a las reglas sobre la aparición (dice «no aparece» o elige
`ausente` donde las reglas la ven, o al revés), `discrepa()` es verdadero:

1. La confianza se limita a 0,5, así que la evaluación se delega en el fallback.
2. La evaluación final sale **siempre con `necesita_revision=True`**, aunque el fallback responda
   con confianza alta. Un segundo modelo no desempata contra las reglas: desempata una persona.
3. Aparición y posición siguen siendo las de las reglas. El juez nunca puede subir el score
   inventando una mención.

**Reproducibilidad.** `JEV_MODEL=jev-1.13` en lugar del alias móvil `jev-latest`. La API de System
One no admite temperatura ni semilla (`SystemOneRequest` solo lleva `model`, `state`, `questions`
y `assets`). La `Trace` registra el modelo que devuelve la respuesta (`response.model`, que puede
diferir del pedido), además de los tokens, el coste y la versión de las preguntas.

## Consecuencias

- **Frase para la deck:** «las reglas deterministas ponen el suelo y auditan, Jev aporta la
  semántica calibrada y, si discrepan, revisa un humano».
- **Más revisión humana:** cada discrepancia de aparición llega a la cola de revisión. La
  calibración la cuenta en `discrepancias`.
- **Sin temperatura ni semilla**, la variación entre llamadas no se puede anular. Se acota con la
  versión fijada y con la caché, y se mide repitiendo llamadas.
- **Cambiar de versión de Jev** exige recalibrar (`scripts/calibrate_judge.py`): el nombre del
  modelo forma parte de la clave de caché.
