Prompts versionados en Markdown, uno por nodo: `<nodo>.v1.md` (Zona E).

| Prompt | Esquema de salida | Claves de `state` |
|---|---|---|
| `intake.v1.md` | `BriefSummary` | `brief` |
| `market.v1.md` | `Market` | `brief_summary`, `marcas_candidatas` |
| `prompts.v1.md` | `PromptSet` (en este paquete) | `brief_summary`, `market`, `banco_plantillas` |
| `plan.v1.md` | `Plan` | `brief_summary`, `metrics`, `findings` |
| `write.v1.md` | `Proposal` | `study`, `brief_summary`, `market`, `prompt_set`, `metrics`, `findings`, `plan` |

Cada fichero empieza por una cabecera YAML (`name`, `version`, `schema`, `state`) y sigue con las
instrucciones. Reglas:

- El texto no contiene datos ni marcadores de interpolación (nada entre llaves): los datos llegan en
  `state` y el adaptador LLM los envía como datos, nunca dentro de las instrucciones.
- Cada prompt prohíbe inventar cifras: solo se citan las que llegan en `state`.
- Un cambio de comportamiento crea una versión nueva (`.v2.md`); no se edita una versión publicada.

`load_prompt("plan")` devuelve un `PromptSpec` con la cabecera validada; `spec.version_tag`
(`plan.v1`) es lo que se registra en `Trace.prompt_version`.
