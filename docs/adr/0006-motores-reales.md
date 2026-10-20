# ADR 0006 · Motores reales con búsqueda web

- **Estado:** aceptado (sin probar en real: no hay claves de API todavía)
- **Fecha:** 2026-10-21
- **Zona:** B

## Contexto

El nivel 3 del reto pide medir la visibilidad en los asistentes reales y no solo en
`ejecuciones.csv`. Un asistente real busca en la web antes de responder, así que la guía de APIs del
kit (`data/kit/03_Documentacion/05_Guia_de_APIs_y_costes.md`) pide activar la búsqueda web en cada
API y quedarse con el dominio de cada fuente citada. También pide reintentos con espera creciente,
un límite de paralelismo, caché en disco y registro de modelo, fecha y coste. El scraping de las
interfaces web está prohibido.

## Decisión

Un `Engine` por proveedor en `adapters/engines/`. Todos heredan de `RealEngine` (`base.py`), y cada
uno solo implementa la llamada a su SDK con la búsqueda activada.

| Motor | Fichero · SDK | Cómo se activa la búsqueda | Dónde salen las fuentes | Precio provisional (USD) |
|---|---|---|---|---|
| ChatGPT | `openai.py` · `openai` (Responses API) | `tools=[{"type": "web_search"}]` | Anotaciones `url_citation` de los bloques `message`. Cada `web_search_call` cuenta como una búsqueda | `gpt-5-mini`: 0,25 / 2,00 por M · 0,01 por búsqueda |
| Gemini | `gemini.py` · `google-genai` | `GenerateContentConfig(tools=[Tool(google_search=GoogleSearch())])` | `candidates[0].grounding_metadata.grounding_chunks[].web`. El dominio sale de `domain`, o de `title` si la `uri` es una redirección de `vertexaisearch` | `gemini-2.5-flash`: 0,30 / 2,50 por M · 0,035 por petición con búsqueda |
| Perplexity | `perplexity.py` · `openai` con `base_url` de Perplexity | Sonar busca por defecto en todas las peticiones | `citations` y, si faltan, `search_results[].url` | `sonar`: 1,00 / 1,00 por M · 0,005 por petición |
| Claude | `anthropic.py` · `anthropic` (Messages API) | Herramienta de servidor `web_search_20260209` (`web_search_20250305` en Haiku) con `max_uses=5` | Solo las citadas: `citations` de tipo `web_search_result_location` en los bloques `text` (no todos los `web_search_tool_result`). Las búsquedas salen de `usage.server_tool_use.web_search_requests` | `claude-opus-5-5`: 4,00 / 20,00 por M · 0,01 por búsqueda |

- **Los precios son provisionales.** Hay que contrastarlos con la página oficial antes del primer
  estudio. Son claves de `settings.py` (`PRICING_<MOTOR>_IN/OUT/SEARCH`), así que se ajustan en
  `.env` sin tocar código. El modelo de cada motor también se configura
  (`<PROVEEDOR>_ENGINE_MODEL`).
- **Coste de una `Run`:** tokens de entrada × precio de entrada + tokens de salida × precio de
  salida + búsquedas × precio por búsqueda, convertido a EUR con `USD_EUR`. En Gemini, los tokens de
  razonamiento cuentan como salida.
- **Fuentes:** dominio en minúsculas y sin `www.`, sin repetir. Su tipo se resuelve contra
  `fuentes_catalogo.csv`, y un subdominio hereda el de su dominio padre (`es.wikipedia.org` →
  `wikipedia.org`). Si el dominio no está en el catálogo, `tipo` y `calidad` quedan en `None`.
- **Solo fuentes citadas, en los cuatro motores.** El Score de Citación compara motores entre sí, y
  ChatGPT, Gemini y Perplexity solo devuelven lo que citan. Si contáramos todo lo que Claude vio en
  `web_search_tool_result`, la calidad de fuentes saldría sesgada a su favor. Por eso en Claude solo
  cuentan las `citations` de los bloques de texto.
- **Sin búsqueda no es un error.** Si no hay fuentes, se escribe un INFO en el log y la `Run` sale
  con `fuentes=[]`, igual que `Fuentes citadas` vacío en el kit. Si Claude buscó pero no citó nada,
  se registra `busco_sin_citar=True` en el log. `Run` no tiene campo de metadatos, y añadirlo sería
  un `contract-change`.
- **Reintentos:** los clientes se crean con `max_retries=0` y reintenta `RealEngine._retry`, para
  que las esperas no se multipliquen. Reintenta ante 408, 409, 429, 5xx y errores de red, con espera
  exponencial y jitter (`ENGINE_MAX_RETRIES`, `ENGINE_BACKOFF_BASE_S`, máximo 30 s). Un 400 falla
  a la primera.
- **Paralelismo:** un semáforo por motor (`ENGINE_CONCURRENCY`) limita las llamadas en vuelo, y
  `ask_many` reparte prompt × repetición en un pool de hilos. Devuelve la `Run` o la excepción de
  cada combinación, para que un fallo aislado no pare al resto.
- **Caché:** `DiskCache` con la clave `(engine:<motor>, modelo, hash del texto del prompt,
  repetición)`. Guarda la respuesta normalizada con su fecha original. Un acierto de caché no se
  paga: la `Run` sale con `coste_eur=0` y no deja traza.
- **Presupuesto:** cada llamada pagada deja una `Trace` (`nodo=engine:<motor>`,
  `prompt_version=<prompt_id>`) en el `Budget` del estudio. Con el presupuesto agotado no se lanza
  ninguna llamada más.
- **Claude, búsquedas largas:** con `stop_reason == "pause_turn"` se reenvía el turno del asistente
  tal cual, sin añadir un «continúa», y el servidor sigue. Se hacen como mucho 5 continuaciones y el
  texto y las fuentes de todos los tramos se concatenan.
- **Claude, fallback de modelo: opt-in.** Viene desactivado (`ANTHROPIC_ENGINE_FALLBACK=false`):
  si respondiera otro modelo, las repeticiones dejarían de ser comparables. Con el fallback activo
  (no disponible en Haiku), se envía `fallbacks="default"` y, si responde otro modelo, `Run.modelo`
  lo registra y el log lo avisa.
- **Claves:** `OPENAI_API_KEY`, `GEMINI_API_KEY`, `PERPLEXITY_API_KEY` y `ANTHROPIC_API_KEY`. Sin
  clave, el motor se construye y falla al llamar con `MissingCredentialError`, que nombra la
  variable. `build_engines(settings, "real", marcas)` devuelve solo los motores con clave y avisa en
  el log de los que faltan. `build_engines(settings, "kit")` devuelve los cuatro `KitEngine`.
- **`marcas_a_evaluar`:** el puerto `Engine.ask` no recibe el mercado, así que el motor real lo
  recibe al construirse (ids de las marcas del estudio).

## Consecuencias

- **El modo real degrada:** sin claves, `build_engines` devuelve una lista vacía y la orquestación
  puede volver al kit.
- **Sin probar en real:** los adaptadores solo están probados con respuestas simuladas de cada SDK.
  La primera prueba es `scripts/smoke_engines.py` (3 prompts × motores con clave × 1 repetición,
  guardada en `data/smoke/<fecha>.jsonl`). Hay que revisar a mano que las fuentes y los tokens que
  salen coinciden con la consola de cada proveedor.
- **Coste de Claude:** con Opus 5.5, los resultados de búsqueda entran como tokens de entrada (miles
  por llamada). Es el motor más caro de los cuatro. `ANTHROPIC_ENGINE_MODEL=claude-haiku-5-5`
  (0,10 / 0,50 por M) lo abarata para desarrollar, pero entonces hay que ajustar también
  `PRICING_CLAUDE_IN/OUT`.
- **Dependencias nuevas:** `google-genai` y `anthropic`.
- **Los resultados que Claude vio y no citó se descartan:** no se guardan ni en la `Run` ni en la
  caché. Si en el futuro interesan, hay que guardarlos aparte, sin mezclarlos con las fuentes
  citadas.
